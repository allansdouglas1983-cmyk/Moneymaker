"""SPEC-091 properties: digest determinism, monotone prior-trial counts, append-only
registration-order invariance of digests (appending later registrations must never
retroactively change an earlier registration's content digest)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l8_evidence.prediction_snapshots import DualClockTimestamp
from l8_evidence.trial_ledger import DateWindow, TrialLedger, TrialRegistration

pytestmark = pytest.mark.spec("SPEC-091")

_FEATURE_HASH = "sha256:" + "1" * 64
_MODEL_HASH = "sha256:" + "2" * 64
_POLICY_HASH = "sha256:" + "3" * 64

_ALPHA = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.20"), places=2)
_MIN_EFFECT = st.decimals(min_value=Decimal("0.001"), max_value=Decimal("0.050"), places=3)
_HYPOTHESIS_TEXT = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=30
)


def _registration(
    experiment_id: str,
    number_of_prior_trials: int,
    *,
    hypothesis: str = "combined model beats the market price on the race-level log score",
    minimum_economic_effect: Decimal = Decimal("0.005"),
    alpha_budget: Decimal = Decimal("0.05"),
) -> TrialRegistration:
    return TrialRegistration(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        decision_unit="race",
        primary_endpoint="paired race-level log-score difference",
        secondary_endpoints=("race-level Brier",),
        minimum_economic_effect=minimum_economic_effect,
        training_window=DateWindow(date(2024, 1, 1), date(2025, 6, 30)),
        validation_window=DateWindow(date(2025, 7, 1), date(2025, 12, 31)),
        lockbox_window=DateWindow(date(2026, 1, 1), date(2026, 6, 30)),
        exclusions=(),
        feature_set_hash=_FEATURE_HASH,
        model_hash=_MODEL_HASH,
        execution_policy_hash=_POLICY_HASH,
        number_of_prior_trials=number_of_prior_trials,
        stopping_rule="anytime-valid confidence sequence at the declared level",
        alpha_budget=alpha_budget,
        recorded_at=DualClockTimestamp(
            wall_utc=datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc), monotonic_ns=1
        ),
    )


@given(hypothesis=_HYPOTHESIS_TEXT, effect=_MIN_EFFECT, alpha=_ALPHA)
@settings(max_examples=50)
def test_content_digest_is_deterministic_for_identical_field_values(
    hypothesis: str, effect: Decimal, alpha: Decimal
) -> None:
    a = _registration("exp-x", 0, hypothesis=hypothesis, minimum_economic_effect=effect, alpha_budget=alpha)
    b = _registration("exp-x", 0, hypothesis=hypothesis, minimum_economic_effect=effect, alpha_budget=alpha)
    assert a.content_digest() == b.content_digest()


@given(hypothesis=_HYPOTHESIS_TEXT, alpha=_ALPHA)
@settings(max_examples=50)
def test_content_digest_changes_when_alpha_budget_changes(hypothesis: str, alpha: Decimal) -> None:
    base = _registration("exp-x", 0, hypothesis=hypothesis, alpha_budget=alpha)
    bumped = alpha + Decimal("0.001") if alpha < Decimal("0.199") else alpha - Decimal("0.001")
    changed = _registration("exp-x", 0, hypothesis=hypothesis, alpha_budget=bumped)
    assert base.content_digest() != changed.content_digest()


@given(n=st.integers(min_value=1, max_value=12))
@settings(max_examples=25)
def test_prior_trial_count_is_strictly_monotone_by_registration_order(n: int) -> None:
    ledger = TrialLedger()
    counts = []
    for i in range(n):
        before = ledger.prior_trial_count()
        ledger.register(_registration(f"exp-{i}", i))
        after = ledger.prior_trial_count()
        counts.append((before, after))
    for before, after in counts:
        assert after == before + 1
    # Registration order equals the strictly increasing sequence 0, 1, ..., n-1.
    assert [ledger.registration_for(f"exp-{i}").number_of_prior_trials for i in range(n)] == list(range(n))


@given(n=st.integers(min_value=1, max_value=8), extra=st.integers(min_value=1, max_value=8))
@settings(max_examples=25)
def test_appending_later_registrations_never_changes_an_earlier_digest(n: int, extra: int) -> None:
    ledger = TrialLedger()
    for i in range(n):
        ledger.register(_registration(f"exp-{i}", i))
    digests_before = [ledger.registration_for(f"exp-{i}").content_digest() for i in range(n)]
    for j in range(n, n + extra):
        ledger.register(_registration(f"exp-{j}", j))
    digests_after = [ledger.registration_for(f"exp-{i}").content_digest() for i in range(n)]
    assert digests_before == digests_after
