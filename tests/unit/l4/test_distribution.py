"""SPEC-034: a distribution over win probability whose ONLY decision-layer exit is the
conservative lower bound. The type cannot be coerced to a point estimate."""
from __future__ import annotations

from decimal import Decimal

import pytest

from l4_pricing.distribution import WinProbabilityDistribution
from l5_decision.ev import WinProbabilityLowerBound

pytestmark = pytest.mark.spec("SPEC-034")


def test_requires_at_least_two_samples_in_open_interval() -> None:
    with pytest.raises(ValueError):
        WinProbabilityDistribution(samples=(0.4,))
    with pytest.raises(ValueError):
        WinProbabilityDistribution(samples=(0.4, 1.0))
    with pytest.raises(ValueError):
        WinProbabilityDistribution(samples=(0.0, 0.4))


def test_samples_are_stored_sorted() -> None:
    d = WinProbabilityDistribution(samples=(0.5, 0.2, 0.4))
    assert d.samples == (0.2, 0.4, 0.5)


def test_conservative_lower_bound_is_the_lower_order_statistic() -> None:
    d = WinProbabilityDistribution(samples=(0.2, 0.4, 0.5, 0.6, 0.8))
    # floor(q*(n-1)): q=0.25 over 5 samples -> index 1 -> 0.4
    bound = d.conservative_lower_bound(Decimal("0.25"))
    assert isinstance(bound, WinProbabilityLowerBound)
    assert bound.value == Decimal("0.4")
    assert d.conservative_lower_bound(Decimal("0.05")).value == Decimal("0.2")


def test_quantile_must_be_in_open_unit_interval() -> None:
    d = WinProbabilityDistribution(samples=(0.2, 0.4))
    for bad in (Decimal("0"), Decimal("1"), Decimal("-0.1"), Decimal("1.5")):
        with pytest.raises(ValueError):
            d.conservative_lower_bound(bad)


def test_cannot_be_coerced_to_a_point_estimate() -> None:
    d = WinProbabilityDistribution(samples=(0.2, 0.4))
    with pytest.raises(TypeError):
        bool(d)
    with pytest.raises(TypeError):
        float(d)
    for forbidden in ("mean", "median", "point_estimate"):
        assert not hasattr(d, forbidden)
