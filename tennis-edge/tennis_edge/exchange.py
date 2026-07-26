"""Exchange prices as a market probability, and expected value at an exchange price.

An exchange is not a bookmaker, and two differences decide whether a bet is worth making.

**There is no built-in overround.** A bookmaker's two prices are one line quoted together
with a margin baked in, so they always sum to more than 1.0 — 4.4% more on main-tour tennis.
Two exchange last-traded prices are *separate trades at separate moments*, so they can sum
to slightly over **or slightly under** 1.0. An under-round pair is normal exchange data, not
corruption, and must not be refused. The pair is still normalised to a proper probability,
because a probability that does not sum to 1 is not one.

**Commission is charged on the net market result**, not on the stake and not per order. A
winner at 3.0 nets 2.0 profit, of which 2% is taken; the stake is never taxed and a losing
bet pays no commission at all. Applying commission to the stake, or per order, understates
the exchange and would flatter a bookmaker comparison.

Together these are why exchange prices are the one genuinely untested case in this package:
at the same displayed odds the exchange pays strictly more, because the bookmaker's margin
is already inside its price while commission only ever touches profit.

Money is exact. Prices and commission are :class:`~decimal.Decimal`; floats are refused.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique

from price_contracts.ladder import is_on_ladder
from tennis_edge.betfair import MarketHistory
from tennis_edge.devig import DevigMethod, devig

__all__ = [
    "COMMISSION",
    "PriceSource",
    "ExchangeQuote",
    "exchange_probability",
    "net_odds",
    "expected_value",
]

#: Betfair Rewards flat rate on the net market result.
COMMISSION = Decimal("0.02")

DEVIG_METHOD = DevigMethod.POWER


@unique
class PriceSource(Enum):
    """Which price the probability is estimated from. These are different jobs.

    ``MIDPOINT`` is the estimator: the normalised midpoint of best back and best lay, which
    is the pilot's benchmark candidate 1 (available for 99.5% of singles). Best-back alone
    is the *worst* price on each side, so estimating a probability from it distorts the
    favourite/longshot balance even after de-vigging.

    ``BEST_BACK`` is what you can transact at, and is what EV must be computed against.
    A quote carries both: the midpoint for the probability, the backable price for the money.

    ``LAST_TRADED`` is a fallback for feeds with no ladder (BASIC). Two prints from
    different moments can imply less than 1.0 in total; that is an artefact, not a market.
    """

    MIDPOINT = "MIDPOINT"
    BEST_BACK = "BEST_BACK"
    LAST_TRADED = "LAST_TRADED"


@dataclass(frozen=True)
class ExchangeQuote:
    """A two-sided exchange price at one horizon, with its de-vigged probabilities."""

    selection_a: int
    selection_b: int
    price_a: Decimal
    price_b: Decimal
    probability_a: float
    probability_b: float
    seconds_before_off: int
    #: Sum of the raw implied probabilities. From two best-BACK prices this is a genuine
    #: over-round (always > 1.0) and is the real cost of crossing. From two last-traded
    #: prints it can fall BELOW 1.0 — those are separate moments straddling the true price,
    #: which is an artefact of the measurement, not a free market.
    raw_overround: float
    #: True when the quote came from the ladder (a crossable price), False from last trades.
    crossable: bool = False
    source: PriceSource = PriceSource.LAST_TRADED
    #: Size available at the quoted price. None in last-traded mode — a print carries no
    #: available size, so it cannot answer "could I have got matched".
    size_a: Decimal | None = None
    size_b: Decimal | None = None


def exchange_probability(
    history: MarketHistory,
    *,
    seconds_before_off: int,
    use_ladder: bool = False,
    source: PriceSource | None = None,
) -> ExchangeQuote | None:
    """De-vigged exchange probability at a horizon, or ``None`` if there is no price.

    ``use_ladder=True`` reads the best price available **to back** (ADVANCED ``batb``) —
    a crossable price with size, which is what you could actually have taken. The default
    reads the last traded price, which is a print of something that already happened and
    may not have been available to you; use it only when the feed carries no ladder (BASIC).

    The distinction is not cosmetic. Two last-traded prints come from different moments and
    can straddle the true price, so their implied probabilities can sum to *under* 1.0 and
    make the market look free. Two best-back prices are a real two-sided book and always
    sum above 1.0 — the genuine cost of crossing.

    ``None`` means one or both sides had no price at that horizon. It is never a guess and
    never substituted from the other side: a single side is not a market.
    """
    active = [r for r in history.runners if r.status.upper() == "ACTIVE"]
    if len(active) != 2:
        raise ValueError(
            f"market {history.market_id} has {len(active)} active runners; Match Odds is "
            "two active runners and a different count is a different choice set"
        )
    if source is None:
        source = PriceSource.BEST_BACK if use_ladder else PriceSource.LAST_TRADED
    a, b = active[0].selection_id, active[1].selection_id

    if source is PriceSource.LAST_TRADED:
        traded_a = history.ltp_at(a, seconds_before_off=seconds_before_off)
        traded_b = history.ltp_at(b, seconds_before_off=seconds_before_off)
        if traded_a is None or traded_b is None:
            return None
        return _quote(a, b, traded_a, traded_b, None, None,
                      1.0 / float(traded_a), 1.0 / float(traded_b),
                      seconds_before_off, source)

    back_a = history.best_back_at(a, seconds_before_off=seconds_before_off)
    back_b = history.best_back_at(b, seconds_before_off=seconds_before_off)
    if back_a is None or back_b is None:
        return None

    if source is PriceSource.BEST_BACK:
        return _quote(a, b, back_a.price, back_b.price, back_a.size, back_b.size,
                      1.0 / float(back_a.price), 1.0 / float(back_b.price),
                      seconds_before_off, source)

    lay_a = history.best_lay_at(a, seconds_before_off=seconds_before_off)
    lay_b = history.best_lay_at(b, seconds_before_off=seconds_before_off)
    if lay_a is None or lay_b is None:
        # A one-sided book has no midpoint, and it is not inferred from the side that
        # happens to exist. That would be inventing the half of the market that is missing.
        return None
    implied_a = (1.0 / float(back_a.price) + 1.0 / float(lay_a.price)) / 2.0
    implied_b = (1.0 / float(back_b.price) + 1.0 / float(lay_b.price)) / 2.0
    # The backable price and its size still travel with the quote: the probability comes
    # from the midpoint, but any EV must be computed at the price you could actually take.
    return _quote(a, b, back_a.price, back_b.price, back_a.size, back_b.size,
                  implied_a, implied_b, seconds_before_off, source)


def _quote(
    a: int, b: int, price_a: Decimal, price_b: Decimal,
    size_a: Decimal | None, size_b: Decimal | None,
    implied_a: float, implied_b: float, seconds_before_off: int, source: PriceSource,
) -> ExchangeQuote:
    total = implied_a + implied_b
    result = devig((1.0 / implied_a, 1.0 / implied_b), DEVIG_METHOD)
    return ExchangeQuote(
        selection_a=a, selection_b=b, price_a=price_a, price_b=price_b,
        probability_a=result.probabilities[0], probability_b=result.probabilities[1],
        seconds_before_off=seconds_before_off, raw_overround=total,
        crossable=source is not PriceSource.LAST_TRADED,
        size_a=size_a, size_b=size_b, source=source,
    )


def _check_commission(commission: Decimal) -> None:
    if not isinstance(commission, Decimal):
        raise TypeError(
            f"commission must be Decimal, got {type(commission).__name__} — money "
            "arithmetic is exact or it does not happen"
        )
    if not Decimal(0) <= commission < Decimal(1):
        raise ValueError(f"commission must be in [0, 1), got {commission}")


def net_odds(price: Decimal, *, commission: Decimal) -> Decimal:
    """Decimal odds after commission on winnings.

    ``1 + (price - 1)(1 - commission)``. The stake is untouched: only the profit part is
    charged, which is how an exchange actually bills.
    """
    _check_commission(commission)
    if not isinstance(price, Decimal):
        raise TypeError(f"price must be Decimal, got {type(price).__name__}")
    if not is_on_ladder(price):
        raise ValueError(f"price {price} is off-ladder; exchange prices are always on it")
    return Decimal(1) + (price - Decimal(1)) * (Decimal(1) - commission)


def expected_value(
    *, probability: float, price: Decimal, commission: Decimal = COMMISSION
) -> float:
    """EV per unit stake for a single back position held to settlement.

    ``p·(net_odds - 1) - (1 - p)``. A losing bet pays no commission, so the downside is
    exactly the stake regardless of the rate.
    """
    net = float(net_odds(price, commission=commission))
    return probability * (net - 1.0) - (1.0 - probability)
