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
from decimal import Decimal
from typing import Sequence

__all__ = ["MIN_PRINTS", "roll_spread"]

#: Below this the serial covariance is noise. Chosen before any result was computed.
MIN_PRINTS = 6


def roll_spread(prices: Sequence[Decimal]) -> float | None:
    """Relative effective spread from a print series, or ``None`` where undefined."""
    if len(prices) < MIN_PRINTS:
        return None
    logs = [math.log(float(p)) for p in prices]
    changes = [b - a for a, b in zip(logs, logs[1:])]
    if len(changes) < 2:
        return None
    mean = math.fsum(changes) / len(changes)
    pairs = list(zip(changes, changes[1:]))
    cov = math.fsum((x - mean) * (y - mean) for x, y in pairs) / len(pairs)
    if cov >= 0.0:
        return None
    return 2.0 * math.sqrt(-cov)
