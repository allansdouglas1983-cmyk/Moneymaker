"""SPEC-037 properties: digest determinism, fair-odds exactness, chain invariants."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from governance.output_rights import EligibilityResult, EligibilityStatus, EligibilityVocabulary
from l4_pricing.probability_outputs import (
    CombinedProbability,
    RaceProbabilityOutputs,
    RunnerProbabilities,
)
from l8_evidence.prediction_snapshots import (
    DualClockTimestamp,
    MarketStateSnapshot,
    PredictionSnapshot,
    SnapshotValidationError,
    UncertaintySummary,
    UpdateReason,
    VintageType,
    build_active_runner_set_hash,
    build_fair_odds,
)

pytestmark = pytest.mark.spec("SPEC-037")

_MODEL_DIGEST = "sha256:" + "1" * 64
_FEATURE_DIGEST = "sha256:" + "2" * 64
_SOURCE_DIGEST = "sha256:" + "3" * 64
_REGISTRY_VERSION = "sha256:" + "4" * 64

_PROB_2 = st.decimals(min_value=Decimal("0.05"), max_value=Decimal("0.95"), places=2)


def _race_for(p1: Decimal) -> RaceProbabilityOutputs:
    p2 = Decimal(1) - p1
    return RaceProbabilityOutputs(
        race_id="race-1",
        runners=(
            RunnerProbabilities(
                runner_id=1,
                p_combined=CombinedProbability(probability=p1, model_digest=_MODEL_DIGEST),
                p_fundamental_missing_reason="not modelled in this test",
                p_market_info_missing_reason="not modelled in this test",
            ),
            RunnerProbabilities(
                runner_id=2,
                p_combined=CombinedProbability(probability=p2, model_digest=_MODEL_DIGEST),
                p_fundamental_missing_reason="not modelled in this test",
                p_market_info_missing_reason="not modelled in this test",
            ),
        ),
    )


def _snapshot_for(p1: Decimal, *, matched: Decimal = Decimal("1000.00")) -> PredictionSnapshot:
    race = _race_for(p1)
    return PredictionSnapshot(
        prediction_id="pred-1",
        race_id="race-1",
        market_id="market-1",
        active_runner_set_hash=build_active_runner_set_hash([r.runner_id for r in race.runners]),
        generated_at=DualClockTimestamp(
            wall_utc=datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc), monotonic_ns=1
        ),
        decision_horizon="T-60m",
        market_state=MarketStateSnapshot(
            market_status="OPEN", in_play=False, number_of_active_runners=2, total_matched=matched
        ),
        probabilities=race,
        fair_odds=build_fair_odds(race),
        uncertainty=UncertaintySummary(
            method="time_fold_ensemble_v1", lower=Decimal("0.1"), central=Decimal("0.2"), upper=Decimal("0.3")
        ),
        model_lineage_digest=_MODEL_DIGEST,
        feature_lineage_digest=_FEATURE_DIGEST,
        source_lineage_digest=_SOURCE_DIGEST,
        publication_eligibility=EligibilityResult(
            status=EligibilityStatus.ELIGIBLE, reasons=(), rights_registry_version=_REGISTRY_VERSION, vocabulary=EligibilityVocabulary.PUBLICATION
    ),
        schema_version="prediction-snapshot-v1",
        forecast_vintage_id="vintage-1",
        vintage_type=VintageType.INITIAL,
        supersedes_prediction_id=None,
        update_reason=None,
        available_to_consumer_at_utc=datetime(2026, 7, 16, 12, 0, 5, tzinfo=timezone.utc),
    )


@given(p1=_PROB_2)
@settings(max_examples=50)
def test_content_digest_is_deterministic_for_identical_inputs(p1: Decimal) -> None:
    a = _snapshot_for(p1)
    b = _snapshot_for(p1)
    assert a.content_digest() == b.content_digest()


@given(p1=_PROB_2, matched=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100000"), places=2))
@settings(max_examples=50)
def test_content_digest_changes_when_market_state_changes(p1: Decimal, matched: Decimal) -> None:
    base = _snapshot_for(p1)
    if matched == base.market_state.total_matched:
        matched = matched + Decimal("1.00")
    changed = _snapshot_for(p1, matched=matched)
    assert base.content_digest() != changed.content_digest()


@given(p1=_PROB_2)
@settings(max_examples=50)
def test_fair_odds_round_trips_exactly_via_decimal_inversion(p1: Decimal) -> None:
    race = _race_for(p1)
    odds = build_fair_odds(race)
    expected = (Decimal(1) / p1).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
    assert odds[1] == expected


@given(p1=_PROB_2)
@settings(max_examples=50)
def test_fair_odds_are_always_greater_than_one(p1: Decimal) -> None:
    race = _race_for(p1)
    odds = build_fair_odds(race)
    for value in odds.values():
        assert value > Decimal(1)


@given(runner_ids=st.lists(st.integers(min_value=1, max_value=1000), min_size=1, max_size=20, unique=True))
@settings(max_examples=50)
def test_active_runner_set_hash_is_order_independent(runner_ids: list[int]) -> None:
    shuffled = list(reversed(runner_ids))
    assert build_active_runner_set_hash(runner_ids) == build_active_runner_set_hash(shuffled)


@given(runner_ids=st.lists(st.integers(min_value=1, max_value=1000), min_size=2, max_size=20, unique=True))
@settings(max_examples=50)
def test_active_runner_set_hash_changes_when_a_runner_is_removed(runner_ids: list[int]) -> None:
    full_hash = build_active_runner_set_hash(runner_ids)
    reduced_hash = build_active_runner_set_hash(runner_ids[:-1])
    assert full_hash != reduced_hash


@given(
    vintage_type=st.sampled_from(list(VintageType)),
    reason=st.sampled_from(list(UpdateReason)),
)
@settings(max_examples=50)
def test_vintage_reason_matrix_only_accepts_the_declared_mapping(
    vintage_type: VintageType, reason: UpdateReason
) -> None:
    race = _race_for(Decimal("0.6"))
    kwargs = dict(
        prediction_id="pred-2",
        race_id="race-1",
        market_id="market-1",
        active_runner_set_hash=build_active_runner_set_hash([r.runner_id for r in race.runners]),
        generated_at=DualClockTimestamp(
            wall_utc=datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc), monotonic_ns=1
        ),
        decision_horizon="T-60m",
        market_state=MarketStateSnapshot(
            market_status="OPEN", in_play=False, number_of_active_runners=2, total_matched=Decimal("1.00")
        ),
        probabilities=race,
        fair_odds=build_fair_odds(race),
        uncertainty=UncertaintySummary(method="m", lower=None, central=Decimal("0.5"), upper=None),
        model_lineage_digest=_MODEL_DIGEST,
        feature_lineage_digest=_FEATURE_DIGEST,
        source_lineage_digest=_SOURCE_DIGEST,
        publication_eligibility=EligibilityResult(
            status=EligibilityStatus.ELIGIBLE, reasons=(), rights_registry_version=_REGISTRY_VERSION, vocabulary=EligibilityVocabulary.PUBLICATION
    ),
        schema_version="prediction-snapshot-v1",
        forecast_vintage_id="vintage-1",
        vintage_type=vintage_type,
        supersedes_prediction_id=None if vintage_type is VintageType.INITIAL else "pred-1",
        update_reason=None if vintage_type is VintageType.INITIAL else reason,
        available_to_consumer_at_utc=datetime(2026, 7, 16, 12, 0, 5, tzinfo=timezone.utc),
    )
    if vintage_type is VintageType.INITIAL:
        PredictionSnapshot(**kwargs)  # type: ignore[arg-type]
        return
    allowed = {
        # SELECTION_WITHDRAWN added by the governed A6 enum extension (audit F-10,
        # founder-approved 2026-07-17): the generic pre-off withdrawal member joins
        # racing's NON_RUNNER in the UPDATED vintage; every other cell is unchanged.
        VintageType.UPDATED: {
            UpdateReason.NON_RUNNER,
            UpdateReason.SELECTION_WITHDRAWN,
            UpdateReason.MARKET_STATE_REFRESH,
            UpdateReason.MODEL_REVISION,
        },
        VintageType.FINAL_APPROVED_HORIZON: {UpdateReason.HORIZON_FINALISED},
        VintageType.CORRECTION: {UpdateReason.DATA_CORRECTION},
    }[vintage_type]
    if reason in allowed:
        PredictionSnapshot(**kwargs)  # type: ignore[arg-type]
    else:
        with pytest.raises(SnapshotValidationError):
            PredictionSnapshot(**kwargs)  # type: ignore[arg-type]
