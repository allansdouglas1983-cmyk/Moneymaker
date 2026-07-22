"""CROSS_MARKET_COHERENCE_V1 — TEST-ONLY independent reference generator (STAGE3-0005 §2.5/§12).

Independently structured re-derivations of the production scoring math, used ONLY to validate
``scoring.py`` over a governed grid. Different structure by construction: the game uses a
closed-form polynomial (vs the production DP), the tiebreak uses a truncated forward recursion
(vs the production closed-form deuce tail), and the set uses a backward recursion (vs the
production forward DP). A discrepancy is STOP_MATH_INTEGRITY.

This module MUST NOT be imported by production code (test-only).
"""
from __future__ import annotations

from collections import defaultdict

from sport_tennis.coherence.formats import FormatSpec, MatchFormat, format_spec


def ref_tiebreak_server_is_first(point_index: int) -> bool:
    """Independent serve-order re-derivation (iterative turn simulation, NOT the production
    closed form) so the tiebreak agreement test genuinely cross-checks production serve order.
    First server serves point 1 only; thereafter serve alternates every two points."""
    server_first = True
    points_left_in_turn = 1          # the first server's opening turn is a single point
    for _ in range(1, point_index):  # simulate transitions up to the queried point
        points_left_in_turn -= 1
        if points_left_in_turn == 0:
            server_first = not server_first
            points_left_in_turn = 2
    return server_first


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
        return p_first if ref_tiebreak_server_is_first(n) else (1.0 - p_other)

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


def ref_set_distribution(p_first: float, p_other: float, spec: FormatSpec, *,
                         is_final_set: bool) -> dict[tuple[int, int], float]:
    """Full terminal-game-score distribution for a set, by TOP-DOWN memoised recursion
    (independent of the production bottom-up forward DP). Returns {(games_first, games_other):
    prob}. Uses the independent game/tiebreak references throughout."""
    hold_first = ref_game_win_prob(p_first)
    hold_other = ref_game_win_prob(p_other)
    tb_target = 10 if (is_final_set and spec.final_set_rule == "TB10_FINAL_AT_6_6") else 7
    tb_first = ref_tiebreak_win_prob(p_first, p_other, tb_target)

    def is_terminal(a: int, b: int) -> bool:
        if a >= 6 and a - b >= 2:
            return True
        if b >= 6 and b - a >= 2:
            return True
        return (a == 7 and b == 5) or (a == 5 and b == 7)

    memo: dict[tuple[int, int], dict[tuple[int, int], float]] = {}

    def dist(a: int, b: int) -> dict[tuple[int, int], float]:
        if (a, b) == (6, 6):
            return {(7, 6): tb_first, (6, 7): 1.0 - tb_first}
        if is_terminal(a, b):
            return {(a, b): 1.0}
        key = (a, b)
        if key in memo:
            return memo[key]
        game_no = a + b + 1
        server_first = (game_no % 2 == 1)
        hold = hold_first if server_first else hold_other
        p_first_wins_game = hold if server_first else (1.0 - hold)
        out: dict[tuple[int, int], float] = defaultdict(float)
        for na, nb, branch in ((a + 1, b, p_first_wins_game),
                               (a, b + 1, 1.0 - p_first_wins_game)):
            for term, pv in dist(na, nb).items():
                out[term] += branch * pv
        memo[key] = dict(out)
        return memo[key]

    return dist(0, 0)


def ref_match(p_a: float, p_b: float, fmt: MatchFormat, *,
              a_serves_first_match: bool) -> tuple[float, dict[int, float], dict[int, float]]:
    """Depth-first re-derivation of the full-match distribution (independent of the production
    forward DP in match.py). Returns (match_win_a, total_games_pmf, margin_pmf), all in terms
    of the FIXED players A and B. Uses the independent set/tiebreak references throughout."""
    spec = format_spec(fmt)
    stw = spec.sets_to_win
    is_match_tb = spec.final_set_rule == "MATCH_TB10_REPLACES_DECIDER"

    match_win_a = 0.0
    total_pmf: dict[int, float] = defaultdict(float)
    margin_pmf: dict[int, float] = defaultdict(float)

    def recurse(sa: int, sb: int, af: bool, tot: int, mar: int, pr: float) -> None:
        nonlocal match_win_a
        is_decider = (sa == stw - 1 and sb == stw - 1)
        if is_match_tb and is_decider:
            a_win = ref_tiebreak_win_prob(p_a, p_b, 10) if af \
                else 1.0 - ref_tiebreak_win_prob(p_b, p_a, 10)
            credit = spec.match_tiebreak_games_credited_to_winner
            match_win_a += pr * a_win
            total_pmf[tot + credit] += pr
            margin_pmf[mar + credit] += pr * a_win
            margin_pmf[mar - credit] += pr * (1.0 - a_win)
            return
        sd = ref_set_distribution(p_a if af else p_b, p_b if af else p_a, spec,
                                  is_final_set=is_decider)
        for (gf, go), spr in sd.items():
            ga, gb = (gf, go) if af else (go, gf)
            games_in_set = gf + go
            a_won = ga > gb
            nsa, nsb = sa + (1 if a_won else 0), sb + (0 if a_won else 1)
            naf = af if (games_in_set % 2 == 0) else (not af)
            ntot, nmar = tot + games_in_set, mar + (ga - gb)
            p2 = pr * spr
            if nsa == stw:
                match_win_a += p2
                total_pmf[ntot] += p2
                margin_pmf[nmar] += p2
            elif nsb == stw:
                total_pmf[ntot] += p2
                margin_pmf[nmar] += p2
            else:
                recurse(nsa, nsb, naf, ntot, nmar, p2)

    recurse(0, 0, a_serves_first_match, 0, 0, 1.0)
    return match_win_a, dict(total_pmf), dict(margin_pmf)
