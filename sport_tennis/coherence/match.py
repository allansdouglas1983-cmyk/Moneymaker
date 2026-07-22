"""CROSS_MARKET_COHERENCE_V1 — PRODUCTION match engine + total-games / game-margin PMFs
(STAGE3-0005 §9/§12). SYNTHETIC-ONLY, deterministic.

Combines validated single-set distributions into a full match by a forward DP over
(sets_A, sets_B, who-serves-first-this-set, cumulative total games, cumulative A−B margin),
tracking the serve carry across sets. Produces the match-win probability and the total-games
and game-margin PMFs in terms of the FIXED players A and B. The BO3 match-tiebreak-decider
format replaces the deciding set with a 10-point tiebreak crediting a verified number of
games. Reads no prices, no outcomes. Import-quarantined.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sport_tennis.coherence.formats import (
    MatchFormat,
    format_spec,
    is_match_tiebreak_decider,
)
from sport_tennis.coherence.scoring import CoherenceMathError, set_distribution, tiebreak_win_prob


@dataclass(frozen=True)
class MatchDistribution:
    """Match-level distribution for fixed players A and B. Outcome-free (a probability model,
    not a result)."""

    match_win_a: float
    total_games_pmf: dict[int, float]     # total games played in the match
    margin_pmf: dict[int, float]          # games_A - games_B


def match_distribution(p_a: float, p_b: float, fmt: MatchFormat, *,
                       a_serves_first_match: bool) -> MatchDistribution:
    spec = format_spec(fmt)
    stw = spec.sets_to_win
    is_match_tb = is_match_tiebreak_decider(spec)

    match_win_a = 0.0
    total_pmf: dict[int, float] = defaultdict(float)
    margin_pmf: dict[int, float] = defaultdict(float)
    state: dict[tuple[int, int, bool, int, int], float] = {
        (0, 0, a_serves_first_match, 0, 0): 1.0}

    while state:
        nxt: dict[tuple[int, int, bool, int, int], float] = defaultdict(float)
        for (sa, sb, af, tot, mar), pr in state.items():
            is_decider = (sa == stw - 1 and sb == stw - 1)

            if is_match_tb and is_decider:
                a_win = tiebreak_win_prob(p_a, p_b, 10) if af \
                    else 1.0 - tiebreak_win_prob(p_b, p_a, 10)
                credit = spec.match_tiebreak_games_credited_to_winner
                match_win_a += pr * a_win
                total_pmf[tot + credit] += pr                     # winner gets `credit` games
                margin_pmf[mar + credit] += pr * a_win
                margin_pmf[mar - credit] += pr * (1.0 - a_win)
                continue

            if af:
                sr = set_distribution(p_a, p_b, spec, is_final_set=is_decider)
            else:
                sr = set_distribution(p_b, p_a, spec, is_final_set=is_decider)
            for (gf, go), spr in sr.games.items():
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
                    nxt[(nsa, nsb, naf, ntot, nmar)] += p2
        state = nxt

    tot_sum = sum(total_pmf.values())
    if abs(tot_sum - 1.0) > 1e-9:
        raise CoherenceMathError(f"match total-games PMF does not normalize (sum={tot_sum})")
    return MatchDistribution(match_win_a=match_win_a,
                             total_games_pmf=dict(total_pmf), margin_pmf=dict(margin_pmf))
