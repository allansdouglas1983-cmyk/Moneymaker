"""Independent reachable-state enumerator for the coherence DPs (TEST-ONLY, STAGE3-0006 §5.6).

Enumerates, by an independent forward walk of the state graph (its own inline terminal rules —
it imports NO production predicate), the exact reachable / terminal / unreachable state sets for
the advantage game, the tiebreak and the set. This is the complete reachable-state proof that
backs any "unreachable-domain" equivalence classification (§2.1): a comparison mutant on a
terminal guard is equivalent only if it agrees with the original on every REACHABLE state, which
these sets make checkable.

Not a test module itself; imported by ``test_reachability.py``.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

_Pred = Callable[[int, int], bool]


@dataclass(frozen=True)
class Reachability:
    reachable: frozenset[tuple[int, int]]     # every state the DP evaluates (incl. terminals)
    terminal: frozenset[tuple[int, int]]      # reachable states that end the unit
    expanded: frozenset[tuple[int, int]]      # reachable non-terminal states (recursed through)


def _walk(is_terminal: _Pred, is_absorbing_nonterminal: _Pred | None = None) -> Reachability:
    """Forward walk from (0,0): a state is expanded into (s+1,r) and (s,r+1) unless it is terminal
    or an absorbing non-terminal (e.g. the set 6-6 tiebreak state or the tiebreak win-by-two
    tail), which are reached but not expanded."""
    reachable: set[tuple[int, int]] = set()
    terminal: set[tuple[int, int]] = set()
    expanded: set[tuple[int, int]] = set()
    frontier = [(0, 0)]
    while frontier:
        s, r = frontier.pop()
        if (s, r) in reachable:
            continue
        reachable.add((s, r))
        if is_terminal(s, r):
            terminal.add((s, r))
            continue
        if is_absorbing_nonterminal is not None and is_absorbing_nonterminal(s, r):
            continue
        expanded.add((s, r))
        frontier.extend([(s + 1, r), (s, r + 1)])
    return Reachability(frozenset(reachable), frozenset(terminal), frozenset(expanded))


def game_reachability() -> Reachability:
    def terminal(s: int, r: int) -> bool:
        win = s >= 4 and s - r >= 2
        loss = r >= 4 and r - s >= 2
        deuce = s >= 3 and r >= 3 and s == r          # closed-form absorbing terminal
        return win or loss or deuce
    return _walk(terminal)


def tiebreak_reachability(target: int) -> Reachability:
    def terminal(a: int, b: int) -> bool:
        win = a >= target and a - b >= 2
        loss = b >= target and b - a >= 2
        tail = a == target - 1 and b == target - 1    # closed-form absorbing tail
        return win or loss or tail
    return _walk(terminal)


def set_reachability() -> Reachability:
    def terminal(a: int, b: int) -> bool:
        return (a >= 6 and a - b >= 2) or (b >= 6 and b - a >= 2) or (a, b) in {(7, 5), (5, 7)}

    def absorbing_six_six(a: int, b: int) -> bool:
        return a == 6 and b == 6                       # tiebreak decides it; not expanded further
    return _walk(terminal, absorbing_six_six)
