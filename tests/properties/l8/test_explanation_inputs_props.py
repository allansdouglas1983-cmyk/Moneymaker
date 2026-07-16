"""SPEC-039: deterministic explanation inputs — Hypothesis property tests.

Determinism: same inputs -> identical digest and identical reason codes; reordering the
contributions input must not change the derived reason codes or digest (canonical ordering
internal to the module, not caller-supplied).
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from governance.output_rights import EligibilityResult, EligibilityStatus, EligibilityVocabulary
from l4_pricing.probability_outputs import (
    CombinedProbability,
    RaceProbabilityOutputs,
    RunnerProbabilities,
)
from l8_evidence.explanation_inputs import FeatureContribution, build_explanation_inputs
from l8_evidence.prediction_snapshots import (
    DualClockTimestamp,
    MarketStateSnapshot,
    PredictionSnapshot,
    UncertaintySummary,
    VintageType,
    build_active_runner_set_hash,
    build_fair_odds,
)

pytestmark = pytest.mark.spec("SPEC-039")

_MODEL_DIGEST = "sha256:" + "1" * 64
_FEATURE_DIGEST = "sha256:" + "2" * 64
_SOURCE_DIGEST = "sha256:" + "3" * 64
_REGISTRY_VERSION = "sha256:" + "4" * 64
_APPROVED_FEATURES = ("f_a", "f_b", "f_c", "f_d", "f_e")


def _snapshot() -> PredictionSnapshot:
    race = RaceProbabilityOutputs(
        race_id="race-1",
        runners=(
            RunnerProbabilities(
                runner_id=1,
                p_combined=CombinedProbability(probability=Decimal("0.6"), model_digest=_MODEL_DIGEST),
                p_fundamental_missing_reason="not modelled in this test",
                p_market_info_missing_reason="not modelled in this test",
            ),
            RunnerProbabilities(
                runner_id=2,
                p_combined=CombinedProbability(probability=Decimal("0.4"), model_digest=_MODEL_DIGEST),
                p_fundamental_missing_reason="not modelled in this test",
                p_market_info_missing_reason="not modelled in this test",
            ),
        ),
    )
    return PredictionSnapshot(
        prediction_id="pred-1",
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
        uncertainty=UncertaintySummary(
            method="time_fold_ensemble_v1",
            lower=Decimal("0.50"),
            central=Decimal("0.58"),
            upper=Decimal("0.66"),
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


_finite_floats = st.floats(
    allow_nan=False, allow_infinity=False, min_value=-1000.0, max_value=1000.0
)


@st.composite
def _contribution_sets(draw: st.DrawFn) -> tuple[FeatureContribution, ...]:
    n = draw(st.integers(min_value=1, max_value=len(_APPROVED_FEATURES)))
    names = draw(
        st.permutations(_APPROVED_FEATURES).map(lambda perm: perm[:n])
    )
    magnitudes = draw(st.lists(_finite_floats, min_size=n, max_size=n))
    return tuple(
        FeatureContribution(feature_name=name, magnitude=magnitude)
        for name, magnitude in zip(names, magnitudes)
    )


@given(contributions=_contribution_sets())
@settings(max_examples=100)
def test_same_inputs_produce_identical_digest_and_reason_codes(
    contributions: tuple[FeatureContribution, ...],
) -> None:
    snapshot = _snapshot()
    kwargs = dict(
        snapshot=snapshot,
        method_id="linear-coefficient-contributions",
        method_version=1,
        approved_feature_names=_APPROVED_FEATURES,
        source_lineage_ids=("source-a", "source-b"),
    )
    first = build_explanation_inputs(contributions=contributions, **kwargs)  # type: ignore[arg-type]
    second = build_explanation_inputs(contributions=contributions, **kwargs)  # type: ignore[arg-type]
    assert first.reproducibility_digest == second.reproducibility_digest
    assert first.reason_codes == second.reason_codes


@given(contributions=_contribution_sets())
@settings(max_examples=100)
def test_reordering_contributions_does_not_change_digest_or_reason_codes(
    contributions: tuple[FeatureContribution, ...],
) -> None:
    snapshot = _snapshot()
    shuffled = list(contributions)
    rng = random.Random(1234567)
    rng.shuffle(shuffled)
    kwargs = dict(
        snapshot=snapshot,
        method_id="linear-coefficient-contributions",
        method_version=1,
        approved_feature_names=_APPROVED_FEATURES,
        source_lineage_ids=("source-a", "source-b"),
    )
    original = build_explanation_inputs(contributions=contributions, **kwargs)  # type: ignore[arg-type]
    reordered = build_explanation_inputs(contributions=tuple(shuffled), **kwargs)  # type: ignore[arg-type]
    assert original.reproducibility_digest == reordered.reproducibility_digest
    assert original.reason_codes == reordered.reason_codes
