"""Exchange prices as a market probability, and EV at an exchange price.

An exchange is not a bookmaker and the arithmetic differs in two ways that decide whether a
bet is worth making:

* there is no built-in overround — two last-traded prices can sum to slightly over or
  slightly *under* 1.0, because they are separate trades at separate moments, not a
  bookmaker's two-sided line;
* commission is charged on the **net market result**, not on the stake and not per order,
  so it reduces winnings only.

Getting either wrong flatters the result, which is why both are pinned here.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from tennis_edge.betfair import LtpObservation, MarketHistory, Runner
from tennis_edge.exchange import (
    ExchangeQuote,
    expected_value,
    exchange_probability,
    net_odds,
)

A, B = 111, 222
OFF_MS = int(dt.datetime(2025, 6, 15, 14, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _history(prices: dict[int, str], *, minutes_before: int = 30) -> MarketHistory:
    at = OFF_MS - minutes_before * 60_000
    return MarketHistory(
        market_id="1.1", event_id="9", event_name="A v B", market_type="MATCH_ODDS",
        country_code="GB", market_time_ms=OFF_MS,
        runners=(Runner(A, "Player A", "ACTIVE", 1), Runner(B, "Player B", "ACTIVE", 2)),
        observations=tuple(
            LtpObservation(publish_time_ms=at, selection_id=sid, price=Decimal(p))
            for sid, p in prices.items()
        ),
        went_in_play=False,
    )


# ------------------------------------------------------------------ probability


def test_a_balanced_book_prices_at_a_half() -> None:
    quote = exchange_probability(_history({A: "2.0", B: "2.0"}), seconds_before_off=600)
    assert quote is not None
    assert quote.probability_a == pytest.approx(0.5)
    assert quote.probability_b == pytest.approx(0.5)


def test_probabilities_sum_to_one_after_devig() -> None:
    quote = exchange_probability(_history({A: "1.5", B: "3.0"}), seconds_before_off=600)
    assert quote is not None
    assert quote.probability_a + quote.probability_b == pytest.approx(1.0)


def test_the_favourite_carries_the_higher_probability() -> None:
    quote = exchange_probability(_history({A: "1.4", B: "3.2"}), seconds_before_off=600)
    assert quote is not None
    assert quote.probability_a > quote.probability_b


def test_an_underround_book_is_handled_not_refused() -> None:
    """Two LTPs are separate trades at separate moments, so unlike a bookmaker's line they
    can imply less than 1.0 in total. That is normal exchange data, not corruption."""
    quote = exchange_probability(_history({A: "2.5", B: "2.5"}), seconds_before_off=600)
    assert quote is not None
    assert quote.raw_overround < 1.0
    assert quote.probability_a + quote.probability_b == pytest.approx(1.0)


def test_a_missing_side_yields_no_quote() -> None:
    """One traded side is not a market. No guess, no substitution from the other side."""
    assert exchange_probability(_history({A: "2.0"}), seconds_before_off=600) is None


def test_a_horizon_before_any_trade_yields_no_quote() -> None:
    history = _history({A: "2.0", B: "2.0"}, minutes_before=10)
    assert exchange_probability(history, seconds_before_off=1800) is None


def test_a_quote_records_the_prices_it_came_from() -> None:
    quote = exchange_probability(_history({A: "1.5", B: "3.0"}), seconds_before_off=600)
    assert quote is not None
    assert quote.price_a == Decimal("1.5") and quote.price_b == Decimal("3.0")
    assert quote.seconds_before_off == 600


def test_a_market_that_is_not_two_active_runners_is_refused() -> None:
    history = MarketHistory(
        market_id="1.1", event_id="9", event_name="A v B", market_type="MATCH_ODDS",
        country_code="GB", market_time_ms=OFF_MS,
        runners=(Runner(A, "Player A", "ACTIVE", 1),),
        observations=(), went_in_play=False,
    )
    with pytest.raises(ValueError, match="two active runners"):
        exchange_probability(history, seconds_before_off=600)


# ------------------------------------------------------------------ commission and EV


def test_commission_reduces_winnings_only() -> None:
    """Betfair charges on the net market result. A 3.0 winner nets 2.0 profit, 2% of which
    is commission; the stake itself is never taxed."""
    assert net_odds(Decimal("3.0"), commission=Decimal("0.02")) == Decimal("2.96")


def test_commission_never_touches_a_losing_stake() -> None:
    assert expected_value(
        probability=0.0, price=Decimal("3.0"), commission=Decimal("0.02")
    ) == pytest.approx(-1.0), "a certain loser loses exactly the stake, commission or not"


def test_an_exchange_price_beats_the_same_bookmaker_price() -> None:
    """The whole reason exchange prices are the untested case: at the same displayed odds
    the exchange pays more, because a bookmaker's margin is already inside its price while
    commission only touches profit."""
    exchange = expected_value(probability=0.4, price=Decimal("3.0"),
                              commission=Decimal("0.02"))
    gross = expected_value(probability=0.4, price=Decimal("3.0"), commission=Decimal("0"))
    assert gross > exchange > -1.0
    # SPEC-050: EV = p(O-1)(1-c) - (1-p). Stake back is not profit.
    assert exchange == pytest.approx(0.4 * (2.0 * 0.98) - 0.6)


def test_expected_value_rises_with_probability() -> None:
    lower = expected_value(probability=0.30, price=Decimal("3.0"),
                           commission=Decimal("0.02"))
    higher = expected_value(probability=0.45, price=Decimal("3.0"),
                            commission=Decimal("0.02"))
    assert higher > lower


def test_expected_value_falls_as_commission_rises() -> None:
    cheap = expected_value(probability=0.4, price=Decimal("3.0"),
                           commission=Decimal("0.02"))
    dear = expected_value(probability=0.4, price=Decimal("3.0"), commission=Decimal("0.05"))
    assert dear < cheap


def test_a_fair_priced_bet_has_zero_edge_before_commission() -> None:
    assert expected_value(
        probability=1 / 3, price=Decimal("3.0"), commission=Decimal("0")
    ) == pytest.approx(0.0)


def test_commission_outside_zero_to_one_is_refused() -> None:
    for bad in (Decimal("-0.01"), Decimal("1.5")):
        with pytest.raises(ValueError, match="commission"):
            net_odds(Decimal("3.0"), commission=bad)


def test_an_off_ladder_price_is_refused() -> None:
    with pytest.raises(ValueError, match="off-ladder"):
        net_odds(Decimal("2.03"), commission=Decimal("0.02"))


def test_float_commission_is_refused() -> None:
    """Money arithmetic is exact or it does not happen."""
    with pytest.raises(TypeError):
        net_odds(Decimal("3.0"), commission=0.02)  # type: ignore[arg-type]


def test_a_quote_is_frozen() -> None:
    quote = exchange_probability(_history({A: "2.0", B: "2.0"}), seconds_before_off=600)
    assert isinstance(quote, ExchangeQuote)
    with pytest.raises(Exception):
        quote.probability_a = 0.9  # type: ignore[misc]
