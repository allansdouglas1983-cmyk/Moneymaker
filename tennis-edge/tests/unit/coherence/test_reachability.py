"""STAGE3-0006 §5.6 — reachable-state proof for the coherence DPs.

Reports the exact reachable / terminal / unreachable state sets (via the independent enumerator)
and proves the boundedness facts that make the surviving terminal-guard comparison mutants
equivalent ON THE REACHABLE STATE SET: the game never reaches a server score above 4, the
tiebreak never reaches a score above the target, and the set never reaches 8-x or 7-4. Only with
this complete enumeration may such a mutant be classified as unreachable-domain equivalence.
"""
from __future__ import annotations

import pytest

from sport_tennis.coherence.scoring import (
    game_is_loss,
    game_is_win,
    set_is_terminal,
    tiebreak_is_loss,
    tiebreak_is_win,
)
from tests.unit.coherence.reachability import (
    game_reachability,
    set_reachability,
    tiebreak_reachability,
)


# ------------------------------------------------------------------------- game
def test_game_reachable_bounded_and_win_guard_tight_on_reachable() -> None:
    g = game_reachability()
    assert max(s for s, _ in g.reachable) == 4          # server score never exceeds 4
    assert max(r for _, r in g.reachable) == 4
    assert (5, 3) not in g.reachable                     # the classic unreachable post-adv state
    # On the reachable set, `s >= 4` holds iff `s == 4`, so the >=4 -> ==4 mutant is equivalent:
    for s, r in g.reachable:
        assert (s >= 4) == (s == 4)
        assert (r >= 4) == (r == 4)
        # and the production predicates equal their reachable-tightened forms
        assert game_is_win(s, r) == (s == 4 and s - r >= 2)
        assert game_is_loss(s, r) == (r == 4 and r - s >= 2)


# --------------------------------------------------------------------- tiebreak
@pytest.mark.parametrize("target", [7, 10])
def test_tiebreak_reachable_bounded_and_guard_tight(target: int) -> None:
    t = tiebreak_reachability(target)
    assert max(a for a, _ in t.reachable) == target      # never exceeds the target
    assert max(b for _, b in t.reachable) == target
    assert (target + 1, target - 1) not in t.reachable
    for a, b in t.reachable:
        assert (a >= target) == (a == target)
        assert tiebreak_is_win(a, b, target) == (a == target and a - b >= 2)
        assert tiebreak_is_loss(a, b, target) == (b == target and b - a >= 2)


# -------------------------------------------------------------------------- set
def test_set_reachable_terminal_and_unreachable_sets() -> None:
    s = set_reachability()
    expected_terminal = {
        (6, 0), (6, 1), (6, 2), (6, 3), (6, 4),
        (0, 6), (1, 6), (2, 6), (3, 6), (4, 6),
        (7, 5), (5, 7),
    }
    assert s.terminal == expected_terminal
    assert (6, 6) in s.reachable and (6, 6) not in s.terminal   # 6-6 reached but absorbing
    # explicit unreachable states the founder called out
    for unreachable in ((8, 4), (8, 0), (7, 4), (7, 3), (9, 5)):
        assert unreachable not in s.reachable
    # every reachable terminal really is terminal per the production predicate
    for cell in s.terminal:
        assert set_is_terminal(*cell) is True


def test_set_reachable_states_are_valid_prefixes() -> None:
    s = set_reachability()
    # no reachable state exceeds 7 games for either player, and the only 7s are the 7-5/5-7/(6-6->)7-6 lines
    for a, b in s.reachable:
        assert a <= 7 and b <= 7
        if a == 7:
            assert b in (5, 6)     # 7-5 terminal or 7-6 via the 6-6 tiebreak (not in this DP)
        if b == 7:
            assert a in (5, 6)
