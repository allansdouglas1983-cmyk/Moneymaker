"""Roll (1984) spread proxy from a market's own prints — the band around hypothetical money.

DR-TENNIS-MICROSTRUCTURE-001's standard: BASIC money numbers need an execution-cost
sensitivity band, and the defensible transaction-only estimator family is Roll's — the
effective spread inferred from negative serial covariance of price changes. Where the
covariance is positive (trending prints), the estimator is undefined and must REFUSE,
never return zero: zero claims frictionless execution, which is the exact assumption the
band exists to retire.
"""
from decimal import Decimal

import pytest

from tennis_edge.betfair import LtpObservation, MarketHistory, Runner
from tennis_edge.execution_cost import (MIN_PRINTS, haircut_odds, roll_spread,
                                        selection_spreads)


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


# --- selection_spreads: the estimator applied per selection to a market's own trace ---

OFF_MS = 1_700_000_000_000
SEL_A, SEL_B = 111, 222


def _market(prints: list[tuple[int, int, str]]) -> MarketHistory:
    """``prints`` is (offset_index, selection_id, price), earliest first."""
    return MarketHistory(
        market_id="1.234", event_id="9", event_name="A v B", market_type="MATCH_ODDS",
        country_code="GB", market_time_ms=OFF_MS,
        runners=(Runner(selection_id=SEL_A, name="A", status="ACTIVE", sort_priority=1),
                 Runner(selection_id=SEL_B, name="B", status="ACTIVE", sort_priority=2)),
        observations=tuple(
            LtpObservation(publish_time_ms=OFF_MS - 3_600_000 + i * 1000,
                           selection_id=sid, price=Decimal(p))
            for i, (_, sid, p) in enumerate(prints)
        ),
        went_in_play=False,
    )


def test_selection_spreads_match_roll_spread_on_that_selections_own_series() -> None:
    series = ["2.00", "2.02", "2.00", "2.02", "2.00", "2.02", "2.00", "2.02"]
    market = _market([(i, SEL_A, p) for i, p in enumerate(series)])
    spreads = selection_spreads(market)
    assert spreads[SEL_A] == roll_spread([Decimal(p) for p in series])
    assert spreads[SEL_B] is None  # no prints is no estimate, never zero


def test_one_selections_prints_never_contaminate_the_others_series() -> None:
    """Interleaved A-bounce and B-trend: A gets its spread, B refuses. A pooled series
    would let B's trend poison A's covariance — the exact bug this function must not have."""
    prints: list[tuple[int, int, str]] = []
    bounce = ["2.00", "2.02"] * 4
    trend = ["3.00", "3.05", "3.10", "3.15", "3.20", "3.25", "3.30", "3.35"]
    for i in range(8):
        prints.append((0, SEL_A, bounce[i]))
        prints.append((0, SEL_B, trend[i]))
    spreads = selection_spreads(_market(prints))
    assert spreads[SEL_A] is not None and spreads[SEL_A] > 0
    assert spreads[SEL_B] is None


def test_every_runner_appears_in_the_result_even_with_no_prints() -> None:
    spreads = selection_spreads(_market([]))
    assert set(spreads) == {SEL_A, SEL_B}
    assert spreads[SEL_A] is None and spreads[SEL_B] is None


def test_too_few_prints_on_a_selection_refuse() -> None:
    market = _market([(i, SEL_A, p) for i, p in
                      enumerate(["2.00", "2.02"] * ((MIN_PRINTS - 1) // 2))])
    assert selection_spreads(market)[SEL_A] is None


# --- haircut_odds: applying a fraction of the spread as an execution cost ---


def test_zero_fraction_or_zero_spread_leaves_odds_unchanged() -> None:
    assert haircut_odds(Decimal("3.5"), 0.02, fraction=0.0) == pytest.approx(3.5)
    assert haircut_odds(Decimal("3.5"), 0.0, fraction=1.0) == pytest.approx(3.5)


def test_haircut_is_monotone_in_both_spread_and_fraction() -> None:
    base = haircut_odds(Decimal("3.0"), 0.01, fraction=0.5)
    wider = haircut_odds(Decimal("3.0"), 0.03, fraction=0.5)
    fuller = haircut_odds(Decimal("3.0"), 0.01, fraction=1.0)
    assert wider < base and fuller < base
    assert base < 3.0


def test_half_spread_on_log_price_is_the_declared_form() -> None:
    import math
    assert haircut_odds(Decimal("4.0"), 0.02, fraction=0.5) == pytest.approx(
        4.0 * math.exp(-0.01))


def test_haircut_floors_at_evens_rather_than_paying_a_negative_win() -> None:
    """A back at effective odds below 1.0 is not a worse fill, it is nonsense. The floor
    makes the pessimistic bound 'your win returns your stake', never 'your win loses'."""
    assert haircut_odds(Decimal("1.01"), 5.0, fraction=1.0) == 1.0


def test_negative_spread_and_out_of_range_fraction_refuse() -> None:
    with pytest.raises(ValueError):
        haircut_odds(Decimal("2.0"), -0.01, fraction=0.5)
    with pytest.raises(ValueError):
        haircut_odds(Decimal("2.0"), 0.01, fraction=1.5)
    with pytest.raises(ValueError):
        haircut_odds(Decimal("2.0"), 0.01, fraction=-0.5)
