"""The execution-cost band displayed with every edge (TE-0017 S6).

A displayed edge is a point; the adopted DR-TENNIS-MICROSTRUCTURE-001 standard says a
BASIC-derived money figure is shown with its execution-cost band or not shown. This module
is the deterministic conversion the site uses: the frozen Roll spread for the prediction's
stratum, applied as half-spread cost on the price, expressed as how far the commission-
aware break-even rises. The site renders the edge as ``[edge − band, edge]``.

**The frozen table.** Measured 2026-07-28 over the v4 price table's markets (46,169 with
a measurable Roll spread; 2,427 refusals, 5.0%, excluded rather than imputed). Per-market
spread is the WORSE side's estimate. The stratum key is the S5 staleness band — the only
serve-time-knowable liquidity signal in the system; each knowable stratum carries its p75,
and an unknown stratum (manual entry: the Betfair UI shows a price, not its age) takes the
pooled p90, which is wider than every knowable stratum's p75 by construction — the display
must never reward not looking. These constants are FROZEN: re-measuring them is a new
table with a new provenance note, never an in-place edit, and no observed return may tune
them.
"""
from __future__ import annotations

import math
from decimal import Decimal

from tennis_edge.upcoming import break_even_probability

__all__ = ["ROLL_BAND_TABLE", "band_spread", "edge_band"]

#: Relative Roll spread by S5 staleness band (p75), plus the pooled p90 fallback.
#: Provenance: roll_spreads_v2.jsonl x exchange_prices_600s_v4.jsonl, 2026-07-28.
ROLL_BAND_TABLE: dict[str, float] = {
    "<60s": 0.042520,
    "60-600s": 0.047880,
    ">600s": 0.054797,
    "pooled_p90": 0.077874,
}


def band_spread(staleness_band: str | None) -> float:
    """The frozen spread for a prediction's stratum; the conservative pooled fallback
    when the stratum is not knowable. A name outside the vocabulary raises — a typo must
    not silently become the fallback."""
    if staleness_band is None:
        return ROLL_BAND_TABLE["pooled_p90"]
    if staleness_band not in ("<60s", "60-600s", ">600s"):
        raise KeyError(f"unknown staleness band {staleness_band!r}")
    return ROLL_BAND_TABLE[staleness_band]


def edge_band(odds: Decimal, spread: float) -> float:
    """Probability points the edge loses to execution, at half the Roll spread.

    Crossing the book costs half the effective spread under the symmetric dealer model
    (the same central assumption TE-0020 adopted), so the effective odds are
    ``O * exp(-spread/2)`` and the band is how far the commission-aware break-even rises.
    Zero spread is zero band; a spread below zero or odds at or below evens are refused.
    """
    if spread < 0.0:
        raise ValueError(f"spread={spread} is negative; a spread is a width")
    if not float(odds) > 1.0:
        raise ValueError(f"odds={odds} are not bettable; the band needs a real price")
    if spread == 0.0:
        return 0.0
    effective = float(odds) * math.exp(-spread / 2.0)
    if effective <= 1.0:
        # The cost swallows the whole price: no probability clears it, break-even rises
        # to certainty, and the band is everything above the quoted break-even. A heavy
        # favourite at a thin price is exactly the case the band must speak on.
        return 1.0 - float(break_even_probability(odds))
    return (float(break_even_probability(Decimal(str(effective))))
            - float(break_even_probability(odds)))
