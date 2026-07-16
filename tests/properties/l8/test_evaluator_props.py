"""SPEC-093 properties: insufficient evidence never PASSes; harm dominates; stale facts
defeat any efficacy; the verdict is never a boolean; evaluation is deterministic."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l8_evidence.gates.evaluator import evaluate
from l8_evidence.gates.experiment import Evidence, ExperimentRecord, PreRegistration
from l8_evidence.gates.facts import Fact, FactsRegistry
from l8_evidence.gates.outcomes import GateOutcome
from l8_evidence.gates.spec import GateDefinition, GateItem, GateKind, GateSpec

pytestmark = pytest.mark.spec("SPEC-093")

_AS_OF = date(2026, 7, 16)
_DATA = "sha256:" + "1" * 64
_MODEL = "sha256:" + "2" * 64

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

_SPEC = GateSpec(version="gates-v1", digest="sha256:" + "3" * 64, gates=(_EVIDENCE_GATE, _PAYBACK_GATE))
_FRESH_FACTS = FactsRegistry(facts=(), digest="sha256:" + "4" * 64)

_D4 = st.decimals(min_value=Decimal("-1"), max_value=Decimal("1"), places=4, allow_nan=False, allow_infinity=False)


def _prereg(trials: int = 0, alpha: Decimal = Decimal("0.05"), max_n: int = 4000) -> PreRegistration:
    return PreRegistration(
        minimum_economic_effect=Decimal("0.005"),
        harm_threshold=Decimal("-0.010"),
        alpha_budget=alpha,
        confidence_level=Decimal("0.99"),
        max_n=max_n,
        number_of_prior_trials=trials,
        primary_endpoint="paired race-level log-score difference",
        stopping_rule="anytime-valid confidence sequence",
    )


def _record(
    evidence: Evidence | None,
    prereg: PreRegistration,
    precondition: bool | None = True,
) -> ExperimentRecord:
    attestations = {} if precondition is None else {"precondition": precondition}
    return ExperimentRecord(
        experiment_id="exp-e",
        gate_id="GATE-E",
        preregistration=prereg,
        evidence=evidence,
        attestations=attestations,
    )


def _run(record: ExperimentRecord, facts: FactsRegistry = _FRESH_FACTS) -> GateOutcome:
    return evaluate(
        spec=_SPEC,
        experiment=record,
        facts=facts,
        data_manifest=_DATA,
        model_manifest=_MODEL,
        as_of=_AS_OF,
    ).outcome


@settings(max_examples=300)
@given(lower=_D4, spread=_D4.filter(lambda d: d >= 0), n=st.integers(min_value=0, max_value=10_000))
def test_insufficient_evidence_never_passes(lower: Decimal, spread: Decimal, n: int) -> None:
    """§12.4: whenever the lower bound has not crossed the efficacy boundary, never PASS."""
    prereg = _prereg()
    evidence = Evidence(lower_bound=lower, upper_bound=lower + spread, n=n, loss_budget_breached=False)
    outcome = _run(_record(evidence, prereg))
    if lower <= prereg.minimum_economic_effect:
        assert outcome is not GateOutcome.PASS


@settings(max_examples=300)
@given(lower=_D4, spread=_D4.filter(lambda d: d >= 0), n=st.integers(min_value=0, max_value=10_000))
def test_verdict_is_always_four_valued_and_never_truth_testable(
    lower: Decimal, spread: Decimal, n: int
) -> None:
    evidence = Evidence(lower_bound=lower, upper_bound=lower + spread, n=n, loss_budget_breached=False)
    outcome = _run(_record(evidence, _prereg()))
    assert outcome in set(GateOutcome)
    with pytest.raises(TypeError):
        bool(outcome)


@settings(max_examples=200)
@given(lower=_D4, spread=_D4.filter(lambda d: d >= 0), n=st.integers(min_value=0, max_value=10_000))
def test_any_stale_fact_defeats_any_evidence(lower: Decimal, spread: Decimal, n: int) -> None:
    stale = FactsRegistry(
        facts=(Fact(fact_id="STALE", populated=True, recheck_by=date(2026, 1, 1), used_by=()),),
        digest="sha256:" + "5" * 64,
    )
    evidence = Evidence(lower_bound=lower, upper_bound=lower + spread, n=n, loss_budget_breached=False)
    assert _run(_record(evidence, _prereg()), facts=stale) is GateOutcome.FAIL_HARM


@settings(max_examples=200)
@given(
    lower=_D4,
    spread=_D4.filter(lambda d: d >= 0),
    n=st.integers(min_value=0, max_value=10_000),
    precondition=st.sampled_from([True, False, None]),
)
def test_loss_budget_breach_always_fails_harm(
    lower: Decimal, spread: Decimal, n: int, precondition: bool | None
) -> None:
    """Harm dominance: a breached loss budget is FAIL_HARM whatever else is going on."""
    evidence = Evidence(lower_bound=lower, upper_bound=lower + spread, n=n, loss_budget_breached=True)
    assert _run(_record(evidence, _prereg(), precondition=precondition)) is GateOutcome.FAIL_HARM


@settings(max_examples=200)
@given(lower=_D4, spread=_D4.filter(lambda d: d >= 0), n=st.integers(min_value=0, max_value=10_000))
def test_false_harm_precondition_always_fails_harm(lower: Decimal, spread: Decimal, n: int) -> None:
    evidence = Evidence(lower_bound=lower, upper_bound=lower + spread, n=n, loss_budget_breached=False)
    assert _run(_record(evidence, _prereg(), precondition=False)) is GateOutcome.FAIL_HARM


@settings(max_examples=200)
@given(
    trials=st.integers(min_value=0, max_value=50),
    fewer_by=st.integers(min_value=1, max_value=50),
    lower=_D4,
    spread=_D4.filter(lambda d: d >= 0),
)
def test_trial_count_downward_closure(
    trials: int, fewer_by: int, lower: Decimal, spread: Decimal
) -> None:
    """If the gate PASSes after t prior trials, it must PASS after fewer prior trials too."""
    evidence = Evidence(lower_bound=lower, upper_bound=lower + spread, n=100, loss_budget_breached=False)
    at_t = _run(_record(evidence, _prereg(trials=trials)))
    at_fewer = _run(_record(evidence, _prereg(trials=max(0, trials - fewer_by))))
    if at_t is GateOutcome.PASS:
        assert at_fewer is GateOutcome.PASS


@settings(max_examples=200)
@given(lower=_D4, spread=_D4.filter(lambda d: d >= 0), n=st.integers(min_value=0, max_value=10_000))
def test_evaluation_is_deterministic(lower: Decimal, spread: Decimal, n: int) -> None:
    evidence = Evidence(lower_bound=lower, upper_bound=lower + spread, n=n, loss_budget_breached=False)
    record = _record(evidence, _prereg())
    first = evaluate(
        spec=_SPEC, experiment=record, facts=_FRESH_FACTS,
        data_manifest=_DATA, model_manifest=_MODEL, as_of=_AS_OF,
    )
    second = evaluate(
        spec=_SPEC, experiment=record, facts=_FRESH_FACTS,
        data_manifest=_DATA, model_manifest=_MODEL, as_of=_AS_OF,
    )
    assert first.canonical_json() == second.canonical_json()


_MONEY = st.decimals(min_value=Decimal("0"), max_value=Decimal("10000"), places=2, allow_nan=False, allow_infinity=False)


def _payback_record(c_recurring: Decimal, c_fixed: Decimal, roi_lower: Decimal) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id="exp-p",
        gate_id="GATE-P",
        computed_inputs={
            "payback_v1": {
                "n_eligible_per_year": 2500,
                "r_select": Decimal("0.10"),
                "r_fill": Decimal("0.80"),
                "mean_stake": Decimal("2.00"),
                "roi_lower": roi_lower,
                "c_recurring_per_year": c_recurring,
                "c_fixed": c_fixed,
                "max_payback_years": Decimal("2"),
            }
        },
    )


@settings(max_examples=200)
@given(
    c1=_MONEY,
    extra=_MONEY,
    c_fixed=_MONEY,
    roi=st.decimals(min_value=Decimal("0"), max_value=Decimal("0.1"), places=4, allow_nan=False, allow_infinity=False),
)
def test_increasing_recurring_costs_never_shortens_payback(
    c1: Decimal, extra: Decimal, c_fixed: Decimal, roi: Decimal
) -> None:
    cheap = _run(_payback_record(c1, c_fixed, roi))
    dear = _run(_payback_record(c1 + extra, c_fixed, roi))
    if dear is GateOutcome.PASS:
        assert cheap is GateOutcome.PASS


@settings(max_examples=200)
@given(
    c_recurring=_MONEY,
    c1=_MONEY,
    extra=_MONEY,
    roi=st.decimals(min_value=Decimal("0"), max_value=Decimal("0.1"), places=4, allow_nan=False, allow_infinity=False),
)
def test_increasing_fixed_costs_never_shortens_payback(
    c_recurring: Decimal, c1: Decimal, extra: Decimal, roi: Decimal
) -> None:
    cheap = _run(_payback_record(c_recurring, c1, roi))
    dear = _run(_payback_record(c_recurring, c1 + extra, roi))
    if dear is GateOutcome.PASS:
        assert cheap is GateOutcome.PASS
