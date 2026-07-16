"""SPEC-097 properties: Wilson-interval sanity, adaptive-bin partition validity, and
renormalising temperature-scaling invariants over randomly generated races.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l8_evidence.prediction_snapshots import VintageType
from l8_evidence.predictor_metrics import ModelKind, RaceEvaluationInput, RunnerOutcome
from l8_evidence.calibration import (
    TEMPERATURE_SCALING_METHOD_ID,
    TEMPERATURE_SCALING_VERSION,
    PosthocCalibrator,
    adaptive_bins,
    apply_posthoc_calibration,
    wilson_score_interval,
)

pytestmark = pytest.mark.spec("SPEC-097")

_HORIZON = "T-60m"

# Kept away from exactly 0.5 so temperature scaling has somewhere to move, and quantised to
# 2dp like the other l8_evidence property-test strategies.
_P1 = st.decimals(min_value=Decimal("0.55"), max_value=Decimal("0.95"), places=2)
_CONFIDENCE = st.sampled_from([Decimal("0.80"), Decimal("0.90"), Decimal("0.95"), Decimal("0.99")])


def _race(race_id: str, p1: Decimal) -> RaceEvaluationInput:
    p2 = Decimal(1) - p1
    return RaceEvaluationInput(
        race_id=race_id,
        model_kind=ModelKind.COMBINED,
        decision_horizon=_HORIZON,
        settled=True,
        vintage_type=VintageType.FINAL_APPROVED_HORIZON,
        runners=(
            RunnerOutcome(runner_id=1, probability=p1, is_winner=True),
            RunnerOutcome(runner_id=2, probability=p2, is_winner=False),
        ),
    )


# --- Wilson score interval -------------------------------------------------------------------


#: Floating-point tolerance for interval-boundary comparisons. The Wilson formula's
#: ``center`` and ``margin`` are computed via different arithmetic paths that are
#: mathematically identical at the boundary cases (e.g. successes == 0), so they can differ
#: by a few ULP (~1e-16) without any real miscalibration — this is not a relaxation of the
#: property, just an acknowledgement that float equality/ordering is never exact at that
#: scale.
_EPS = 1e-9


@given(
    total=st.integers(min_value=1, max_value=500),
    confidence_level=_CONFIDENCE,
)
@settings(max_examples=50)
def test_wilson_interval_always_within_unit_interval_and_contains_point_estimate(
    total: int, confidence_level: Decimal
) -> None:
    successes = total // 2
    lower, upper = wilson_score_interval(successes, total, confidence_level=confidence_level)
    p_hat = successes / total
    assert -_EPS <= lower <= upper <= 1.0 + _EPS
    assert lower <= p_hat + _EPS
    assert upper >= p_hat - _EPS


@given(total=st.integers(min_value=1, max_value=500))
@settings(max_examples=30)
def test_wilson_interval_widens_as_confidence_increases(total: int) -> None:
    successes = total // 2
    lower_90, upper_90 = wilson_score_interval(successes, total, confidence_level=Decimal("0.90"))
    lower_99, upper_99 = wilson_score_interval(successes, total, confidence_level=Decimal("0.99"))
    assert lower_99 <= lower_90 + _EPS
    assert upper_99 >= upper_90 - _EPS


@given(
    successes=st.integers(min_value=0, max_value=200),
    total=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=50)
def test_wilson_interval_deterministic(successes: int, total: int) -> None:
    successes = min(successes, total)
    result_1 = wilson_score_interval(successes, total, confidence_level=Decimal("0.95"))
    result_2 = wilson_score_interval(successes, total, confidence_level=Decimal("0.95"))
    assert result_1 == result_2


# --- adaptive_bins: gap-free partition property -----------------------------------------------


@given(
    n_bins=st.integers(min_value=2, max_value=5),
    p1s=st.lists(_P1, min_size=12, max_size=30, unique=True),
)
@settings(max_examples=30)
def test_adaptive_bins_always_gap_free_partition(n_bins: int, p1s: list[Decimal]) -> None:
    races = [_race(f"r{i}", p1) for i, p1 in enumerate(p1s)]
    bands = adaptive_bins(races, n_bins=n_bins)
    ordered = sorted(bands, key=lambda b: b.lower)
    assert ordered[0].lower == Decimal(0)
    assert ordered[-1].upper == Decimal(1)
    for prev, nxt in zip(ordered, ordered[1:]):
        assert prev.upper == nxt.lower
    assert len(ordered) == n_bins


# --- temperature scaling: renormalisation and monotone flattening -----------------------------


def _calibrator(temperature: Decimal) -> PosthocCalibrator:
    return PosthocCalibrator(
        method_id=TEMPERATURE_SCALING_METHOD_ID,
        version=TEMPERATURE_SCALING_VERSION,
        parameters={"T": temperature},
    )


@given(_P1)
@settings(max_examples=50)
def test_temperature_scaling_output_always_sums_to_one(p1: Decimal) -> None:
    p2 = Decimal(1) - p1
    result = apply_posthoc_calibration({1: p1, 2: p2}, _calibrator(Decimal("1.7")))
    total = sum(result.values(), Decimal(0))
    assert abs(total - Decimal(1)) < Decimal("1e-9")


@given(_P1)
@settings(max_examples=50)
def test_temperature_scaling_t_greater_than_one_strictly_flattens(p1: Decimal) -> None:
    p2 = Decimal(1) - p1
    original_max = max(p1, p2)
    result = apply_posthoc_calibration({1: p1, 2: p2}, _calibrator(Decimal("2")))
    assert max(result.values()) < original_max


@given(_P1)
@settings(max_examples=50)
def test_temperature_scaling_is_deterministic(p1: Decimal) -> None:
    p2 = Decimal(1) - p1
    calibrator = _calibrator(Decimal("1.3"))
    result_1 = apply_posthoc_calibration({1: p1, 2: p2}, calibrator)
    result_2 = apply_posthoc_calibration({1: p1, 2: p2}, calibrator)
    assert result_1 == result_2


@given(_P1)
@settings(max_examples=50)
def test_temperature_scaling_identity_at_t_equals_one(p1: Decimal) -> None:
    p2 = Decimal(1) - p1
    result = apply_posthoc_calibration({1: p1, 2: p2}, _calibrator(Decimal("1")))
    assert abs(result[1] - p1) < Decimal("1e-9")
    assert abs(result[2] - p2) < Decimal("1e-9")
