"""CROSS_MARKET_COHERENCE_V1 — TEST-ONLY independent reference generator (STAGE3-0005 §2.5/§12).

Independently structured re-derivations of the production scoring math, used ONLY to validate
``scoring.py`` over a governed grid. Different structure by construction: the game uses a
closed-form polynomial (vs the production DP), the tiebreak uses a truncated forward recursion
(vs the production closed-form deuce tail), and the set uses a backward recursion (vs the
production forward DP). A discrepancy is STOP_MATH_INTEGRITY.

This module MUST NOT be imported by production code (test-only).
"""
from __future__ import annotations

from sport_tennis.coherence.formats import FormatSpec
from sport_tennis.coherence.scoring import tiebreak_server_is_first


def ref_game_win_prob(p: float) -> float:
    """Closed-form advantage-game hold probability (independent of the production DP)."""
    q = 1.0 - p
    to_love_15_30 = p ** 4 * (1.0 + 4.0 * q + 10.0 * q * q)   # 4-0, 4-1, 4-2
    reach_deuce = 20.0 * p ** 3 * q ** 3                       # C(6,3) ways to 3-3
    win_from_deuce = p * p / (p * p + q * q)
    return to_love_15_30 + reach_deuce * win_from_deuce


def ref_tiebreak_win_prob(p_first: float, p_other: float, target: int, cap: int = 400) -> float:
    """Truncated forward recursion (no closed-form tail): play up to ``cap`` points; the
    residual mass beyond ``cap`` is < 1e-60 for any realistic split, so this agrees with the
    production closed-form deuce tail to machine precision while being a different structure."""
    def first_pt(n: int) -> float:
        return p_first if tiebreak_server_is_first(n) else (1.0 - p_other)

    memo: dict[tuple[int, int], float] = {}

    def tb(a: int, b: int) -> float:
        if a >= target and a - b >= 2:
            return 1.0
        if b >= target and b - a >= 2:
            return 0.0
        if a + b >= cap:
            return 0.5
        key = (a, b)
        if key in memo:
            return memo[key]
        w = first_pt(a + b + 1)
        v = w * tb(a + 1, b) + (1.0 - w) * tb(a, b + 1)
        memo[key] = v
        return v

    return tb(0, 0)


def ref_set_first_wins(p_first: float, p_other: float, spec: FormatSpec, *,
                       is_final_set: bool) -> float:
    """Backward recursion for the first server's set-win probability (independent of the
    production forward DP)."""
    hold_first = ref_game_win_prob(p_first)
    hold_other = ref_game_win_prob(p_other)
    tb_target = 10 if (is_final_set and spec.final_set_rule == "TB10_FINAL_AT_6_6") else 7
    tb = ref_tiebreak_win_prob(p_first, p_other, tb_target)

    memo: dict[tuple[int, int], float] = {}

    def s(a: int, b: int) -> float:
        if a >= 6 and a - b >= 2:
            return 1.0
        if b >= 6 and b - a >= 2:
            return 0.0
        if a == 7 and b == 5:
            return 1.0
        if a == 5 and b == 7:
            return 0.0
        if a == 6 and b == 6:
            return tb
        key = (a, b)
        if key in memo:
            return memo[key]
        game_no = a + b + 1
        server_first = (game_no % 2 == 1)
        hold = hold_first if server_first else hold_other
        p_first_wins_game = hold if server_first else (1.0 - hold)
        v = p_first_wins_game * s(a + 1, b) + (1.0 - p_first_wins_game) * s(a, b + 1)
        memo[key] = v
        return v

    return s(0, 0)
