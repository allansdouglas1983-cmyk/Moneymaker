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

from price_contracts.ladder import is_on_ladder
from tennis_edge.betfair import MarketHistory
from tennis_edge.devig import DevigMethod, devig

__all__ = [
    "COMMISSION",
    "ExchangeQuote",
    "exchange_probability",
    "net_odds",
    "expected_value",
]

#: Betfair Rewards flat rate on the net market result.
COMMISSION = Decimal("0.02")

DEVIG_METHOD = DevigMethod.POWER


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
    #: Size available at the quoted price. None in last-traded mode — a print carries no
    #: available size, so it cannot answer "could I have got matched".
    size_a: Decimal | None = None
    size_b: Decimal | None = None


def exchange_probability(
    history: MarketHistory, *, seconds_before_off: int, use_ladder: bool = False
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
    a, b = active[0].selection_id, active[1].selection_id
    size_a: Decimal | None = None
    size_b: Decimal | None = None
    price_a: Decimal | None
    price_b: Decimal | None
    if use_ladder:
        level_a = history.best_back_at(a, seconds_before_off=seconds_before_off)
        level_b = history.best_back_at(b, seconds_before_off=seconds_before_off)
        if level_a is None or level_b is None:
            return None
        price_a, price_b = level_a.price, level_b.price
        size_a, size_b = level_a.size, level_b.size
    else:
        price_a = history.ltp_at(a, seconds_before_off=seconds_before_off)
        price_b = history.ltp_at(b, seconds_before_off=seconds_before_off)
        if price_a is None or price_b is None:
            return None

    result = devig((float(price_a), float(price_b)), DEVIG_METHOD)
    return ExchangeQuote(
        selection_a=a, selection_b=b, price_a=price_a, price_b=price_b,
        probability_a=result.probabilities[0], probability_b=result.probabilities[1],
        seconds_before_off=seconds_before_off,
        raw_overround=1.0 / float(price_a) + 1.0 / float(price_b),
        crossable=use_ladder, size_a=size_a, size_b=size_b,
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
