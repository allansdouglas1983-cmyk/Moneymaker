"""STAGE3-0006 §4/§7 — FAST exact production-vs-reference agreement for mutation hardening.

The full ``test_match_production_equals_reference`` sweeps BO5 (an un-memoised ~6M-path
independent reference) and is far too slow to run once per mutant. This module gives an EXACT
agreement check that is cheap enough for mutation: the three BO3 format branches — normal-set
7-point tiebreak, deciding-set 10-point tiebreak, and the match-tiebreak-replaces-decider path —
each have a bounded (~50-terminal-score) set distribution, so the top-down reference costs only a
few thousand calls per case. It pins the match engine's exact win probability and both PMFs.

BO5's stw=3 structural correctness is covered separately and cheaply by the existing all-format
fast tests: ``test_match_pmfs_normalize`` (sum-to-1 over every format incl. BO5) and
``test_match_symmetric_players_half`` (equal servers -> exactly 0.5 over every format incl. BO5).
Together with these, the exact BO3 reference below distinguishes the match/pmf mutants without the
BO5 reference cost. Any surviving mutant that could ONLY manifest at BO5 is handled by targeted
addition, never by relaxing this file.
"""
from __future__ import annotations

import pytest

from sport_tennis.coherence import reference as R
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.match import match_distribution

_TOL = 1e-9

# The three BO3 branches (cheap reference). BO5 is intentionally excluded here (see module docstring).
_BO3_FORMATS = [
    MatchFormat.BO3_AD_TB7_ALL_SETS,
    MatchFormat.BO3_AD_TB10_FINAL_AT_6_6,
    MatchFormat.BO3_AD_MATCH_TB10_REPLACES_DECIDER,
]


def _pmf_close(a: dict[int, float], b: dict[int, float]) -> None:
    for k in set(a) | set(b):
        assert a.get(k, 0.0) == pytest.approx(b.get(k, 0.0), abs=_TOL), f"PMF mismatch at {k}"


@pytest.mark.parametrize("fmt", _BO3_FORMATS)
@pytest.mark.parametrize("a_first", [True, False])
def test_match_exact_vs_reference_bo3_fast(fmt: MatchFormat, a_first: bool) -> None:
    # Two asymmetric server pairs pin exact values (asymmetry defeats the p_a<->p_b swap mutants
    # that a symmetric pair would hide).
    for pa, pb in ((0.63, 0.57), (0.71, 0.66)):
        prod = match_distribution(pa, pb, fmt, a_serves_first_match=a_first)
        win, tot, mar = R.ref_match(pa, pb, fmt, a_serves_first_match=a_first)
        assert prod.match_win_a == pytest.approx(win, abs=_TOL)
        _pmf_close(prod.total_games_pmf, tot)
        _pmf_close(prod.margin_pmf, mar)


def test_match_distribution_serves_first_is_keyword_only() -> None:
    # match_distribution(..., *, a_serves_first_match): the `*` keyword-only marker. A `*`->`/`
    # (Mul_Div) signature mutant turns it into a positional-only marker, silently dropping the
    # keyword-only enforcement. Passing a_serves_first_match POSITIONALLY must raise TypeError under
    # the correct signature; the mutant would accept it.
    import pytest
    with pytest.raises(TypeError):
        match_distribution(0.6, 0.5, MatchFormat.BO3_AD_TB7_ALL_SETS, True)  # type: ignore[misc]
