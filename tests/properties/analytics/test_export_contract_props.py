"""SPEC-045: exportable prediction contract — Hypothesis property tests.

RED: analytics_contracts does not exist yet in the repository. This test module fails at
collection time with a ModuleNotFoundError until the SPEC-045 slice lands
analytics_contracts/export_contract.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from governance.output_rights import EligibilityResult, EligibilityStatus, EligibilityVocabulary
from l4_pricing.probability_outputs import (
    CombinedProbability,
    FundamentalProbability,
    MarketProbability,
    RaceProbabilityOutputs,
    RunnerProbabilities,
)
from l8_evidence.explanation_inputs import AttributionUnavailable
from l8_evidence.prediction_snapshots import (
    DualClockTimestamp,
    MarketStateSnapshot,
    PredictionSnapshot,
    UncertaintySummary,
    VintageType,
    build_active_runner_set_hash,
    build_fair_odds,
)

from analytics_contracts.export_contract import (
    ForecastAvailability,
    PublicationEligibility,
    RecommendationStatus,
    build_export,
    build_unavailable,
    display_decimal,
    map_eligibility_to_publication_status,
)

pytestmark = pytest.mark.spec("SPEC-045")

_MODEL_DIGEST = "sha256:" + "1" * 64
_FEATURE_DIGEST = "sha256:" + "2" * 64
_SOURCE_DIGEST = "sha256:" + "3" * 64
_REGISTRY_VERSION = "sha256:" + "4" * 64


def _race(p1: Decimal, p2: Decimal) -> RaceProbabilityOutputs:
    return RaceProbabilityOutputs(
        race_id="race-1",
        runners=(
            RunnerProbabilities(
                runner_id=1,
                p_fundamental=FundamentalProbability(probability=p1, model_digest=_MODEL_DIGEST),
                p_market_info=MarketProbability(probability=p1, price_version="info-price-v1"),
                p_combined=CombinedProbability(probability=p1, model_digest=_MODEL_DIGEST),
            ),
            RunnerProbabilities(
                runner_id=2,
                p_fundamental=FundamentalProbability(probability=p2, model_digest=_MODEL_DIGEST),
                p_market_info=MarketProbability(probability=p2, price_version="info-price-v1"),
                p_combined=CombinedProbability(probability=p2, model_digest=_MODEL_DIGEST),
            ),
        ),
    )


def _snapshot(p1: Decimal, p2: Decimal, prediction_id: str = "pred-1") -> PredictionSnapshot:
    race = _race(p1, p2)
    return PredictionSnapshot(
        prediction_id=prediction_id,
        race_id="race-1",
        market_id="market-1",
        active_runner_set_hash=build_active_runner_set_hash([r.runner_id for r in race.runners]),
        generated_at=DualClockTimestamp(
            wall_utc=datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc), monotonic_ns=1000
        ),
        decision_horizon="T-60m",
        market_state=MarketStateSnapshot(
            market_status="OPEN",
            in_play=False,
            number_of_active_runners=2,
            total_matched=Decimal("1000.00"),
        ),
        probabilities=race,
        fair_odds=build_fair_odds(race),
        uncertainty=UncertaintySummary(method="time_fold_ensemble_v1", lower=None, central=None, upper=None),
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


def _unavailable_explanation(prediction_id: str) -> AttributionUnavailable:
    return AttributionUnavailable(prediction_id=prediction_id, reason="no method approved")


_split = st.floats(min_value=0.05, max_value=0.95, allow_nan=False, allow_infinity=False)


@given(split=_split, gate=st.booleans())
@settings(max_examples=50)
def test_build_export_digest_is_deterministic(split: float, gate: bool) -> None:
    p1 = Decimal(str(round(split, 6)))
    p2 = Decimal(1) - p1
    snapshot = _snapshot(p1, p2)
    eligibility = EligibilityResult(
        status=EligibilityStatus.ELIGIBLE, reasons=(), rights_registry_version=_REGISTRY_VERSION, vocabulary=EligibilityVocabulary.PUBLICATION
    )
    export_a = build_export(
        snapshot, eligibility, gate_p1_activated=gate, explanations=_unavailable_explanation("pred-1")
    )
    export_b = build_export(
        snapshot, eligibility, gate_p1_activated=gate, explanations=_unavailable_explanation("pred-1")
    )
    assert export_a.content_digest() == export_b.content_digest()


@given(split=_split)
@settings(max_examples=50)
def test_build_export_digest_changes_when_a_probability_changes(split: float) -> None:
    p1 = Decimal(str(round(split, 6)))
    p2 = Decimal(1) - p1
    snapshot_a = _snapshot(p1, p2)
    # Perturb by swapping toward a different split (still valid, still sums to 1).
    other_split = min(0.95, max(0.05, split + 0.02)) if split < 0.9 else split - 0.02
    q1 = Decimal(str(round(other_split, 6)))
    q2 = Decimal(1) - q1
    snapshot_b = _snapshot(q1, q2)
    eligibility = EligibilityResult(
        status=EligibilityStatus.ELIGIBLE, reasons=(), rights_registry_version=_REGISTRY_VERSION, vocabulary=EligibilityVocabulary.PUBLICATION
    )
    export_a = build_export(
        snapshot_a, eligibility, gate_p1_activated=True, explanations=_unavailable_explanation("pred-1")
    )
    export_b = build_export(
        snapshot_b, eligibility, gate_p1_activated=True, explanations=_unavailable_explanation("pred-1")
    )
    if snapshot_a.content_digest() != snapshot_b.content_digest():
        assert export_a.content_digest() != export_b.content_digest()


@given(
    status=st.sampled_from(
        [
            EligibilityStatus.ELIGIBLE,
            EligibilityStatus.INELIGIBLE_LICENSING,
            EligibilityStatus.INELIGIBLE_STALE_RIGHTS,
        ]
    ),
    gate=st.booleans(),
)
@settings(max_examples=20)
def test_mapping_is_a_pure_deterministic_function_of_its_inputs(
    status: EligibilityStatus, gate: bool
) -> None:
    eligibility = EligibilityResult(status=status, reasons=(), rights_registry_version=_REGISTRY_VERSION, vocabulary=EligibilityVocabulary.PUBLICATION
    )
    result_a = map_eligibility_to_publication_status(eligibility, gate_p1_activated=gate)
    result_b = map_eligibility_to_publication_status(eligibility, gate_p1_activated=gate)
    assert result_a is result_b
    assert isinstance(result_a, PublicationEligibility)


@given(status=st.sampled_from([EligibilityStatus.INELIGIBLE_LICENSING, EligibilityStatus.INELIGIBLE_STALE_RIGHTS]))
@settings(max_examples=20)
def test_mapping_ineligible_statuses_are_gate_independent(status: EligibilityStatus) -> None:
    eligibility = EligibilityResult(status=status, reasons=("x",), rights_registry_version=_REGISTRY_VERSION, vocabulary=EligibilityVocabulary.PUBLICATION
    )
    with_gate = map_eligibility_to_publication_status(eligibility, gate_p1_activated=True)
    without_gate = map_eligibility_to_publication_status(eligibility, gate_p1_activated=False)
    assert with_gate is without_gate


@given(
    value=st.decimals(min_value="0.0001", max_value="0.9999", places=6, allow_nan=False, allow_infinity=False),
    places=st.integers(min_value=0, max_value=6),
)
@settings(max_examples=50)
def test_display_decimal_never_mutates_input_and_is_idempotent_at_same_precision(
    value: Decimal, places: int
) -> None:
    before = value
    rounded_once = display_decimal(value, places=places)
    assert value == before
    rounded_twice = display_decimal(rounded_once, places=places)
    assert rounded_once == rounded_twice


@given(
    race_id=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("Ll", "Nd"))),
    market_id=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("Ll", "Nd"))),
    availability=st.sampled_from(
        [
            ForecastAvailability.UNAVAILABLE_NO_PREDICTION,
            ForecastAvailability.UNAVAILABLE_EXCLUDED,
            ForecastAvailability.WITHHELD_DATA_QUALITY,
        ]
    ),
)
@settings(max_examples=30)
def test_unavailable_forecast_always_carries_recommendation_not_evaluated(
    race_id: str, market_id: str, availability: ForecastAvailability
) -> None:
    export = build_unavailable(
        race_id,
        market_id,
        availability,
        "reason text",
        generated_at_utc=datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert export.recommendation_status is RecommendationStatus.NOT_EVALUATED
