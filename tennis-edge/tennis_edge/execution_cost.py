"""Roll (1984) effective-spread proxy from a market's own prints.

BASIC carries trades, not quotes, so the cost of actually crossing the book is unobserved.
DR-TENNIS-MICROSTRUCTURE-001's standard: a money number from this data needs an explicit
execution-cost sensitivity band, and the defensible transaction-only family is Roll's —
under a simple dealer model, buys and sells bounce between the two sides of an unobserved
spread, which makes successive price changes NEGATIVELY correlated, and the spread is
recoverable as ``2 * sqrt(-cov)``.

Computed on log-price changes, so the result is a relative spread (a fraction of the
price) and comparable across odds levels.

**A positive covariance refuses.** Trending prints carry no bounce to measure; the model's
assumption fails and the estimator is undefined there. Returning zero instead would assert
frictionless execution — the precise assumption the band exists to retire — so ``None`` it
is, and the caller reports coverage alongside the band.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tennis_edge.betfair import MarketHistory

__all__ = ["MIN_PRINTS", "haircut_odds", "roll_spread", "selection_spreads"]

#: Below this the serial covariance is noise. Chosen before any result was computed.
MIN_PRINTS = 6


def roll_spread(prices: Sequence[Decimal]) -> float | None:
    """Relative effective spread from a print series, or ``None`` where undefined."""
    if len(prices) < MIN_PRINTS:
        return None
    logs = [math.log(float(p)) for p in prices]
    changes = [b - a for a, b in zip(logs, logs[1:], strict=False)]
    if len(changes) < 2:
        return None
    mean = math.fsum(changes) / len(changes)
    pairs = list(zip(changes, changes[1:], strict=False))
    cov = math.fsum((x - mean) * (y - mean) for x, y in pairs) / len(pairs)
    if cov >= 0.0:
        return None
    return 2.0 * math.sqrt(-cov)


def selection_spreads(market: MarketHistory) -> dict[int, float | None]:
    """Roll spread per selection over the market's own pre-off trace.

    Each selection's print series is estimated alone. Pooling selections would difference
    prices of *different runners* — a level jump between runners, not a bounce across one
    spread — and the covariance it produces belongs to no market that exists. Every runner
    the market defined appears in the result; ``None`` where the estimator refuses.
    """
    series: dict[int, list[Decimal]] = {r.selection_id: [] for r in market.runners}
    for observation in market.observations:
        prints = series.get(observation.selection_id)
        if prints is not None:
            prints.append(observation.price)
    return {selection_id: roll_spread(prints)
            for selection_id, prints in series.items()}


def haircut_odds(odds: Decimal, spread: float, *, fraction: float) -> float:
    """Back odds after paying ``fraction`` of the relative spread, floored at evens.

    The haircut acts on log-price — ``odds * exp(-fraction * spread)`` — because the Roll
    estimate is itself a relative (log-price) spread. Half the spread is the symmetric
    dealer-model cost of crossing; the full spread is the pessimistic bound. Effective odds
    below 1.0 would make a *win* lose money, which is not a worse fill but an impossible
    one, so the floor stops the pessimistic bound at "a win returns the stake".
    """
    if spread < 0.0:
        raise ValueError(f"spread={spread} is negative; a spread is a width")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"fraction={fraction} outside [0, 1]; the band runs from "
                         "uncosted to one full spread, nothing beyond")
    return max(1.0, float(odds) * math.exp(-fraction * spread))
