"""Hierarchical Markov match model: P(point on serve) -> game -> tiebreak -> set -> match.

This is the classical tennis structure (Barnett & Clarke 2005; O'Malley 2008; Klaassen &
Magnus 2001/2003). It is genuinely different information from a rating: a rating summarises
who beat whom, whereas this consumes how points were won on serve, which is the first thing
in this system the betting market does not trivially already know.

Implemented as memoised recursions rather than the published closed forms, because the
recursions extend naturally to no-advantage games, first-to-10 match tiebreaks, advantage
final sets and arbitrary in-play scores. The closed forms are used as tests, which is the
right way round — a formula that only agrees with itself proves nothing.

The structural fact that governs everything downstream: match probability is driven almost
entirely by the *difference* between the two players' serve-point probabilities, not their
sum. Near the ATP norm of p ~ 0.62 the sensitivity is roughly five points of best-of-three
match probability per one point of difference. So pricing a match to +/-1% needs the
difference estimated to about +/-0.2 points, and a single match's serve percentage carries a
standard error near 5 points. Estimation noise, not the scoring model, is the binding
constraint — which is why :mod:`tennis_edge.serve_stats` shrinks so hard.
"""
from __future__ import annotations

from functools import lru_cache

__all__ = [
    "game_probability",
    "tiebreak_probability",
    "set_probability",
    "match_probability",
    "serve_difference_sensitivity",
]

_EPS = 1e-12


def _clamp(p: float) -> float:
    return min(max(p, _EPS), 1.0 - _EPS)


@lru_cache(maxsize=200_000)
def game_probability(p: float, *, no_advantage: bool = False) -> float:
    """P(server holds) given ``p`` = P(server wins a point on serve).

    ``no_advantage`` switches to a single deciding point at deuce, which is the scoring used
    in ATP doubles, NextGen and many Challenger/ITF events. Pricing those with the standard
    formula overstates holds — at p = 0.65 the break rate moves from 17% to 20%, which is not
    a rounding error.
    """
    p = _clamp(p)
    q = 1.0 - p

    @lru_cache(maxsize=None)
    def state(server: int, receiver: int) -> float:
        if server >= 4 and server - receiver >= 2:
            return 1.0
        if receiver >= 4 and receiver - server >= 2:
            return 0.0
        if server >= 3 and receiver >= 3:
            # Deuce: either one deciding point, or the classic two-clear geometric sum.
            if no_advantage:
                return p
            return (p * p) / (p * p + q * q)
        return p * state(server + 1, receiver) + q * state(server, receiver + 1)

    return state(0, 0)


@lru_cache(maxsize=200_000)
def tiebreak_probability(p_serve: float, p_return: float, *, target: int = 7) -> float:
    """P(player A wins the tiebreak) with A serving first.

    ``p_serve`` is A's point-win probability on his own serve; ``p_return`` is A's point-win
    probability on the opponent's serve. Serving alternates 1-2-2-2, which the recursion
    tracks from the point index rather than assuming.
    """
    p_serve = _clamp(p_serve)
    p_return = _clamp(p_return)

    @lru_cache(maxsize=None)
    def state(a: int, b: int) -> float:
        if a >= target and a - b >= 2:
            return 1.0
        if b >= target and b - a >= 2:
            return 0.0
        if a >= target and b >= target:
            # From parity, A must win a serve-and-return pair; otherwise return to parity.
            win_pair = p_serve * p_return
            lose_pair = (1.0 - p_serve) * (1.0 - p_return)
            denominator = win_pair + lose_pair
            if denominator <= _EPS:
                return 0.5
            return win_pair / denominator
        # A serves points 0, 3, 4, 7, 8, ... under the 1-2-2-2 alternation.
        a_serving = 2 <= (a + b + 3) % 4 <= 3
        p = p_serve if a_serving else p_return
        return p * state(a + 1, b) + (1.0 - p) * state(a, b + 1)

    return state(0, 0)


@lru_cache(maxsize=200_000)
def set_probability(
    p_serve: float, p_return: float, *, advantage_set: bool = False, no_advantage: bool = False
) -> float:
    """P(player A wins the set) with A serving the first game.

    ``advantage_set`` plays out 6-6 instead of a tiebreak (historic finals at some events).
    """
    hold = game_probability(p_serve, no_advantage=no_advantage)
    break_ = game_probability(1.0 - p_return, no_advantage=no_advantage)
    win_return_game = 1.0 - break_

    @lru_cache(maxsize=None)
    def state(a: int, b: int) -> float:
        if a >= 6 and a - b >= 2:
            return 1.0
        if b >= 6 and b - a >= 2:
            return 0.0
        if a == 6 and b == 6:
            return tiebreak_probability(p_serve, p_return)
        if advantage_set and a >= 5 and b >= 5 and a == b:
            # From parity in an advantage set: hold and break, or return to parity.
            win_pair = hold * win_return_game
            lose_pair = (1.0 - hold) * break_
            denominator = win_pair + lose_pair
            if denominator <= _EPS:
                return 0.5
            return win_pair / denominator
        a_serving = (a + b) % 2 == 0
        p = hold if a_serving else win_return_game
        return p * state(a + 1, b) + (1.0 - p) * state(a, b + 1)

    return state(0, 0)


def match_probability(
    p_serve: float,
    p_return: float,
    *,
    best_of: int = 3,
    advantage_final_set: bool = False,
    no_advantage: bool = False,
) -> float:
    """P(player A wins the match).

    Sets are treated as independent draws from :func:`set_probability`, the standard
    simplification: who serves first alternates by set, and modelling that explicitly moves
    the answer by far less than the error in estimating ``p_serve`` itself.
    """
    if best_of not in (3, 5):
        raise ValueError(f"tennis matches are best of 3 or 5, got {best_of}")
    per_set = set_probability(p_serve, p_return, no_advantage=no_advantage)
    final_set = (
        set_probability(p_serve, p_return, advantage_set=True, no_advantage=no_advantage)
        if advantage_final_set
        else per_set
    )
    needed = 2 if best_of == 3 else 3

    def state(a: int, b: int) -> float:
        if a == needed:
            return 1.0
        if b == needed:
            return 0.0
        decider = a == needed - 1 and b == needed - 1
        p = final_set if decider else per_set
        return p * state(a + 1, b) + (1.0 - p) * state(a, b + 1)

    return state(0, 0)


def serve_difference_sensitivity(
    pivot: float = 0.62, delta: float = 0.01, *, best_of: int = 3
) -> float:
    """Match-probability change per unit of serve-difference, near ``pivot``.

    Exposed because it is the number that decides how much estimation precision the serve
    model actually needs; it is used in tests to pin the model's leverage.
    """
    # The two evaluations sit at serve-differences of +delta and -delta, so the span is
    # 2*delta; dividing by delta alone would report twice the true derivative.
    high = match_probability(pivot + delta / 2.0, 1.0 - (pivot - delta / 2.0), best_of=best_of)
    low = match_probability(pivot - delta / 2.0, 1.0 - (pivot + delta / 2.0), best_of=best_of)
    return (high - low) / (2.0 * delta)
