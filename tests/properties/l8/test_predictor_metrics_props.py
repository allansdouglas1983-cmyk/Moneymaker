"""SPEC-038 properties: coverage monotonicity, digest determinism, per-kind non-merging."""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l8_evidence.prediction_snapshots import VintageType
from l8_evidence.predictor_metrics import (
    BenchmarkDefinition,
    ForecastVintagePolicy,
    ModelKind,
    RaceEvaluationInput,
    ReliabilityBand,
    RunnerOutcome,
    coverage_rate,
    evaluate_overall,
    evaluate_race,
    compute_input_digest,
)

pytestmark = pytest.mark.spec("SPEC-038")

_INCLUSION_HASH = "sha256:" + "1" * 64
_EXCLUSION_HASH = "sha256:" + "2" * 64
_HORIZON = "T-60m"

_PROB = st.decimals(min_value=Decimal("0.05"), max_value=Decimal("0.95"), places=2)


def _bands() -> tuple[ReliabilityBand, ...]:
    return (
        ReliabilityBand(label="low", lower=Decimal("0"), upper=Decimal("0.5")),
        ReliabilityBand(label="high", lower=Decimal("0.5"), upper=Decimal("1")),
    )


def _benchmark() -> BenchmarkDefinition:
    return BenchmarkDefinition(
        benchmark_id="predictor-eval-v1",
        version=1,
        universe_version="universe-2026-07",
        forecast_vintage_policy=ForecastVintagePolicy.FINAL_APPROVED_HORIZON_ONLY,
        inclusion_hash=_INCLUSION_HASH,
        exclusion_hash=_EXCLUSION_HASH,
        coverage_policy="all scheduled UK/IRE flat races",
        decision_horizon=_HORIZON,
        approved_reliability_bands=_bands(),
    )


def _race_for(p1: Decimal, race_id: str = "race-1", model_kind: ModelKind = ModelKind.COMBINED) -> RaceEvaluationInput:
    p2 = Decimal(1) - p1
    return RaceEvaluationInput(
        race_id=race_id,
        model_kind=model_kind,
        decision_horizon=_HORIZON,
        settled=True,
        vintage_type=VintageType.FINAL_APPROVED_HORIZON,
        runners=(
            RunnerOutcome(runner_id=1, probability=p1, is_winner=True),
            RunnerOutcome(runner_id=2, probability=p2, is_winner=False),
        ),
    )


@given(_PROB)
@settings(max_examples=50)
def test_coverage_never_exceeds_one(evaluated_fraction: Decimal) -> None:
    total = 100
    evaluated = int(evaluated_fraction * total)
    result = coverage_rate(races_evaluated=evaluated, total_universe_races=total)
    assert 0.0 <= result.coverage_rate <= 1.0


@given(st.integers(min_value=0, max_value=100), st.integers(min_value=1, max_value=100))
@settings(max_examples=50)
def test_coverage_monotone_in_evaluated(evaluated: int, total: int) -> None:
    evaluated = min(evaluated, total)
    fewer = max(evaluated - 1, 0)
    result_full = coverage_rate(races_evaluated=evaluated, total_universe_races=total)
    result_fewer = coverage_rate(races_evaluated=fewer, total_universe_races=total)
    assert result_fewer.coverage_rate <= result_full.coverage_rate


@given(_PROB)
@settings(max_examples=50)
def test_digest_deterministic_across_repeated_calls(p1: Decimal) -> None:
    races = [_race_for(p1)]
    digest_1 = compute_input_digest(races)
    digest_2 = compute_input_digest(races)
    assert digest_1 == digest_2
    assert digest_1.startswith("sha256:")


@given(_PROB)
@settings(max_examples=50)
def test_log_score_worsens_as_winner_probability_falls(p1: Decimal) -> None:
    # A lower winner probability must never produce a BETTER (lower) log score.
    lower_p = p1 / 2
    race_high = _race_for(p1)
    race_low = _race_for(lower_p)
    benchmark = _benchmark()
    high_score = evaluate_race(race_high, benchmark).log_score
    low_score = evaluate_race(race_low, benchmark).log_score
    assert low_score >= high_score


@given(_PROB)
@settings(max_examples=30)
def test_same_race_different_kind_never_merged(p1: Decimal) -> None:
    race_combined = _race_for(p1, model_kind=ModelKind.COMBINED)
    race_fundamental = _race_for(p1, model_kind=ModelKind.FUNDAMENTAL)
    benchmark = _benchmark()
    result_combined = evaluate_overall(
        [race_combined], benchmark, ModelKind.COMBINED, total_universe_races=1
    )
    result_fundamental = evaluate_overall(
        [race_fundamental], benchmark, ModelKind.FUNDAMENTAL, total_universe_races=1
    )
    assert result_combined.model_kind is ModelKind.COMBINED
    assert result_fundamental.model_kind is ModelKind.FUNDAMENTAL
    # Deliberate cross-kind inequality: mypy narrows each side to a distinct literal.
    assert result_combined.model_kind != result_fundamental.model_kind  # type: ignore[comparison-overlap]
