"""Roll (1984) spread proxy from a market's own prints — the band around hypothetical money.

DR-TENNIS-MICROSTRUCTURE-001's standard: BASIC money numbers need an execution-cost
sensitivity band, and the defensible transaction-only estimator family is Roll's — the
effective spread inferred from negative serial covariance of price changes. Where the
covariance is positive (trending prints), the estimator is undefined and must REFUSE,
never return zero: zero claims frictionless execution, which is the exact assumption the
band exists to retire.
"""
from decimal import Decimal

from tennis_edge.execution_cost import MIN_PRINTS, roll_spread


def test_alternating_prints_recover_a_positive_spread() -> None:
    prices = [Decimal(p) for p in ("2.00", "2.02", "2.00", "2.02", "2.00", "2.02",
                                   "2.00", "2.02")]
    spread = roll_spread(prices)
    assert spread is not None and spread > 0
    # Bouncing one tick around 2.0 is a relative spread near 0.01, not near 0.5.
    assert 0.001 < spread < 0.05


def test_trending_prints_refuse_rather_than_claim_zero_cost() -> None:
    prices = [Decimal(p) for p in ("2.00", "2.04", "2.08", "2.12", "2.16", "2.20")]
    assert roll_spread(prices) is None


def test_too_few_prints_refuse() -> None:
    assert roll_spread([Decimal("2.0")] * (MIN_PRINTS - 1)) is None


def test_constant_prints_refuse_a_market_with_no_information() -> None:
    assert roll_spread([Decimal("2.0")] * 20) is None


def test_wider_bounce_means_wider_spread() -> None:
    narrow = roll_spread([Decimal("2.00"), Decimal("2.02")] * 6)
    wide = roll_spread([Decimal("2.00"), Decimal("2.10")] * 6)
    assert narrow is not None and wide is not None and wide > narrow
