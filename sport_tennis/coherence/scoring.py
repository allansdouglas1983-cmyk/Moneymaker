"""CROSS_MARKET_COHERENCE_V1 — PRODUCTION scoring generator (STAGE3-0005 §9/§12).

SYNTHETIC-ONLY, deterministic. Given per-player serve-point-win probabilities and an explicit
format, computes game / tiebreak / set / match probabilities and the total-games and
game-margin PMFs by dynamic programming (no unbounded recursion; exact closed-form tails for
the win-by-two regions; normalized PMFs). Reads NO market prices and NO outcomes. A test-only
independent reference (``reference.py``) must agree with everything here over a governed grid;
a discrepancy is STOP_MATH_INTEGRITY. Import-quarantined from execution/pricing/V0.
"""
from __future__ import annotations

from dataclasses import dataclass

from sport_tennis.coherence.formats import FormatSpec, set_tiebreak_target

_EPS = 1e-12


class CoherenceMathError(Exception):
    """A synthetic math input/domain is invalid — refuse, never guess."""


def _check_p(name: str, p: float) -> None:
    if not isinstance(p, float) or not (0.0 < p < 1.0):
        raise CoherenceMathError(f"{name} must be a float in the open interval (0,1), got {p!r}")


# ------------------------------------------------------------------------- serve order
def tiebreak_server_is_first(point_index: int) -> bool:
    """True if the player who served the tiebreak's first point serves ``point_index``
    (1-indexed). Order: first serves point 1; then serve alternates in pairs (2,3 other;
    4,5 first; 6,7 other; ...)."""
    if point_index == 1:
        return True
    return ((point_index - 2) // 2) % 2 == 1


# ------------------------------------------------------------------------------- game
def game_win_prob(p: float) -> float:
    """Probability the server wins an advantage game given serve-point-win probability p."""
    _check_p("p", p)
    q = 1.0 - p
    memo: dict[tuple[int, int], float] = {}

    def g(s: int, r: int) -> float:
        if s >= 4 and s - r >= 2:
            return 1.0
        if r >= 4 and r - s >= 2:
            return 0.0
        if s >= 3 and r >= 3 and s == r:                 # deuce
            return p * p / (p * p + q * q)
        key = (s, r)
        if key in memo:
            return memo[key]
        v = p * g(s + 1, r) + q * g(s, r + 1)
        memo[key] = v
        return v

    return g(0, 0)


# --------------------------------------------------------------------------- tiebreak
def tiebreak_win_prob(p_first: float, p_other: float, target: int) -> float:
    """Probability the first-server wins a first-to-``target`` (win-by-2) tiebreak, given each
    player's serve-point-win probability. ``target`` is 7 or 10."""
    _check_p("p_first", p_first)
    _check_p("p_other", p_other)
    if target not in (7, 10):
        raise CoherenceMathError(f"tiebreak target must be 7 or 10, got {target}")

    def first_point_win(n: int) -> float:
        return p_first if tiebreak_server_is_first(n) else (1.0 - p_other)

    # deuce tail at (target-1, target-1): two-point cycle using the ACTUAL servers there
    n0 = 2 * (target - 1) + 1
    x, y = first_point_win(n0), first_point_win(n0 + 1)
    ff, oo = x * y, (1.0 - x) * (1.0 - y)
    deuce_first = 0.5 if (ff + oo) < _EPS else ff / (ff + oo)

    memo: dict[tuple[int, int], float] = {}

    def tb(a: int, b: int) -> float:
        if a >= target and a - b >= 2:
            return 1.0
        if b >= target and b - a >= 2:
            return 0.0
        if a == target - 1 and b == target - 1:
            return deuce_first
        key = (a, b)
        if key in memo:
            return memo[key]
        n = a + b + 1
        w = first_point_win(n)
        v = w * tb(a + 1, b) + (1.0 - w) * tb(a, b + 1)
        memo[key] = v
        return v

    return tb(0, 0)


# ------------------------------------------------------------------------------- set
@dataclass(frozen=True)
class SetResult:
    """Distribution over a set's terminal game score (games_first, games_other), where
    "first" is the player who served the set's first game. ``first_server_wins`` is the
    marginal set-win probability for that player."""

    games: dict[tuple[int, int], float]
    first_server_wins: float


def _set_terminal(a: int, b: int) -> bool:
    """True if game score (a,b) ends the set (6-0..6-4 / 7-5 mirrors). 6-6 is NOT terminal
    (a tiebreak follows); 7-6 is produced only by that tiebreak."""
    if a >= 6 and a - b >= 2:
        return True
    if b >= 6 and b - a >= 2:
        return True
    return (a == 7 and b == 5) or (a == 5 and b == 7)


def set_distribution(p_first: float, p_other: float, spec: FormatSpec, *,
                     is_final_set: bool) -> SetResult:
    """Single-set distribution by forward DP. The "first" player serves games 1,3,5,...; the
    server alternates each game. At 6-6 a tiebreak (7 normally; 10 in the final set for the
    *_FINAL_AT_6_6 formats) decides a 7-6 set."""
    _check_p("p_first", p_first)
    _check_p("p_other", p_other)
    hold_first = game_win_prob(p_first)
    hold_other = game_win_prob(p_other)
    tb_target = set_tiebreak_target(spec, is_final_set=is_final_set)
    tb_first_wins = tiebreak_win_prob(p_first, p_other, tb_target)

    games: dict[tuple[int, int], float] = {}
    level: dict[tuple[int, int], float] = {(0, 0): 1.0}
    while level:
        nxt: dict[tuple[int, int], float] = {}
        for (a, b), pr in level.items():
            if (a, b) == (6, 6):
                games[(7, 6)] = games.get((7, 6), 0.0) + pr * tb_first_wins
                games[(6, 7)] = games.get((6, 7), 0.0) + pr * (1.0 - tb_first_wins)
                continue
            game_no = a + b + 1                      # the game about to be played
            server_is_first = (game_no % 2 == 1)
            hold = hold_first if server_is_first else hold_other
            p_first_wins_game = hold if server_is_first else (1.0 - hold)
            for na, nb, branch in ((a + 1, b, p_first_wins_game),
                                   (a, b + 1, 1.0 - p_first_wins_game)):
                if _set_terminal(na, nb):
                    games[(na, nb)] = games.get((na, nb), 0.0) + pr * branch
                else:
                    nxt[(na, nb)] = nxt.get((na, nb), 0.0) + pr * branch
        level = nxt

    total = sum(games.values())
    if abs(total - 1.0) > 1e-9:
        raise CoherenceMathError(f"set distribution does not normalize (sum={total})")
    first_wins = sum(pr for (a, b), pr in games.items() if a > b)
    return SetResult(games=games, first_server_wins=first_wins)
