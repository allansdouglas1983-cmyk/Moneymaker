"""SPEC-091: the trial ledger — immutable, append-only per-experiment records.

Covers §9.7 field validation (windows, hashes, closed decision enum, lockbox overlap),
the append-only ledger's refusals (duplicate/unknown/double-completion, the prior-trial
count enforcement, the completion tamper guard), the "no update/delete API" surface, and
the round-trip into the SPEC-093 gate evaluator's multiplicity arithmetic.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from l8_evidence.gates.evaluator import evaluate
from l8_evidence.gates.experiment import Evidence, ExperimentRecord, PreRegistration
from l8_evidence.gates.facts import FactsRegistry
from l8_evidence.gates.outcomes import GateOutcome
from l8_evidence.gates.spec import GateDefinition, GateKind, GateSpec
from l8_evidence.prediction_snapshots import DualClockTimestamp
from l8_evidence.trial_ledger import (
    Attestation,
    DateWindow,
    DoubleCompletionError,
    DuplicateExperimentError,
    Exclusion,
    PriorTrialCountError,
    RegistrationDigestMismatchError,
    TrialCompletion,
    TrialDecision,
    TrialLedger,
    TrialRegistration,
    TrialValidationError,
    UnknownExperimentError,
    alpha_budget_for_evaluation,
    prior_trials_for_evaluation,
)

pytestmark = pytest.mark.spec("SPEC-091")

_FEATURE_HASH = "sha256:" + "1" * 64
_MODEL_HASH = "sha256:" + "2" * 64
_POLICY_HASH = "sha256:" + "3" * 64


def _clock(hour: int = 12) -> DualClockTimestamp:
    return DualClockTimestamp(wall_utc=datetime(2026, 7, 16, hour, 0, 0, tzinfo=timezone.utc), monotonic_ns=hour)


def _registration(
    experiment_id: str = "exp-2026-041",
    *,
    number_of_prior_trials: int = 0,
    training_window: DateWindow | None = None,
    validation_window: DateWindow | None = None,
    lockbox_window: DateWindow | None = None,
    decision_unit: str = "race",
    minimum_economic_effect: Decimal = Decimal("0.005"),
    alpha_budget: Decimal = Decimal("0.05"),
    exclusions: tuple[Exclusion, ...] = (),
    secondary_endpoints: tuple[str, ...] = ("race-level Brier",),
    feature_set_hash: str = _FEATURE_HASH,
    model_hash: str = _MODEL_HASH,
    execution_policy_hash: str = _POLICY_HASH,
) -> TrialRegistration:
    return TrialRegistration(
        experiment_id=experiment_id,
        hypothesis="combined model beats the market price on the race-level log score",
        decision_unit=decision_unit,
        primary_endpoint="paired race-level log-score difference",
        secondary_endpoints=secondary_endpoints,
        minimum_economic_effect=minimum_economic_effect,
        training_window=training_window or DateWindow(date(2024, 1, 1), date(2025, 6, 30)),
        validation_window=validation_window or DateWindow(date(2025, 7, 1), date(2025, 12, 31)),
        lockbox_window=lockbox_window or DateWindow(date(2026, 1, 1), date(2026, 6, 30)),
        exclusions=exclusions,
        feature_set_hash=feature_set_hash,
        model_hash=model_hash,
        execution_policy_hash=execution_policy_hash,
        number_of_prior_trials=number_of_prior_trials,
        stopping_rule="anytime-valid confidence sequence at the declared level",
        alpha_budget=alpha_budget,
        recorded_at=_clock(),
    )


def _completion(
    experiment_id: str,
    registration_digest: str,
    *,
    decision: TrialDecision = TrialDecision.CONTINUE,
    result: Decimal | None = Decimal("0.010"),
    confidence_interval: tuple[Decimal, Decimal] | None = (Decimal("0.001"), Decimal("0.020")),
) -> TrialCompletion:
    return TrialCompletion(
        experiment_id=experiment_id,
        registration_digest=registration_digest,
        result=result,
        confidence_interval=confidence_interval,
        decision=decision,
        attestation=Attestation(reviewer="a.reviewer", attested_at_utc=_clock(13).wall_utc),
        completed_at=_clock(14),
    )


# --- DateWindow / Exclusion / Attestation --------------------------------------------


def test_date_window_refuses_start_after_end() -> None:
    with pytest.raises(TrialValidationError):
        DateWindow(date(2026, 6, 30), date(2026, 1, 1))


def test_date_window_allows_single_day() -> None:
    DateWindow(date(2026, 1, 1), date(2026, 1, 1))


def test_exclusion_requires_nonempty_rule() -> None:
    with pytest.raises(TrialValidationError):
        Exclusion(rule="", knowledge_time_rationale="not known until backfill")


def test_exclusion_requires_nonempty_rationale() -> None:
    with pytest.raises(TrialValidationError):
        Exclusion(rule="missing runner odds", knowledge_time_rationale="")


def test_attestation_requires_nonempty_reviewer() -> None:
    with pytest.raises(TrialValidationError):
        Attestation(reviewer="", attested_at_utc=_clock().wall_utc)


def test_attestation_requires_utc_timestamp() -> None:
    with pytest.raises(TrialValidationError):
        Attestation(reviewer="a.reviewer", attested_at_utc=datetime(2026, 7, 16, 12, 0, 0))


# --- TrialRegistration field validation ------------------------------------------------


def test_registration_accepts_a_well_formed_record() -> None:
    registration = _registration()
    assert registration.experiment_id == "exp-2026-041"
    assert registration.decision_unit == "race"


def test_registration_refuses_non_race_decision_unit() -> None:
    with pytest.raises(TrialValidationError):
        _registration(decision_unit="runner")


def test_registration_refuses_empty_hypothesis() -> None:
    with pytest.raises(TrialValidationError):
        TrialRegistration(
            experiment_id="exp-1",
            hypothesis="",
            decision_unit="race",
            primary_endpoint="paired race-level log-score difference",
            secondary_endpoints=(),
            minimum_economic_effect=Decimal("0.005"),
            training_window=DateWindow(date(2024, 1, 1), date(2025, 6, 30)),
            validation_window=DateWindow(date(2025, 7, 1), date(2025, 12, 31)),
            lockbox_window=DateWindow(date(2026, 1, 1), date(2026, 6, 30)),
            exclusions=(),
            feature_set_hash=_FEATURE_HASH,
            model_hash=_MODEL_HASH,
            execution_policy_hash=_POLICY_HASH,
            number_of_prior_trials=0,
            stopping_rule="anytime-valid confidence sequence",
            alpha_budget=Decimal("0.05"),
            recorded_at=_clock(),
        )


def test_registration_refuses_non_positive_minimum_economic_effect() -> None:
    with pytest.raises(TrialValidationError):
        _registration(minimum_economic_effect=Decimal("0"))


@pytest.mark.parametrize(
    "bad_hash",
    ["", "deadbeef", "sha256:" + "1" * 63, "sha256:" + "G" * 64, "sha256:" + "A" * 64, "md5:" + "1" * 64],
)
def test_registration_refuses_malformed_feature_set_hash(bad_hash: str) -> None:
    with pytest.raises(TrialValidationError):
        _registration(feature_set_hash=bad_hash)


@pytest.mark.parametrize(
    "bad_hash",
    ["", "deadbeef", "sha256:" + "1" * 63, "sha256:" + "G" * 64],
)
def test_registration_refuses_malformed_model_hash(bad_hash: str) -> None:
    with pytest.raises(TrialValidationError):
        _registration(model_hash=bad_hash)


@pytest.mark.parametrize(
    "bad_hash",
    ["", "deadbeef", "sha256:" + "1" * 63, "sha256:" + "G" * 64],
)
def test_registration_refuses_malformed_execution_policy_hash(bad_hash: str) -> None:
    with pytest.raises(TrialValidationError):
        _registration(execution_policy_hash=bad_hash)


def test_registration_refuses_empty_secondary_endpoint() -> None:
    with pytest.raises(TrialValidationError):
        _registration(secondary_endpoints=("fine", ""))


def test_registration_refuses_number_of_prior_trials_negative_at_field_level() -> None:
    with pytest.raises(TrialValidationError):
        _registration(number_of_prior_trials=-1)


@pytest.mark.parametrize("bad_alpha", [Decimal("0"), Decimal("1"), Decimal("-0.01"), Decimal("1.01")])
def test_registration_refuses_alpha_budget_outside_open_unit_interval(bad_alpha: Decimal) -> None:
    with pytest.raises(TrialValidationError):
        _registration(alpha_budget=bad_alpha)


def test_registration_refuses_lockbox_overlapping_training_window() -> None:
    with pytest.raises(TrialValidationError):
        _registration(
            training_window=DateWindow(date(2024, 1, 1), date(2026, 3, 1)),
            lockbox_window=DateWindow(date(2026, 1, 1), date(2026, 6, 30)),
        )


def test_registration_refuses_lockbox_overlapping_validation_window() -> None:
    with pytest.raises(TrialValidationError):
        _registration(
            validation_window=DateWindow(date(2025, 7, 1), date(2026, 2, 1)),
            lockbox_window=DateWindow(date(2026, 1, 1), date(2026, 6, 30)),
        )


def test_registration_allows_adjacent_non_overlapping_lockbox() -> None:
    _registration(
        validation_window=DateWindow(date(2025, 7, 1), date(2025, 12, 31)),
        lockbox_window=DateWindow(date(2026, 1, 1), date(2026, 6, 30)),
    )


# --- TrialDecision closed enum ----------------------------------------------------------


def test_trial_decision_is_exactly_five_valued() -> None:
    assert {d.name for d in TrialDecision} == {
        "PASS",
        "CONTINUE",
        "FAIL_HARM",
        "FAIL_FUTILITY",
        "ABANDONED",
    }


@pytest.mark.parametrize(
    "shared", [TrialDecision.PASS, TrialDecision.CONTINUE, TrialDecision.FAIL_HARM, TrialDecision.FAIL_FUTILITY]
)
def test_shared_decision_values_match_gate_outcome(shared: TrialDecision) -> None:
    assert shared.value == GateOutcome[shared.name].value


def test_abandoned_decision_has_no_gate_outcome_counterpart() -> None:
    with pytest.raises(KeyError):
        GateOutcome["ABANDONED"]


# --- TrialCompletion field validation ----------------------------------------------------


def test_completion_requires_result_unless_abandoned() -> None:
    registration = _registration()
    with pytest.raises(TrialValidationError):
        _completion(
            registration.experiment_id,
            registration.content_digest(),
            decision=TrialDecision.CONTINUE,
            result=None,
        )


def test_completion_requires_confidence_interval_unless_abandoned() -> None:
    registration = _registration()
    with pytest.raises(TrialValidationError):
        _completion(
            registration.experiment_id,
            registration.content_digest(),
            decision=TrialDecision.FAIL_FUTILITY,
            confidence_interval=None,
        )


def test_abandoned_completion_must_not_carry_a_result() -> None:
    registration = _registration()
    with pytest.raises(TrialValidationError):
        _completion(
            registration.experiment_id,
            registration.content_digest(),
            decision=TrialDecision.ABANDONED,
        )


def test_abandoned_completion_with_no_result_or_ci_is_valid() -> None:
    registration = _registration()
    _completion(
        registration.experiment_id,
        registration.content_digest(),
        decision=TrialDecision.ABANDONED,
        result=None,
        confidence_interval=None,
    )


def test_completion_refuses_confidence_interval_lower_above_upper() -> None:
    registration = _registration()
    with pytest.raises(TrialValidationError):
        _completion(
            registration.experiment_id,
            registration.content_digest(),
            confidence_interval=(Decimal("0.5"), Decimal("0.1")),
        )


def test_completion_refuses_malformed_registration_digest() -> None:
    with pytest.raises(TrialValidationError):
        _completion("exp-2026-041", "not-a-digest")


def test_completion_refuses_non_trial_decision_value() -> None:
    registration = _registration()
    with pytest.raises(TrialValidationError):
        TrialCompletion(
            experiment_id=registration.experiment_id,
            registration_digest=registration.content_digest(),
            result=Decimal("0.01"),
            confidence_interval=(Decimal("0"), Decimal("0.02")),
            decision="CONTINUE",  # type: ignore[arg-type]
            attestation=Attestation(reviewer="a.reviewer", attested_at_utc=_clock().wall_utc),
            completed_at=_clock(),
        )


# --- TrialLedger: append-only refusals ---------------------------------------------------


def test_register_then_lookup_round_trips() -> None:
    ledger = TrialLedger()
    registration = _registration()
    ledger.register(registration)
    assert ledger.registration_for("exp-2026-041") is registration
    assert ledger.experiment_ids() == ("exp-2026-041",)


def test_register_refuses_duplicate_experiment_id() -> None:
    ledger = TrialLedger()
    ledger.register(_registration("exp-a", number_of_prior_trials=0))
    with pytest.raises(DuplicateExperimentError):
        ledger.register(_registration("exp-a", number_of_prior_trials=1))


def test_register_refuses_wrong_prior_trial_count_on_first_registration() -> None:
    ledger = TrialLedger()
    with pytest.raises(PriorTrialCountError):
        ledger.register(_registration("exp-a", number_of_prior_trials=1))


def test_register_refuses_wrong_prior_trial_count_on_later_registration() -> None:
    ledger = TrialLedger()
    ledger.register(_registration("exp-a", number_of_prior_trials=0))
    with pytest.raises(PriorTrialCountError):
        ledger.register(_registration("exp-b", number_of_prior_trials=0))
    with pytest.raises(PriorTrialCountError):
        ledger.register(_registration("exp-b", number_of_prior_trials=2))
    ledger.register(_registration("exp-b", number_of_prior_trials=1))
    assert ledger.experiment_ids() == ("exp-a", "exp-b")


def test_prior_trial_count_reflects_registrations_so_far() -> None:
    ledger = TrialLedger()
    assert ledger.prior_trial_count() == 0
    ledger.register(_registration("exp-a", number_of_prior_trials=0))
    assert ledger.prior_trial_count() == 1
    ledger.register(_registration("exp-b", number_of_prior_trials=1))
    assert ledger.prior_trial_count() == 2


def test_registration_for_unknown_experiment_raises() -> None:
    ledger = TrialLedger()
    with pytest.raises(UnknownExperimentError):
        ledger.registration_for("nope")


def test_complete_refuses_unknown_experiment_id() -> None:
    ledger = TrialLedger()
    with pytest.raises(UnknownExperimentError):
        ledger.complete(_completion("nope", "sha256:" + "0" * 64))


def test_complete_refuses_double_completion() -> None:
    ledger = TrialLedger()
    registration = _registration("exp-a", number_of_prior_trials=0)
    ledger.register(registration)
    ledger.complete(_completion("exp-a", registration.content_digest()))
    with pytest.raises(DoubleCompletionError):
        ledger.complete(_completion("exp-a", registration.content_digest()))


def test_complete_refuses_tampered_registration_digest() -> None:
    ledger = TrialLedger()
    registration = _registration("exp-a", number_of_prior_trials=0)
    ledger.register(registration)
    wrong_digest = "sha256:" + ("f" * 64)
    with pytest.raises(RegistrationDigestMismatchError):
        ledger.complete(_completion("exp-a", wrong_digest))


def test_completion_for_returns_none_before_completion() -> None:
    ledger = TrialLedger()
    registration = _registration("exp-a", number_of_prior_trials=0)
    ledger.register(registration)
    assert ledger.completion_for("exp-a") is None
    ledger.complete(_completion("exp-a", registration.content_digest()))
    assert ledger.completion_for("exp-a") is not None


def test_completion_for_unknown_experiment_raises() -> None:
    ledger = TrialLedger()
    with pytest.raises(UnknownExperimentError):
        ledger.completion_for("nope")


def test_ledger_has_no_update_or_delete_api_surface() -> None:
    ledger = TrialLedger()
    public_methods = {name for name in dir(ledger) if not name.startswith("_")}
    assert public_methods == {
        "register",
        "complete",
        "prior_trial_count",
        "registration_for",
        "completion_for",
        "experiment_ids",
    }
    forbidden_substrings = ("update", "delete", "remove", "modify", "edit", "mutate", "overwrite", "set_")
    for name in public_methods:
        for forbidden in forbidden_substrings:
            assert forbidden not in name.lower(), f"{name!r} looks like a mutation escape hatch"


# --- gate-evaluator round trip (the "gate evaluation MUST read it" half) ----------------


_GATE_ID = "GATE-E"
_EVIDENCE_GATE = GateDefinition(
    gate_id=_GATE_ID,
    kind=GateKind.EVIDENCE,
    decision="anytime_valid_bounds_v1",
    items=(),
)
_SPEC = GateSpec(version="gates-v1", digest="sha256:" + "9" * 64, gates=(_EVIDENCE_GATE,))
_FRESH_FACTS = FactsRegistry(facts=(), digest="sha256:" + "8" * 64)
_GOOD_EVIDENCE = Evidence(
    lower_bound=Decimal("0.007"), upper_bound=Decimal("0.020"), n=2100, loss_budget_breached=False
)


def _prereg_from_ledger(ledger: TrialLedger, experiment_id: str) -> PreRegistration:
    registration = ledger.registration_for(experiment_id)
    return PreRegistration(
        minimum_economic_effect=registration.minimum_economic_effect,
        harm_threshold=Decimal("-0.010"),
        alpha_budget=alpha_budget_for_evaluation(ledger, experiment_id),
        confidence_level=Decimal("0.99"),
        max_n=4000,
        number_of_prior_trials=prior_trials_for_evaluation(ledger, experiment_id),
        primary_endpoint=registration.primary_endpoint,
        stopping_rule=registration.stopping_rule,
    )


def _evaluate_experiment(ledger: TrialLedger, experiment_id: str) -> GateOutcome:
    prereg = _prereg_from_ledger(ledger, experiment_id)
    record = ExperimentRecord(
        experiment_id=experiment_id,
        gate_id=_GATE_ID,
        preregistration=prereg,
        evidence=_GOOD_EVIDENCE,
    )
    result = evaluate(
        spec=_SPEC,
        experiment=record,
        facts=_FRESH_FACTS,
        data_manifest="sha256:" + "a" * 64,
        model_manifest="sha256:" + "b" * 64,
        as_of=date(2026, 7, 16),
    )
    return result.outcome


def test_prior_trials_for_evaluation_round_trips_into_pass() -> None:
    # (1 - 0.99) * (4 + 1) = 0.05 exactly at the alpha_budget boundary -> PASS.
    ledger = TrialLedger()
    for i in range(4):
        ledger.register(_registration(f"exp-{i}", number_of_prior_trials=i))
    ledger.register(_registration("exp-4", number_of_prior_trials=4, alpha_budget=Decimal("0.05")))
    assert prior_trials_for_evaluation(ledger, "exp-4") == 4
    assert alpha_budget_for_evaluation(ledger, "exp-4") == Decimal("0.05")
    assert _evaluate_experiment(ledger, "exp-4") is GateOutcome.PASS


def test_ledger_reported_multiplicity_blocks_pass_when_too_many_prior_trials() -> None:
    # (1 - 0.99) * (5 + 1) = 0.06 > 0.05 -> multiplicity is exceeded -> CONTINUE, never PASS.
    # This proves the LEDGER's own count (not a caller-invented number) is what feeds the
    # evaluator: the same _evaluate_experiment/_prereg_from_ledger plumbing that produced
    # PASS at 4 prior trials above produces CONTINUE once the ledger has registered a 5th.
    ledger = TrialLedger()
    for i in range(5):
        ledger.register(_registration(f"exp-{i}", number_of_prior_trials=i))
    ledger.register(_registration("exp-5", number_of_prior_trials=5, alpha_budget=Decimal("0.05")))
    assert prior_trials_for_evaluation(ledger, "exp-5") == 5
    assert _evaluate_experiment(ledger, "exp-5") is GateOutcome.CONTINUE


# --- completion cannot be backdated before its registration (lead addition, 2026-07-16) ------


def test_completion_backdated_before_registration_is_refused() -> None:
    ledger = TrialLedger()
    registration = _registration("exp-1", number_of_prior_trials=0)
    ledger.register(registration)
    backdated = TrialCompletion(
        experiment_id="exp-1",
        registration_digest=registration.content_digest(),
        result=Decimal("0.010"),
        confidence_interval=(Decimal("0.001"), Decimal("0.020")),
        decision=TrialDecision.CONTINUE,
        attestation=Attestation(reviewer="a.reviewer", attested_at_utc=_clock(13).wall_utc),
        completed_at=_clock(hour=1),
    )
    with pytest.raises(TrialValidationError):
        ledger.complete(backdated)
