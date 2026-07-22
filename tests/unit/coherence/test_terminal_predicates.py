"""STAGE3-0006 §5.7 — pure terminal predicates with exhaustive truth tables.

Extracts the game / tiebreak / set terminal predicates into pure functions and pins their EXACT
truth value over the complete bounded integer domain the engine uses. Independent oracles (built
from the tennis rules, not by copying the production boolean expression verbatim) make every
operator substitution — subtraction↔addition, ≥↔≠, win-by-two↔win-by-one, or↔and, and the
7-5/5-7 constants — a truth-table mismatch, so those mutants cannot survive.
"""
from __future__ import annotations

import pytest

from sport_tennis.coherence.scoring import (
    game_is_deuce,
    game_is_loss,
    game_is_win,
    set_is_terminal,
    set_is_tiebreak_state,
    tiebreak_is_loss,
    tiebreak_is_tail,
    tiebreak_is_win,
)

_DOMAIN = range(0, 9)


# ------- independent oracles (win-by-two reached-threshold semantics, stated explicitly) -------
def _oracle_game_win(s: int, r: int) -> bool:
    return s in (4, 5, 6, 7, 8) and s - r in (2, 3, 4, 5, 6, 7, 8)


def _oracle_game_loss(s: int, r: int) -> bool:
    return _oracle_game_win(r, s)


def _oracle_game_deuce(s: int, r: int) -> bool:
    return s == r and s >= 3


def _oracle_tb_win(a: int, b: int, target: int) -> bool:
    return a >= target and (a - b) >= 2


def _oracle_tb_loss(a: int, b: int, target: int) -> bool:
    return _oracle_tb_win(b, a, target)


def _oracle_tb_tail(a: int, b: int, target: int) -> bool:
    return a == target - 1 and b == target - 1


def _oracle_set_terminal(a: int, b: int) -> bool:
    lead2_six = (a >= 6 and a - b >= 2) or (b >= 6 and b - a >= 2)
    seven_five = (a, b) in {(7, 5), (5, 7)}
    return lead2_six or seven_five


# ------------------------------------------------------------------------- game
def test_game_terminal_truth_table() -> None:
    for s in _DOMAIN:
        for r in _DOMAIN:
            assert game_is_win(s, r) is _oracle_game_win(s, r), (s, r)
            assert game_is_loss(s, r) is _oracle_game_loss(s, r), (s, r)
            assert game_is_deuce(s, r) is _oracle_game_deuce(s, r), (s, r)


# --------------------------------------------------------------------- tiebreak
@pytest.mark.parametrize("target", [7, 10])
def test_tiebreak_terminal_truth_table(target: int) -> None:
    for a in range(0, target + 3):
        for b in range(0, target + 3):
            assert tiebreak_is_win(a, b, target) is _oracle_tb_win(a, b, target), (a, b, target)
            assert tiebreak_is_loss(a, b, target) is _oracle_tb_loss(a, b, target), (a, b, target)
            assert tiebreak_is_tail(a, b, target) is _oracle_tb_tail(a, b, target), (a, b, target)


# -------------------------------------------------------------------------- set
def test_set_terminal_truth_table() -> None:
    for a in _DOMAIN:
        for b in _DOMAIN:
            assert set_is_terminal(a, b) is _oracle_set_terminal(a, b), (a, b)
            assert set_is_tiebreak_state(a, b) is (a == 6 and b == 6), (a, b)


def test_set_seven_five_and_six_six_specifics() -> None:
    # explicit anchors the founder called out
    assert set_is_terminal(7, 5) is True
    assert set_is_terminal(5, 7) is True
    assert set_is_terminal(6, 6) is False            # 6-6 is NOT terminal (tiebreak follows)
    assert set_is_tiebreak_state(6, 6) is True
    assert set_is_terminal(7, 6) is False            # 7-6 comes only via the tiebreak branch
