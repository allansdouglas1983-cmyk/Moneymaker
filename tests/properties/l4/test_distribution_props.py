"""SPEC-034 properties: the conservative lower bound is a real order statistic — inside the
sample set, monotone in the quantile, and deterministic."""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l4_pricing.distribution import WinProbabilityDistribution

pytestmark = pytest.mark.spec("SPEC-034")

_SAMPLES = st.lists(
    st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    min_size=2,
    max_size=12,
)
_Q = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.99"), places=2)


@settings(max_examples=200)
@given(samples=_SAMPLES, q=_Q)
def test_bound_is_a_member_sample_and_conservative(samples: list[float], q: Decimal) -> None:
    d = WinProbabilityDistribution(samples=tuple(samples))
    bound = d.conservative_lower_bound(q)
    as_float = float(bound.value)
    assert any(abs(as_float - s) < 1e-15 for s in d.samples)
    # at least (1-q) of the ensemble sits at or above the bound
    at_or_above = sum(1 for s in d.samples if s >= as_float - 1e-15)
    assert at_or_above >= len(d.samples) - int(q * Decimal(len(d.samples) - 1))


@settings(max_examples=200)
@given(samples=_SAMPLES, q_low=_Q, q_high=_Q)
def test_bound_is_monotone_in_the_quantile(
    samples: list[float], q_low: Decimal, q_high: Decimal
) -> None:
    if q_low > q_high:
        q_low, q_high = q_high, q_low
    d = WinProbabilityDistribution(samples=tuple(samples))
    assert d.conservative_lower_bound(q_low).value <= d.conservative_lower_bound(q_high).value


@settings(max_examples=100)
@given(samples=_SAMPLES, q=_Q)
def test_bound_is_deterministic_and_order_invariant(samples: list[float], q: Decimal) -> None:
    a = WinProbabilityDistribution(samples=tuple(samples))
    b = WinProbabilityDistribution(samples=tuple(reversed(samples)))
    assert a.conservative_lower_bound(q).value == b.conservative_lower_bound(q).value
