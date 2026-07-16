"""SPEC-093: the deterministic gate evaluator — verdicts, precedence, binding."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

import pytest

from l8_evidence.gates.evaluator import EvaluatorError, evaluate
from l8_evidence.gates.experiment import Evidence, ExperimentRecord, PreRegistration
from l8_evidence.gates.facts import Fact, FactsRegistry
from l8_evidence.gates.outcomes import EVALUATOR_VERSION, GateOutcome, GateResult
from l8_evidence.gates.spec import GateDefinition, GateItem, GateKind, GateSpec

pytestmark = pytest.mark.spec("SPEC-093")

_AS_OF = date(2026, 7, 16)
_DATA = "sha256:" + "1" * 64
_MODEL = "sha256:" + "2" * 64
_DIGEST = "sha256:" + "3" * 64

_CHECKLIST_GATE = GateDefinition(
    gate_id="GATE-C",
    kind=GateKind.CHECKLIST,
    items=(
        GateItem(item_id="harm_item", on_false=GateOutcome.FAIL_HARM),
        GateItem(item_id="futility_item", on_false=GateOutcome.FAIL_FUTILITY),
        GateItem(item_id="continue_item", on_false=GateOutcome.CONTINUE),
    ),
)

_EVIDENCE_GATE = GateDefinition(
    gate_id="GATE-E",
    kind=GateKind.EVIDENCE,
    decision="anytime_valid_bounds_v1",
    items=(GateItem(item_id="precondition", on_false=GateOutcome.FAIL_HARM),),
)

_PAYBACK_GATE = GateDefinition(
    gate_id="GATE-P",
    kind=GateKind.CHECKLIST,
    items=(
        GateItem(
            item_id="payback_within_precommitted_horizon",
            on_false=GateOutcome.FAIL_FUTILITY,
            computed="payback_v1",
        ),
    ),
)

_SPEC = GateSpec(
    version="gates-v1",
    digest=_DIGEST,
    gates=(_CHECKLIST_GATE, _EVIDENCE_GATE, _PAYBACK_GATE),
)

_FRESH_FACTS = FactsRegistry(facts=(), digest="sha256:" + "4" * 64)

_PREREG = PreRegistration(
    minimum_economic_effect=Decimal("0.005"),
    harm_threshold=Decimal("-0.010"),
    alpha_budget=Decimal("0.05"),
    confidence_level=Decimal("0.99"),
    max_n=4000,
    number_of_prior_trials=3,
    primary_endpoint="paired race-level log-score difference",
    stopping_rule="anytime-valid confidence sequence",
)

_GOOD_EVIDENCE = Evidence(
    lower_bound=Decimal("0.007"),
    upper_bound=Decimal("0.020"),
    n=2100,
    loss_budget_breached=False,
)


def _checklist_record(attestations: Mapping[str, bool]) -> ExperimentRecord:
    return ExperimentRecord(experiment_id="exp-c", gate_id="GATE-C", attestations=dict(attestations))


def _evidence_record(
    evidence: Evidence | None,
    prereg: PreRegistration | None = _PREREG,
    attestations: Mapping[str, bool] | None = None,
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id="exp-e",
        gate_id="GATE-E",
        preregistration=prereg,
        evidence=evidence,
        attestations=dict(attestations if attestations is not None else {"precondition": True}),
    )


def _run(
    record: ExperimentRecord, facts: FactsRegistry = _FRESH_FACTS, spec: GateSpec = _SPEC
) -> GateResult:
    return evaluate(
        spec=spec,
        experiment=record,
        facts=facts,
        data_manifest=_DATA,
        model_manifest=_MODEL,
        as_of=_AS_OF,
    )


_ALL_TRUE = {"harm_item": True, "futility_item": True, "continue_item": True}


# --- checklist gates -----------------------------------------------------------------


def test_checklist_all_true_passes() -> None:
    result = _run(_checklist_record(_ALL_TRUE))
    assert result.outcome is GateOutcome.PASS
    assert result.reasons == ()


def test_missing_attestation_is_continue_not_a_violation() -> None:
    result = _run(_checklist_record({"harm_item": True, "futility_item": True}))
    assert result.outcome is GateOutcome.CONTINUE
    assert "continue_item" in " ".join(result.reasons)


def test_false_harm_item_fails_harm() -> None:
    result = _run(_checklist_record({**_ALL_TRUE, "harm_item": False}))
    assert result.outcome is GateOutcome.FAIL_HARM
    assert "harm_item" in " ".join(result.reasons)


def test_false_futility_item_fails_futility() -> None:
    result = _run(_checklist_record({**_ALL_TRUE, "futility_item": False}))
    assert result.outcome is GateOutcome.FAIL_FUTILITY


def test_false_continue_item_is_continue() -> None:
    result = _run(_checklist_record({**_ALL_TRUE, "continue_item": False}))
    assert result.outcome is GateOutcome.CONTINUE


def test_harm_dominates_futility_when_both_items_are_false() -> None:
    result = _run(_checklist_record({"harm_item": False, "futility_item": False, "continue_item": True}))
    assert result.outcome is GateOutcome.FAIL_HARM


def test_unknown_attestation_id_is_an_evaluator_error() -> None:
    with pytest.raises(EvaluatorError):
        _run(_checklist_record({**_ALL_TRUE, "not_in_the_gate": True}))


# --- evidence gates ------------------------------------------------------------------


def test_efficacy_crossed_passes() -> None:
    result = _run(_evidence_record(_GOOD_EVIDENCE))
    assert result.outcome is GateOutcome.PASS


def test_lower_bound_equal_to_minimum_effect_is_not_a_pass() -> None:
    evidence = Evidence(
        lower_bound=Decimal("0.005"), upper_bound=Decimal("0.020"), n=2100, loss_budget_breached=False
    )
    assert _run(_evidence_record(evidence)).outcome is GateOutcome.CONTINUE


def test_upper_bound_below_harm_threshold_fails_harm() -> None:
    evidence = Evidence(
        lower_bound=Decimal("-0.050"), upper_bound=Decimal("-0.020"), n=200, loss_budget_breached=False
    )
    assert _run(_evidence_record(evidence)).outcome is GateOutcome.FAIL_HARM


def test_upper_bound_equal_to_harm_threshold_is_not_harm() -> None:
    evidence = Evidence(
        lower_bound=Decimal("-0.050"), upper_bound=Decimal("-0.010"), n=200, loss_budget_breached=False
    )
    assert _run(_evidence_record(evidence)).outcome is GateOutcome.CONTINUE


def test_loss_budget_breach_fails_harm_despite_efficacy() -> None:
    evidence = Evidence(
        lower_bound=Decimal("0.007"), upper_bound=Decimal("0.020"), n=2100, loss_budget_breached=True
    )
    assert _run(_evidence_record(evidence)).outcome is GateOutcome.FAIL_HARM


def test_missing_evidence_is_continue() -> None:
    assert _run(_evidence_record(None)).outcome is GateOutcome.CONTINUE


def test_false_precondition_uses_its_declared_flavour() -> None:
    result = _run(_evidence_record(_GOOD_EVIDENCE, attestations={"precondition": False}))
    assert result.outcome is GateOutcome.FAIL_HARM


def test_missing_precondition_blocks_pass() -> None:
    result = _run(_evidence_record(_GOOD_EVIDENCE, attestations={}))
    assert result.outcome is GateOutcome.CONTINUE


def test_max_n_reached_without_efficacy_fails_futility() -> None:
    evidence = Evidence(
        lower_bound=Decimal("0.001"), upper_bound=Decimal("0.004"), n=4000, loss_budget_breached=False
    )
    assert _run(_evidence_record(evidence)).outcome is GateOutcome.FAIL_FUTILITY


def test_max_n_reached_with_efficacy_still_passes() -> None:
    evidence = Evidence(
        lower_bound=Decimal("0.007"), upper_bound=Decimal("0.020"), n=4000, loss_budget_breached=False
    )
    assert _run(_evidence_record(evidence)).outcome is GateOutcome.PASS


def test_evidence_gate_without_preregistration_is_an_evaluator_error() -> None:
    with pytest.raises(EvaluatorError):
        _run(_evidence_record(_GOOD_EVIDENCE, prereg=None))


# --- multiplicity (SPEC-091 accounting, exact multiplication) ------------------------


def _prereg_with_trials(trials: int, alpha: str = "0.05", confidence: str = "0.99") -> PreRegistration:
    return PreRegistration(
        minimum_economic_effect=Decimal("0.005"),
        harm_threshold=Decimal("-0.010"),
        alpha_budget=Decimal(alpha),
        confidence_level=Decimal(confidence),
        max_n=4000,
        number_of_prior_trials=trials,
        primary_endpoint="paired race-level log-score difference",
        stopping_rule="anytime-valid confidence sequence",
    )


def test_multiplicity_boundary_is_exact_at_equality() -> None:
    # (1 - 0.99) * (4 + 1) = 0.05 exactly: binary floats would overshoot and wrongly refuse.
    result = _run(_evidence_record(_GOOD_EVIDENCE, prereg=_prereg_with_trials(4)))
    assert result.outcome is GateOutcome.PASS


def test_multiplicity_exceeded_blocks_pass() -> None:
    result = _run(_evidence_record(_GOOD_EVIDENCE, prereg=_prereg_with_trials(5)))
    assert result.outcome is GateOutcome.CONTINUE
    assert "alpha" in " ".join(result.reasons).lower()


# --- facts join ----------------------------------------------------------------------


def _facts(*facts: Fact) -> FactsRegistry:
    return FactsRegistry(facts=facts, digest="sha256:" + "5" * 64)


def test_stale_fact_fails_harm_despite_overwhelming_efficacy() -> None:
    stale = Fact(fact_id="STALE", populated=True, recheck_by=date(2026, 1, 1), used_by=())
    result = _run(_evidence_record(_GOOD_EVIDENCE), facts=_facts(stale))
    assert result.outcome is GateOutcome.FAIL_HARM
    assert "STALE" in " ".join(result.reasons)


def test_misconfigured_fact_fails_harm() -> None:
    bad = Fact(fact_id="BAD", populated=True, recheck_by=None, misconfigured=True, used_by=())
    result = _run(_checklist_record(_ALL_TRUE), facts=_facts(bad))
    assert result.outcome is GateOutcome.FAIL_HARM


def test_unpopulated_required_fact_is_continue() -> None:
    needed = Fact(fact_id="NEEDED", populated=False, recheck_by=None, used_by=("GATE-C",))
    result = _run(_checklist_record(_ALL_TRUE), facts=_facts(needed))
    assert result.outcome is GateOutcome.CONTINUE
    assert "NEEDED" in " ".join(result.reasons)


def test_unpopulated_unrelated_fact_does_not_block() -> None:
    other = Fact(fact_id="OTHER", populated=False, recheck_by=None, used_by=("GATE-Z",))
    result = _run(_checklist_record(_ALL_TRUE), facts=_facts(other))
    assert result.outcome is GateOutcome.PASS


# --- payback_v1 computed item (§10.4) ------------------------------------------------


def _payback_record(inputs: Mapping[str, Decimal | int]) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id="exp-p",
        gate_id="GATE-P",
        computed_inputs={"payback_v1": dict(inputs)},
    )


_VIABLE = {
    "n_eligible_per_year": 2500,
    "r_select": Decimal("0.10"),
    "r_fill": Decimal("0.80"),
    "mean_stake": Decimal("2.00"),
    "roi_lower": Decimal("0.02"),
    "c_recurring_per_year": Decimal("2.00"),
    "c_fixed": Decimal("10.00"),
    "max_payback_years": Decimal("2"),
}
# annual = 2500 * 0.10 * 0.80 * 2.00 * 0.02 - 2.00 = 8.00 - 2.00 = 6.00; T = 10/6 <= 2.


def test_viable_payback_passes() -> None:
    assert _run(_payback_record(_VIABLE)).outcome is GateOutcome.PASS


def test_payback_boundary_equality_is_viable() -> None:
    # c_fixed == max_payback_years * annual exactly (12.00 == 2 * 6.00).
    assert (
        _run(_payback_record({**_VIABLE, "c_fixed": Decimal("12.00")})).outcome is GateOutcome.PASS
    )


def test_payback_just_over_the_horizon_fails_futility() -> None:
    result = _run(_payback_record({**_VIABLE, "c_fixed": Decimal("12.01")}))
    assert result.outcome is GateOutcome.FAIL_FUTILITY


def test_recurring_costs_swallowing_the_contribution_fails_futility() -> None:
    result = _run(_payback_record({**_VIABLE, "c_recurring_per_year": Decimal("8.00")}))
    assert result.outcome is GateOutcome.FAIL_FUTILITY


def test_missing_computed_inputs_is_continue() -> None:
    record = ExperimentRecord(experiment_id="exp-p", gate_id="GATE-P")
    assert _run(record).outcome is GateOutcome.CONTINUE


def test_incomplete_computed_inputs_is_continue() -> None:
    partial = {k: v for k, v in _VIABLE.items() if k != "roi_lower"}
    assert _run(_payback_record(partial)).outcome is GateOutcome.CONTINUE


def test_hand_attesting_a_computed_item_is_an_evaluator_error() -> None:
    record = ExperimentRecord(
        experiment_id="exp-p",
        gate_id="GATE-P",
        attestations={"payback_within_precommitted_horizon": True},
        computed_inputs={"payback_v1": dict(_VIABLE)},
    )
    with pytest.raises(EvaluatorError):
        _run(record)


# --- binding and provenance ----------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "deadbeef",
        "sha256:" + "1" * 63,
        "sha256:" + "G" * 64,
        "sha256:" + "A" * 64,  # uppercase hex refused
        "md5:" + "1" * 64,
        " sha256:" + "1" * 64,
    ],
)
def test_malformed_data_manifest_is_an_error_never_a_verdict(bad: str) -> None:
    with pytest.raises(EvaluatorError):
        evaluate(
            spec=_SPEC,
            experiment=_checklist_record(_ALL_TRUE),
            facts=_FRESH_FACTS,
            data_manifest=bad,
            model_manifest=_MODEL,
            as_of=_AS_OF,
        )


def test_malformed_model_manifest_is_an_error_never_a_verdict() -> None:
    with pytest.raises(EvaluatorError):
        evaluate(
            spec=_SPEC,
            experiment=_checklist_record(_ALL_TRUE),
            facts=_FRESH_FACTS,
            data_manifest=_DATA,
            model_manifest="not-a-manifest",
            as_of=_AS_OF,
        )


def test_unknown_gate_in_the_record_is_an_error() -> None:
    record = ExperimentRecord(experiment_id="exp-x", gate_id="GATE-UNKNOWN")
    with pytest.raises(EvaluatorError):
        _run(record)


def test_result_embeds_the_full_binding() -> None:
    result = _run(_checklist_record(_ALL_TRUE))
    assert result.gate_id == "GATE-C"
    assert result.experiment_id == "exp-c"
    assert result.data_manifest == _DATA
    assert result.model_manifest == _MODEL
    assert result.spec_version == "gates-v1"
    assert result.spec_digest == _DIGEST
    assert result.facts_digest == _FRESH_FACTS.digest
    assert result.evaluator_version == EVALUATOR_VERSION
    assert result.as_of == _AS_OF
