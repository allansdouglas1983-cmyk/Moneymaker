"""SPEC-090 properties: paired race-level log-score differences and the block bootstrap
clustered by meeting-day.

Runner-level independence assumptions must never appear anywhere in this module — every
property here is stated purely in terms of races and meeting-days.
"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l8_evidence.paired_inference import (
    PairedRace,
    block_bootstrap_ci,
    empirical_percentile,
    paired_differences,
)

from sport_core.clustering import ClusterId


def _cid(day):  # racing dependence-group identity for tests (A4); identity only, no order
    return ClusterId(f"horse_racing:day:{day.isoformat()}")

pytestmark = pytest.mark.spec("SPEC-090")

_DAY1 = date(2026, 6, 1)
_DAY2 = date(2026, 6, 2)

_PROB = st.decimals(min_value=Decimal("0.05"), max_value=Decimal("0.95"), places=2)


def _race(race_id: str, meeting_day: date, p_market: Decimal, p_combined: Decimal) -> PairedRace:
    return PairedRace(
        race_id=race_id,
        cluster_id=_cid(meeting_day),
        p_market_winner=p_market,
        p_combined_winner=p_combined,
    )


# --- mean_d equals the plain mean of d_r when every race shares one value -------------------


@given(
    p_market=_PROB,
    p_combined=_PROB,
    n_day1=st.integers(min_value=1, max_value=5),
    n_day2=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=50)
def test_mean_d_equals_constant_d_r_when_all_races_share_one_value(
    p_market: Decimal, p_combined: Decimal, n_day1: int, n_day2: int
) -> None:
    races = tuple(
        _race(f"d1-{i}", _DAY1, p_market, p_combined) for i in range(n_day1)
    ) + tuple(_race(f"d2-{i}", _DAY2, p_market, p_combined) for i in range(n_day2))
    expected_d_r = math.log(float(p_combined)) - math.log(float(p_market))
    result = block_bootstrap_ci(races, n_resamples=20, confidence_level=Decimal("0.8"), seed=1)
    assert result.mean_d == pytest.approx(expected_d_r, rel=1e-9, abs=1e-9)


# --- lower <= upper, and mean_d stays within the observed [min, max] of d_r -----------------


_RACE_SPEC = st.tuples(_PROB, _PROB, st.booleans())
_RACE_SPECS = st.lists(_RACE_SPEC, min_size=4, max_size=12).filter(
    lambda specs: any(day for _, _, day in specs) and any(not day for _, _, day in specs)
)


@given(specs=_RACE_SPECS, seed=st.integers(min_value=0, max_value=2**31 - 1))
@settings(max_examples=50)
def test_ci_bounds_ordered_and_mean_within_observed_range(
    specs: list[tuple[Decimal, Decimal, bool]], seed: int
) -> None:
    races = tuple(
        _race(f"r-{i}", _DAY2 if is_day2 else _DAY1, p_market, p_combined)
        for i, (p_market, p_combined, is_day2) in enumerate(specs)
    )
    diffs = paired_differences(races)
    d_values = [d.d_r for d in diffs]

    result = block_bootstrap_ci(races, n_resamples=20, confidence_level=Decimal("0.8"), seed=seed)

    assert result.lower <= result.upper
    assert min(d_values) - 1e-9 <= result.mean_d <= max(d_values) + 1e-9


# --- determinism: same seed -> byte-identical digest, for arbitrary race sets ---------------


@given(specs=_RACE_SPECS, seed=st.integers(min_value=0, max_value=2**31 - 1))
@settings(max_examples=30)
def test_same_seed_is_byte_identical_digest(
    specs: list[tuple[Decimal, Decimal, bool]], seed: int
) -> None:
    races = tuple(
        _race(f"r-{i}", _DAY2 if is_day2 else _DAY1, p_market, p_combined)
        for i, (p_market, p_combined, is_day2) in enumerate(specs)
    )
    result_a = block_bootstrap_ci(races, n_resamples=15, confidence_level=Decimal("0.8"), seed=seed)
    result_b = block_bootstrap_ci(races, n_resamples=15, confidence_level=Decimal("0.8"), seed=seed)
    assert result_a.content_digest() == result_b.content_digest()


# --- empirical_percentile: monotone in quantile, always within [min, max] of the sample -----


@given(
    values=st.lists(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False), min_size=1, max_size=30),
    q_low=st.decimals(min_value=Decimal("0"), max_value=Decimal("1"), places=3),
    q_high=st.decimals(min_value=Decimal("0"), max_value=Decimal("1"), places=3),
)
@settings(max_examples=75)
def test_empirical_percentile_monotone_and_bounded(
    values: list[float], q_low: Decimal, q_high: Decimal
) -> None:
    if q_low > q_high:
        q_low, q_high = q_high, q_low
    sorted_values = sorted(values)
    lo = empirical_percentile(sorted_values, q_low)
    hi = empirical_percentile(sorted_values, q_high)
    assert lo <= hi + 1e-9
    assert sorted_values[0] - 1e-9 <= lo <= sorted_values[-1] + 1e-9
    assert sorted_values[0] - 1e-9 <= hi <= sorted_values[-1] + 1e-9
