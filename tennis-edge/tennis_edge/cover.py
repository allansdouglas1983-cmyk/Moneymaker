"""Buy the whole outcome space as cheaply as possible, from whichever markets sell it.

TE-0009 checked one pair of markets and found them coherent. This is the complete form of
that question, and it cannot be improved on by adding another pair.

Match Odds, Set Betting and Number of Sets are all **partitions of the same space** — the
final set score. A best-of-three ends exactly one of four ways, and every runner in every one
of those markets pays out on some subset of the four:

    MATCH_ODDS      "A"            -> {A 2-0, A 2-1}
    SET_BETTING     "A 2-1"        -> {A 2-1}
    NUMBER_OF_SETS  "Three Sets"   -> {A 2-1, B 2-1}

So any selection of runners whose subsets are disjoint and together cover all four is a
guaranteed position, whichever markets those runners came from. Searching every such cover
and keeping the cheapest asks the strongest available version of "do these markets agree" —
a two-market check can only find a mispricing visible between those two books, while this
finds the cheapest way to buy the space at all.

**Two ways an exact cover lies, and both are refused rather than scored.** A selection that
*misses* an outcome is unhedged, and it looks most profitable exactly when it is most
dangerous, because the uncovered outcome is the one whose price it did not have to pay. A
selection that covers an outcome *twice* has paid for it twice; that is merely wrong rather
than dangerous, but it is still not a lock. Only exact covers are considered.

Size is carried through from :mod:`tennis_edge.xmarket` for the reason recorded there: a
best-back price with nothing behind it is not a price, and taking those at face value is how
an earlier scan reported a six-hundred-percent guaranteed return.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from tennis_edge.xmarket import MINIMUM_LEG_SIZE, Leg, parse_set_runner, surname_of

__all__ = [
    "Outcome",
    "Cover",
    "outcome_space",
    "covered_outcomes",
    "best_cover",
]

#: ``(side, sets won by the winner, sets lost)``. Sides are the literal strings the caller
#: uses for the two players, so a cover is always expressed in the caller's orientation.
Outcome = tuple[str, int, int]

#: Runner names in NUMBER_OF_SETS. Spelled out rather than numeric on Betfair.
_LENGTH_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5}
_LENGTH = re.compile(r"^(?P<word>two|three|four|five)\s+sets$", re.IGNORECASE)


@dataclass(frozen=True)
class Cover:
    """An exact cover of the outcome space, and what it would return."""

    legs: tuple[tuple[frozenset[Outcome], Leg], ...]
    unit_return: float
    max_total_stake: float


def outcome_space(best_of: int) -> set[Outcome]:
    """Every way the match can finish, as ``(winner, sets won, sets lost)``."""
    if best_of not in (3, 5):
        raise ValueError(f"best_of must be 3 or 5, got {best_of}")
    needed = best_of // 2 + 1
    return {(side, needed, lost)
            for side in ("A", "B")
            for lost in range(needed)}


def covered_outcomes(
    market_type: str, runner: str, *, sides: tuple[str, str], best_of: int
) -> set[Outcome] | None:
    """Which outcomes this runner pays out on, or ``None`` if it cannot be classified.

    ``None`` covers everything from an unsupported market type to a runner naming a match
    length the format cannot produce ("Five Sets" on a best-of-three, which means the two
    markets are not describing the same match). Refusing is the only safe answer: a runner
    silently mapped to an empty set would let an incomplete selection look like a full cover.
    """
    space = outcome_space(best_of)
    kind = market_type.upper()

    if kind == "MATCH_ODDS":
        key = surname_of(runner)
        for label, name in zip(("A", "B"), sides):
            if surname_of(name) == key:
                return {o for o in space if o[0] == label}
        return None

    if kind == "SET_BETTING":
        parsed = parse_set_runner(runner)
        if parsed is None:
            return None
        name, won, lost = parsed
        key = surname_of(name)
        for label, side in zip(("A", "B"), sides):
            if surname_of(side) == key:
                outcome = (label, won, lost)
                return {outcome} if outcome in space else None
        return None

    if kind == "NUMBER_OF_SETS":
        match = _LENGTH.match(runner.strip())
        if match is None:
            return None
        total = _LENGTH_WORDS[match.group("word").lower()]
        found = {o for o in space if o[1] + o[2] == total}
        return found or None

    return None


def _net(price: Decimal, commission: Decimal) -> Decimal:
    return Decimal(1) + (price - Decimal(1)) * (Decimal(1) - commission)


def best_cover(
    candidates: Sequence[tuple[frozenset[Outcome], Leg]],
    space: set[Outcome],
    *,
    commission: Decimal,
    minimum_size: float = MINIMUM_LEG_SIZE,
) -> Cover | None:
    """The cheapest exact cover of ``space``, or ``None`` if none can be built.

    Exhaustive search with pruning. The space is four or six outcomes and the candidate list
    is a handful of runners, so the exact answer is cheap and there is no reason to
    approximate it. The recursion always covers the *lowest uncovered outcome* next, which
    makes each cover reachable by exactly one path and removes the need to deduplicate.

    Legs below ``minimum_size`` are dropped before the search rather than penalised: a leg
    that cannot be taken is not a worse leg, it is not a leg.
    """
    usable = [(outcomes, leg) for outcomes, leg in candidates
              if leg.size >= minimum_size and leg.price > 1 and outcomes <= space]
    if not usable:
        return None
    ordered = sorted(space)
    weights = [float(Decimal(1) / _net(leg.price, commission)) for _o, leg in usable]

    best: list[int] | None = None
    best_cost = float("inf")

    def search(remaining: frozenset[Outcome], chosen: list[int], cost: float) -> None:
        nonlocal best, best_cost
        if cost >= best_cost:
            return
        if not remaining:
            best, best_cost = list(chosen), cost
            return
        target = next(o for o in ordered if o in remaining)
        for index, (outcomes, _leg) in enumerate(usable):
            if target not in outcomes or not outcomes <= remaining:
                continue
            chosen.append(index)
            search(remaining - outcomes, chosen, cost + weights[index])
            chosen.pop()

    search(frozenset(space), [], 0.0)
    if best is None:
        return None

    legs = tuple(usable[i] for i in best)
    caps = [usable[i][1].size / weights[i] for i in best]
    return Cover(
        legs=legs,
        unit_return=float(Decimal(1) / Decimal(str(best_cost)) - Decimal(1)),
        max_total_stake=min(caps) * best_cost,
    )
