"""CROSS_MARKET_COHERENCE_V1 — PRODUCTION derived-market quantities from a MatchDistribution
(STAGE3-0005 §9). SYNTHETIC-ONLY, deterministic.

Given the total-games and game-margin PMFs (integer support) produced by ``match.py``, computes
the Over/Under total-games probabilities and the Asian game-handicap cover probabilities at a
governed line. Integer lines carry an explicit PUSH mass; half-lines carry none. Lines are exact
(``Decimal`` restricted to multiples of 0.5) — there is no float line arithmetic and no silent
rounding. Reads NO market prices and NO outcomes. Import-quarantined from execution/pricing/V0.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sport_tennis.coherence.scoring import CoherenceMathError, check_normalized

_HALF = Decimal("0.5")


def _validate_line(line: Decimal) -> None:
    """A line MUST be a multiple of 0.5 (integer line -> push possible; half-line -> no push)."""
    if not isinstance(line, Decimal):
        raise CoherenceMathError(f"line must be a Decimal, got {type(line).__name__}")
    if (line * 2) != (line * 2).to_integral_value():
        raise CoherenceMathError(f"line must be a multiple of 0.5, got {line}")


def _validate_pmf(pmf: dict[int, float]) -> None:
    if not pmf:
        raise CoherenceMathError("empty PMF")
    check_normalized(sum(pmf.values()), what="PMF")


@dataclass(frozen=True)
class OverUnder:
    """Over/Under decomposition at a total-games line. ``push`` is non-zero only for an integer
    line; the three sum to 1."""

    line: Decimal
    over: float
    under: float
    push: float


@dataclass(frozen=True)
class HandicapCover:
    """Asian game-handicap decomposition for player A carrying handicap ``line`` (A covers when
    margin_A_minus_B + line > 0). ``push`` is non-zero only for an integer line; the three
    sum to 1."""

    line: Decimal
    a_covers: float
    b_covers: float
    push: float


def over_under(total_games_pmf: dict[int, float], line: Decimal) -> OverUnder:
    """Over/Under total-games probabilities at ``line``. Over wins when total > line; Under when
    total < line; push (integer line only) when total == line."""
    _validate_line(line)
    _validate_pmf(total_games_pmf)
    over = sum(pr for t, pr in total_games_pmf.items() if Decimal(t) > line)
    under = sum(pr for t, pr in total_games_pmf.items() if Decimal(t) < line)
    push = sum(pr for t, pr in total_games_pmf.items() if Decimal(t) == line)
    return OverUnder(line=line, over=over, under=under, push=push)


def handicap_cover(margin_pmf: dict[int, float], line: Decimal) -> HandicapCover:
    """Asian game-handicap cover probabilities for player A carrying ``line`` (games handicap on
    A). A covers when (margin_A_minus_B + line) > 0; B covers when < 0; push (integer line only)
    when == 0. A line of e.g. -3.5 means A must win by 4+ games to cover."""
    _validate_line(line)
    _validate_pmf(margin_pmf)
    a_covers = sum(pr for m, pr in margin_pmf.items() if Decimal(m) + line > 0)
    b_covers = sum(pr for m, pr in margin_pmf.items() if Decimal(m) + line < 0)
    push = sum(pr for m, pr in margin_pmf.items() if Decimal(m) + line == 0)
    return HandicapCover(line=line, a_covers=a_covers, b_covers=b_covers, push=push)


def expected_total_games(total_games_pmf: dict[int, float]) -> float:
    _validate_pmf(total_games_pmf)
    return sum(t * pr for t, pr in total_games_pmf.items())


def expected_margin(margin_pmf: dict[int, float]) -> float:
    _validate_pmf(margin_pmf)
    return sum(m * pr for m, pr in margin_pmf.items())
