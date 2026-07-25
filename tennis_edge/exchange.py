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
    #: Sum of the raw implied probabilities. Above 1.0 is over-round, below is under-round;
    #: both occur on an exchange and neither is an error.
    raw_overround: float


def exchange_probability(
    history: MarketHistory, *, seconds_before_off: int
) -> ExchangeQuote | None:
    """De-vigged exchange probability at a horizon, or ``None`` if the market has no price.

    ``None`` means one or both sides had not traded by that horizon. It is never a guess and
    never substituted from the other side: a single traded side is not a market.
    """
    active = [r for r in history.runners if r.status.upper() == "ACTIVE"]
    if len(active) != 2:
        raise ValueError(
            f"market {history.market_id} has {len(active)} active runners; Match Odds is "
            "two active runners and a different count is a different choice set"
        )
    a, b = active[0].selection_id, active[1].selection_id
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
