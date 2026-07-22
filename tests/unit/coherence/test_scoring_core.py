"""STAGE3-0005 §12/§16 — game/tiebreak/set production vs independent reference agreement.

Synthetic-only. Property tests (finite, [0,1], monotonic, symmetric) plus production ==
reference agreement over a governed serve-probability grid. A discrepancy is STOP_MATH_INTEGRITY.
"""
from __future__ import annotations

import pytest

from sport_tennis.coherence import reference as R
from sport_tennis.coherence import scoring as S
from sport_tennis.coherence.formats import MatchFormat, format_spec

_GRID = [0.30, 0.40, 0.50, 0.55, 0.62, 0.75, 0.90]
_TOL = 1e-9


# --------------------------------------------------------------------------- game
def test_game_win_prob_finite_and_in_unit_interval() -> None:
    for p in _GRID:
        v = S.game_win_prob(p)
        assert 0.0 <= v <= 1.0


def test_game_win_prob_monotone_in_serve() -> None:
    vals = [S.game_win_prob(p) for p in _GRID]
    assert vals == sorted(vals)


def test_game_win_prob_half_is_half() -> None:
    assert S.game_win_prob(0.5) == pytest.approx(0.5, abs=_TOL)


def test_game_production_equals_reference() -> None:
    for p in _GRID:
        assert S.game_win_prob(p) == pytest.approx(R.ref_game_win_prob(p), abs=_TOL)


def test_game_refuses_out_of_range() -> None:
    for bad in (0.0, 1.0, -0.1, 1.2, 1):
        with pytest.raises(S.CoherenceMathError):
            S.game_win_prob(bad)


# ----------------------------------------------------------------------- tiebreak
@pytest.mark.parametrize("target", [7, 10])
def test_tiebreak_symmetric_players_is_half(target: int) -> None:
    assert S.tiebreak_win_prob(0.5, 0.5, target) == pytest.approx(0.5, abs=1e-9)


@pytest.mark.parametrize("target", [7, 10])
def test_tiebreak_production_equals_reference(target: int) -> None:
    for pf in _GRID:
        for po in _GRID:
            assert S.tiebreak_win_prob(pf, po, target) == pytest.approx(
                R.ref_tiebreak_win_prob(pf, po, target), abs=1e-9)


def test_tiebreak_complement_symmetry() -> None:
    # P(first wins | pf, po) == 1 - P(first wins | po, pf) with servers swapped is NOT trivially
    # true (serve order matters); but a stronger server-first should never do worse.
    strong = S.tiebreak_win_prob(0.80, 0.50, 7)
    weak = S.tiebreak_win_prob(0.50, 0.80, 7)
    assert strong > weak


def test_tiebreak_bad_target_refuses() -> None:
    with pytest.raises(S.CoherenceMathError):
        S.tiebreak_win_prob(0.6, 0.6, 5)


def test_tiebreak_serve_order_equals_independent_reference() -> None:
    # Production closed-form serve order vs the independent iterative reference, point by point.
    for n in range(1, 41):
        assert S.tiebreak_server_is_first(n) == R.ref_tiebreak_server_is_first(n)


# ---------------------------------------------------------------------------- set
_FORMATS = [MatchFormat.BO3_AD_TB7_ALL_SETS, MatchFormat.BO3_AD_TB10_FINAL_AT_6_6,
            MatchFormat.BO5_AD_TB10_FINAL_AT_6_6]


def test_set_distribution_normalizes_and_scores_valid() -> None:
    spec = format_spec(MatchFormat.BO3_AD_TB7_ALL_SETS)
    res = S.set_distribution(0.62, 0.58, spec, is_final_set=False)
    assert abs(sum(res.games.values()) - 1.0) < 1e-9
    for (a, b), pr in res.games.items():
        assert 0.0 <= pr <= 1.0
        assert S._set_terminal(a, b) or (a, b) in {(7, 6), (6, 7)}  # 7-6 comes via the tiebreak


@pytest.mark.parametrize("fmt", _FORMATS)
@pytest.mark.parametrize("final", [False, True])
def test_set_production_first_wins_equals_reference(fmt: MatchFormat, final: bool) -> None:
    spec = format_spec(fmt)
    for pf in (0.40, 0.55, 0.70):
        for po in (0.45, 0.60):
            prod = S.set_distribution(pf, po, spec, is_final_set=final).first_server_wins
            ref = R.ref_set_first_wins(pf, po, spec, is_final_set=final)
            assert prod == pytest.approx(ref, abs=1e-9)


def test_set_symmetric_players_half() -> None:
    spec = format_spec(MatchFormat.BO3_AD_TB7_ALL_SETS)
    res = S.set_distribution(0.6, 0.6, spec, is_final_set=False)
    assert res.first_server_wins == pytest.approx(0.5, abs=1e-9)
