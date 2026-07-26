"""Margin removal — turning quoted odds into probabilities.

This is the highest-leverage code in the repository and it is easy to get wrong. On the
largest public study of tennis market efficiency (68,361 Pinnacle-priced matches, 2015-2019)
the *choice of method here* moved the measured yield of backing every selection at the close
by **7.6 percentage points** — from -7.18% (no adjustment) through -2.73% (proportional) to
+0.47% (logarithmic). That is larger than the entire claimed edge of any published tennis
model. Pick the method deliberately, record which one produced a number, and never compare
two figures computed under different methods.

Proportional removal — the obvious `p_i = (1/o_i) / sum(1/o_j)` — assumes the bookmaker
spread its margin evenly across probability. It does not: margin is concentrated on
longshots, so proportional removal systematically **overstates** the longshot's true
probability and will manufacture an underdog edge that is not there. It is included because
it is the field's default and we need to reproduce other people's numbers, not because it
is right.

Every function takes raw decimal odds and returns probabilities summing to exactly 1.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from typing import Sequence

__all__ = [
    "DevigMethod",
    "DevigResult",
    "overround",
    "devig",
    "proportional",
    "multiplicative",
    "power",
    "shin",
    "DEFAULT_METHOD",
]

_TOL = 1e-12
_MAX_ITER = 200


@unique
class DevigMethod(Enum):
    """The margin-removal methods this system knows how to apply."""

    PROPORTIONAL = "PROPORTIONAL"
    MULTIPLICATIVE = "MULTIPLICATIVE"
    POWER = "POWER"
    SHIN = "SHIN"


#: What we use unless a caller deliberately asks otherwise. Power (a.k.a. logarithmic)
#: removal is the method that produced the near-zero yield on the reference study, i.e. the
#: one under which the market looks efficient rather than exploitable.
DEFAULT_METHOD = DevigMethod.POWER


@dataclass(frozen=True)
class DevigResult:
    """Probabilities plus the diagnostics that let you audit how they were produced."""

    probabilities: tuple[float, ...]
    method: DevigMethod
    overround: float
    parameter: float | None

    def __post_init__(self) -> None:
        total = sum(self.probabilities)
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"de-vigged probabilities must sum to 1, got {total!r}")


def _validate(odds: Sequence[float]) -> tuple[float, ...]:
    if len(odds) < 2:
        raise ValueError(f"need at least two prices to remove a margin, got {len(odds)}")
    out: list[float] = []
    for price in odds:
        value = float(price)
        if not value > 1.0:
            raise ValueError(f"decimal odds must exceed 1, got {price!r}")
        out.append(value)
    return tuple(out)


def overround(odds: Sequence[float]) -> float:
    """The bookmaker's book sum minus 1 — the gross margin on the market."""
    prices = _validate(odds)
    return sum(1.0 / p for p in prices) - 1.0


def proportional(odds: Sequence[float]) -> DevigResult:
    """Scale every implied probability by the same factor.

    Assumes margin is spread in proportion to probability. It is not; this overstates
    longshots. Kept for reproducing published figures, not for pricing decisions.
    """
    prices = _validate(odds)
    book = sum(1.0 / p for p in prices)
    return DevigResult(
        probabilities=tuple((1.0 / p) / book for p in prices),
        method=DevigMethod.PROPORTIONAL,
        overround=book - 1.0,
        parameter=None,
    )


def multiplicative(odds: Sequence[float]) -> DevigResult:
    """Alias of proportional under a different name in the literature.

    Reported separately so a result can state which name its author used, but the arithmetic
    is identical and the same longshot distortion applies.
    """
    result = proportional(odds)
    return DevigResult(
        probabilities=result.probabilities,
        method=DevigMethod.MULTIPLICATIVE,
        overround=result.overround,
        parameter=None,
    )


def power(odds: Sequence[float]) -> DevigResult:
    """Odds-proportional (logarithmic) removal: find k with ``sum((1/o_i)**k) == 1``.

    Each raw implied probability is below 1, so raising it to a power ``k > 1`` shrinks it —
    and shrinks the *smaller* one proportionally more. An overround book therefore solves to
    ``k > 1``, which takes proportionally more probability off the longshot than off the
    favourite. That is the empirically correct direction: bookmakers load margin onto
    longshots, and this is the method under which tennis closing prices come out almost
    perfectly calibrated.
    """
    prices = _validate(odds)
    raw = [1.0 / p for p in prices]
    book = sum(raw)
    if abs(book - 1.0) < _TOL:
        return DevigResult(tuple(raw), DevigMethod.POWER, book - 1.0, 1.0)

    def total(k: float) -> float:
        return float(sum(float(r) ** k for r in raw))

    # total(k) is strictly decreasing in k (every raw < 1), so bracket according to which
    # side of 1 the book sits: overround needs k > 1, underround needs k < 1.
    low, high = 1e-6, 1.0
    if total(1.0) > 1.0:
        low, high = 1.0, 2.0
        while total(high) > 1.0 and high < 1e6:
            high *= 2.0
    for _ in range(_MAX_ITER):
        mid = (low + high) / 2.0
        value = total(mid)
        if abs(value - 1.0) < _TOL:
            break
        if value > 1.0:
            low = mid
        else:
            high = mid
    k = (low + high) / 2.0
    probabilities = [r ** k for r in raw]
    scale = sum(probabilities)
    return DevigResult(
        probabilities=tuple(p / scale for p in probabilities),
        method=DevigMethod.POWER,
        overround=book - 1.0,
        parameter=k,
    )


def shin(odds: Sequence[float]) -> DevigResult:
    """Shin (1993): margin as compensation for a fraction ``z`` of insider money.

    Solves for the insider proportion z that makes the implied probabilities sum to 1 under

        p_i = ( sqrt(z**2 + 4*(1-z)*(1/o_i)**2 / book) - z ) / ( 2*(1-z) )

    Unlike the power method this has an economic story behind it, and it likewise shifts
    probability away from longshots. Useful as a cross-check: if a measured edge survives
    both Shin and power removal it is more likely to be real.
    """
    prices = _validate(odds)
    raw = [1.0 / p for p in prices]
    book = sum(raw)
    if abs(book - 1.0) < _TOL:
        return DevigResult(tuple(raw), DevigMethod.SHIN, book - 1.0, 0.0)

    def probabilities_for(z: float) -> list[float]:
        if z <= 0.0:
            return [r / book for r in raw]
        return [
            (((z * z + 4.0 * (1.0 - z) * (r * r) / book) ** 0.5) - z) / (2.0 * (1.0 - z))
            for r in raw
        ]

    low, high = 0.0, 0.99
    for _ in range(_MAX_ITER):
        mid = (low + high) / 2.0
        total = sum(probabilities_for(mid))
        if abs(total - 1.0) < _TOL:
            break
        if total > 1.0:
            low = mid
        else:
            high = mid
    z = (low + high) / 2.0
    values = probabilities_for(z)
    scale = sum(values)
    return DevigResult(
        probabilities=tuple(v / scale for v in values),
        method=DevigMethod.SHIN,
        overround=book - 1.0,
        parameter=z,
    )


_DISPATCH = {
    DevigMethod.PROPORTIONAL: proportional,
    DevigMethod.MULTIPLICATIVE: multiplicative,
    DevigMethod.POWER: power,
    DevigMethod.SHIN: shin,
}


def devig(odds: Sequence[float], method: DevigMethod = DEFAULT_METHOD) -> DevigResult:
    """Remove the margin from ``odds`` using ``method``."""
    return _DISPATCH[method](odds)
