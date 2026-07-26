"""STAGE3-0006 §5.8/§5.9 — set-DP level completeness + game-server parity.

§5.9 pins the exact server of the next game for every reachable set score (the parity seam).
§5.8 pins that the per-level expander processes EVERY state in a level — including a 6-6 tiebreak
state co-located with another live state — so the `continue -> break` mutant (which would skip the
rest of the level) is killed, and every terminal cell (not just the set-win marginal) is checked.
"""
from __future__ import annotations

import pytest

from sport_tennis.coherence.scoring import (
    _expand_set_level,
    set_game_server_is_first,
)


# ---------------------------------------------------------------- §5.9 server parity
def _oracle_server_is_first(a: int, b: int) -> bool:
    # game 1 (0 games played) is served by first; the server alternates each game.
    return (a + b) % 2 == 0


def test_game_server_parity_truth_table() -> None:
    for a in range(0, 13):
        for b in range(0, 13):
            assert set_game_server_is_first(a, b) is _oracle_server_is_first(a, b), (a, b)


# ---------------------------------------------------------- §5.8 level completeness
def test_expand_level_processes_every_state_including_six_six() -> None:
    # A level containing the 6-6 tiebreak state AND another live (5,5) state: BOTH must contribute.
    # A `continue -> break` mutant would process only the first dict entry and drop the rest.
    tb_first = 0.6
    level = {(6, 6): 0.4, (5, 5): 0.6}
    terminals, nxt = _expand_set_level(level, 0.8, 0.7, tb_first)
    # 6-6 contributes the two tiebreak terminals with its mass 0.4
    assert terminals[(7, 6)] == pytest.approx(0.4 * tb_first)
    assert terminals[(6, 7)] == pytest.approx(0.4 * (1.0 - tb_first))
    # 5-5 is NOT terminal -> it must expand into the next level (proving it was processed)
    assert nxt, "the (5,5) state was dropped — the loop did not process the whole level"
    assert sum(nxt.values()) == pytest.approx(0.6)          # all of (5,5)'s mass carried forward
    assert set(nxt) == {(6, 5), (5, 6)}


def test_expand_level_order_independent() -> None:
    # Same level, opposite insertion order: identical result (kills break, which is order-sensitive)
    tb_first = 0.55
    a = _expand_set_level({(6, 6): 0.3, (5, 5): 0.7}, 0.75, 0.65, tb_first)
    b = _expand_set_level({(5, 5): 0.7, (6, 6): 0.3}, 0.75, 0.65, tb_first)
    assert a[0] == b[0] and a[1] == b[1]


def test_expand_level_mass_conserved() -> None:
    level = {(5, 5): 1.0}
    terminals, nxt = _expand_set_level(level, 0.7, 0.6, 0.5)
    assert sum(terminals.values()) + sum(nxt.values()) == pytest.approx(1.0)
