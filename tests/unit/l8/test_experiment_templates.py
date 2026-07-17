"""SPEC-094: typed experiment pre-registration templates (ADR 0017 S6, phase seven).

Covers the five exported template instances (market-only baseline, surface-elo,
weighted-elo, bradley-terry, stage2-combined), the decision-unit validation against the
trial ledger's permitted vocabulary, the structural impossibility of producing trial
registration fields without human-supplied pre-registered endpoints, the no-defaults rule
on those endpoints, the zero-numeric-literal constraint on the module, and the round-trip
of template output into a real SPEC-091 TrialRegistration.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

import l8_evidence.experiment_templates as experiment_templates_module
from l8_evidence.experiment_templates import (
    ALL_EXPERIMENT_TEMPLATES,
    BRADLEY_TERRY_TEMPLATE,
    MARKET_ONLY_BASELINE_TEMPLATE,
    STAGE2_COMBINED_TEMPLATE,
    SURFACE_ELO_TEMPLATE,
    WEIGHTED_ELO_TEMPLATE,
    ExperimentTemplate,
    ExperimentTemplateError,
    PreRegisteredEndpoints,
    PreRegistrationIncompleteError,
    TemplateValidationError,
)
from l8_evidence.prediction_snapshots import DualClockTimestamp
from l8_evidence.sample_size import PowerAssumptions, assert_no_borrowed_gate_constants
from l8_evidence.trial_ledger import (
    PERMITTED_DECISION_UNITS,
    DateWindow,
    TrialLedger,
    TrialRegistration,
)

pytestmark = pytest.mark.spec("SPEC-094")

_FIVE_FAMILIES = (
    "market-only-baseline",
    "surface-elo",
    "weighted-elo",
    "bradley-terry",
    "stage2-combined",
)


def _assumptions(delta: str = "0.004") -> PowerAssumptions:
    return PowerAssumptions(
        alpha=Decimal("0.05"),
        power=Decimal("0.8"),
        sigma_d=Decimal("0.12"),
        delta=Decimal(delta),
        two_sided=True,
    )


def _endpoints(delta: str = "0.004") -> PreRegisteredEndpoints:
    return PreRegisteredEndpoints(
        minimum_economic_effect=Decimal(delta),
        power_assumptions=_assumptions(delta),
        stopping_rule="anytime-valid confidence sequence, pre-registered spending schedule",
    )


def _template(**overrides: object) -> ExperimentTemplate:
    fields: dict[str, object] = {
        "template_id": "exp-template-example",
        "template_version": "adr-0017-s6",
        "description": (
            "example template; running it stays blocked on purchased data and founder "
            "approval"
        ),
        "decision_unit": "match",
        "candidate_model_family": "surface-elo",
        "baseline_comparator": "market-only-baseline",
        "primary_endpoint_description": (
            "paired decision-unit-level log-score difference against the baseline"
        ),
    }
    fields.update(overrides)
    return ExperimentTemplate(**fields)  # type: ignore[arg-type]


class TestTemplateInstances:
    def test_exactly_five_templates_exported(self) -> None:
        assert len(ALL_EXPERIMENT_TEMPLATES) == 5
        families = tuple(t.candidate_model_family for t in ALL_EXPERIMENT_TEMPLATES)
        assert families == _FIVE_FAMILIES

    def test_named_constants_carry_their_families(self) -> None:
        assert MARKET_ONLY_BASELINE_TEMPLATE.candidate_model_family == "market-only-baseline"
        assert SURFACE_ELO_TEMPLATE.candidate_model_family == "surface-elo"
        assert WEIGHTED_ELO_TEMPLATE.candidate_model_family == "weighted-elo"
        assert BRADLEY_TERRY_TEMPLATE.candidate_model_family == "bradley-terry"
        assert STAGE2_COMBINED_TEMPLATE.candidate_model_family == "stage2-combined"

    def test_template_ids_are_unique(self) -> None:
        ids = [t.template_id for t in ALL_EXPERIMENT_TEMPLATES]
        assert len(set(ids)) == len(ids)

    def test_decision_units_come_from_the_permitted_vocabulary(self) -> None:
        for template in ALL_EXPERIMENT_TEMPLATES:
            assert template.decision_unit in PERMITTED_DECISION_UNITS

    def test_candidates_compare_against_the_market_only_baseline(self) -> None:
        for template in ALL_EXPERIMENT_TEMPLATES:
            assert template.baseline_comparator == "market-only-baseline"

    def test_every_template_documents_the_data_and_approval_block(self) -> None:
        for template in ALL_EXPERIMENT_TEMPLATES:
            lowered = template.description.lower()
            assert "purchased data" in lowered, template.template_id
            assert "founder approval" in lowered, template.template_id

    def test_templates_are_frozen(self) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            SURFACE_ELO_TEMPLATE.template_id = "renamed"  # type: ignore[misc]


class TestTemplateValidation:
    def test_selection_level_decision_unit_is_refused(self) -> None:
        # The unit of analysis is the mutually exclusive choice set, never the
        # individual selection.
        with pytest.raises(TemplateValidationError):
            _template(decision_unit="runner")

    @pytest.mark.parametrize(
        "field",
        [
            "template_id",
            "template_version",
            "description",
            "candidate_model_family",
            "baseline_comparator",
            "primary_endpoint_description",
        ],
    )
    def test_blank_required_text_is_refused(self, field: str) -> None:
        with pytest.raises(TemplateValidationError):
            _template(**{field: "  "})

    def test_templates_carry_no_numeric_fields(self) -> None:
        # SPEC-094: endpoints are declared per-experiment by a human before
        # observation; the template type cannot even hold a number.
        for field in dataclasses.fields(ExperimentTemplate):
            assert field.type == "str", field.name

    def test_error_taxonomy(self) -> None:
        assert issubclass(TemplateValidationError, ExperimentTemplateError)
        assert issubclass(PreRegistrationIncompleteError, ExperimentTemplateError)


class TestPreRegisteredEndpoints:
    def test_all_fields_are_mandatory_with_no_defaults(self) -> None:
        for field in dataclasses.fields(PreRegisteredEndpoints):
            assert field.default is dataclasses.MISSING, field.name
            assert field.default_factory is dataclasses.MISSING, field.name

    def test_minimum_effect_must_equal_the_power_delta(self) -> None:
        # The declared minimum economically meaningful effect and the delta the sample
        # size was derived from must be the same pre-registered number.
        with pytest.raises(TemplateValidationError):
            PreRegisteredEndpoints(
                minimum_economic_effect=Decimal("0.005"),
                power_assumptions=_assumptions("0.004"),
                stopping_rule="anytime-valid confidence sequence",
            )

    def test_blank_stopping_rule_is_refused(self) -> None:
        with pytest.raises(TemplateValidationError):
            PreRegisteredEndpoints(
                minimum_economic_effect=Decimal("0.004"),
                power_assumptions=_assumptions("0.004"),
                stopping_rule="   ",
            )

    def test_wrong_types_are_refused(self) -> None:
        with pytest.raises(TemplateValidationError):
            PreRegisteredEndpoints(
                minimum_economic_effect=0.004,  # type: ignore[arg-type]
                power_assumptions=_assumptions("0.004"),
                stopping_rule="anytime-valid confidence sequence",
            )
        with pytest.raises(TemplateValidationError):
            PreRegisteredEndpoints(
                minimum_economic_effect=Decimal("0.004"),
                power_assumptions="not-assumptions",  # type: ignore[arg-type]
                stopping_rule="anytime-valid confidence sequence",
            )


class TestToTrialRegistrationFields:
    def test_missing_endpoints_raise_a_typed_incompleteness_error(self) -> None:
        # Structurally impossible to run without a human filling the endpoints.
        with pytest.raises(PreRegistrationIncompleteError):
            SURFACE_ELO_TEMPLATE.to_trial_registration_fields(None)

    def test_wrong_endpoint_type_is_refused(self) -> None:
        with pytest.raises(TemplateValidationError):
            SURFACE_ELO_TEMPLATE.to_trial_registration_fields(
                "not-endpoints"  # type: ignore[arg-type]
            )

    def test_fields_carry_the_human_supplied_endpoints(self) -> None:
        endpoints = _endpoints()
        fields = SURFACE_ELO_TEMPLATE.to_trial_registration_fields(endpoints)
        assert fields["decision_unit"] == SURFACE_ELO_TEMPLATE.decision_unit
        assert fields["primary_endpoint"] == SURFACE_ELO_TEMPLATE.primary_endpoint_description
        assert fields["minimum_economic_effect"] == endpoints.minimum_economic_effect
        assert fields["stopping_rule"] == endpoints.stopping_rule
        hypothesis = fields["hypothesis"]
        assert isinstance(hypothesis, str)
        assert "surface-elo" in hypothesis
        assert "market-only-baseline" in hypothesis

    def test_returned_fields_are_not_mutable(self) -> None:
        fields = SURFACE_ELO_TEMPLATE.to_trial_registration_fields(_endpoints())
        with pytest.raises(TypeError):
            fields["stopping_rule"] = "edited"  # type: ignore[index]

    def test_round_trip_into_a_real_trial_registration(self) -> None:
        # The template's vocabulary must plug directly into the existing SPEC-091
        # ledger, not a parallel one.
        fields = dict(SURFACE_ELO_TEMPLATE.to_trial_registration_fields(_endpoints()))
        registration = TrialRegistration(
            experiment_id="exp-2027-001",
            hypothesis=str(fields["hypothesis"]),
            decision_unit=str(fields["decision_unit"]),
            primary_endpoint=str(fields["primary_endpoint"]),
            secondary_endpoints=("decision-unit-level multiclass Brier",),
            minimum_economic_effect=Decimal(str(fields["minimum_economic_effect"])),
            training_window=DateWindow(date(2026, 1, 1), date(2026, 6, 30)),
            validation_window=DateWindow(date(2026, 7, 1), date(2026, 9, 30)),
            lockbox_window=DateWindow(date(2026, 10, 1), date(2026, 12, 31)),
            exclusions=(),
            feature_set_hash="sha256:" + "a" * 64,
            model_hash="sha256:" + "b" * 64,
            execution_policy_hash="sha256:" + "c" * 64,
            number_of_prior_trials=0,
            stopping_rule=str(fields["stopping_rule"]),
            alpha_budget=Decimal("0.05"),
            recorded_at=DualClockTimestamp(
                wall_utc=datetime(2027, 1, 1, tzinfo=timezone.utc), monotonic_ns=1
            ),
        )
        ledger = TrialLedger()
        ledger.register(registration)
        assert ledger.experiment_ids() == ("exp-2027-001",)


class TestModuleHygiene:
    def test_module_contains_zero_numeric_literals(self) -> None:
        source = inspect.getsource(experiment_templates_module)
        tree = ast.parse(source)
        numeric = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float, complex))
            and not isinstance(node.value, bool)
        ]
        assert numeric == []

    def test_module_text_carries_no_borrowed_gate_constants(self) -> None:
        source = inspect.getsource(experiment_templates_module)
        assert_no_borrowed_gate_constants(source)

    def test_no_forbidden_import_boundary_crossings(self) -> None:
        # ADR 0013 analytics boundary: no path from this module into live execution,
        # risk, broker or settlement code.
        source = inspect.getsource(experiment_templates_module)
        tree = ast.parse(source)
        forbidden_roots = ("l5_decision", "l5b_risk", "l6_broker", "l7_settle")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_roots), alias.name
            if isinstance(node, ast.ImportFrom):
                assert node.module is not None
                assert not node.module.startswith(forbidden_roots), node.module
