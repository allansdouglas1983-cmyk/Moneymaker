"""Cross-market coherence: Match Odds against Set Betting, on the same match.

Everything else in this package tries to **forecast better than the market**. Eight findings
say that is very hard and worth very little. This asks a completely different question, and
one the market can fail without anybody being wrong about tennis:

**do Betfair's own markets agree with each other?**

For a best-of-three, P(A wins the match) is *exactly* P(A wins 2-0) + P(A wins 2-1). That is
an identity, not a model. Detecting a gap between Match Odds and Set Betting needs no rating,
no serve statistics and no opinion — only arithmetic. If the two disagree, at least one of
them is wrong, and which one does not matter to someone taking both sides.

**Two quantities, and confusing them is the way this goes wrong.**

*Coherence gap* is measured on de-vigged probabilities. It says how much the two markets
disagree, and it is common — Set Betting is thinner and slower than Match Odds, so it drifts.

*Dutch return* is measured on the **actual best-back prices** and says whether the
disagreement can be transacted: back A in Match Odds, back every one of B's set scores, and
see whether the guaranteed return exceeds the outlay after commission. A gap is interesting;
a positive dutch return is the only thing that is worth anything, and reporting the first as
though it were the second would be the most flattering error available here.

**Why this is worth building even though most gaps will not be transactable.** The cost of
finding out is one pass over data already on disk, and unlike a forecasting edge, a
transactable incoherence does not have to survive an argument about whether the model is
better than the market. It either locks or it does not.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

__all__ = [
    "Leg",
    "align_sides",
    "FillableDutch",
    "MINIMUM_LEG_SIZE",
    "SetBettingView",
    "fillable_dutch",
    "parse_set_runner",
    "coherence_gap",
    "dutch_return",
]

#: ``"<name> 2-0"`` / ``"<name> 3-2"``. The name may contain spaces, so the score is anchored
#: to the end rather than found by splitting.
_RUNNER = re.compile(r"^(?P<name>.+?)\s+(?P<won>\d)-(?P<lost>\d)$")


@dataclass(frozen=True)
class SetBettingView:
    """What the Set Betting market implies about who wins, de-vigged to a distribution."""

    probability_a: float
    probability_b: float

    def __post_init__(self) -> None:
        total = self.probability_a + self.probability_b
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"set-betting view must sum to 1 across both players, got {total!r} — "
                f"an un-de-vigged book is a price, not a probability"
            )


def parse_set_runner(name: str) -> tuple[str, int, int] | None:
    """``("Bonzi", 2, 0)`` from ``"Bonzi 2-0"``, or ``None`` when it is not a set score.

    ``None`` for anything that does not carry a score — "Three Sets" from NUMBER_OF_SETS,
    a tournament winner, an empty string. Returning ``None`` rather than guessing keeps a
    runner nobody can classify out of the sum instead of silently attributing it to a player.
    """
    match = _RUNNER.match(name.strip())
    if match is None:
        return None
    return match.group("name"), int(match.group("won")), int(match.group("lost"))


def coherence_gap(*, match_odds_a: float, set_betting: SetBettingView) -> float:
    """How much Match Odds rates A above what Set Betting implies.

    Positive means Match Odds is the more bullish of the two on A. Both inputs must already
    be de-vigged — comparing a de-vigged probability with a raw one would report the
    market's own margin as a disagreement.
    """
    return match_odds_a - set_betting.probability_a


def dutch_return(
    *,
    match_odds_back_a: Decimal,
    set_back_prices_b: Sequence[Decimal],
    commission: Decimal,
) -> float:
    """Guaranteed return per unit outlay from backing A on Match Odds and all of B's scores.

    Every outcome is covered exactly once: A wins the match, or B wins it by one of the
    scorelines. Staking each leg in proportion to its inverse price equalises the payout, so
    the return is ``1 / Σ(1/O_i) − 1`` on the gross prices, with commission taken off the
    winnings of whichever leg lands.

    Negative is the normal answer and means the two markets are jointly overround. Positive
    means they disagree by more than it costs to trade the disagreement.

    An empty set-score leg raises. A partial book cannot be dutched, and treating a missing
    runner as though it did not exist would invent a lock out of an incomplete market — the
    single most dangerous mistake available in this file.
    """
    if not set_back_prices_b:
        raise ValueError("need at least one set-betting price for B to cover that side")
    legs = [match_odds_back_a, *set_back_prices_b]
    if any(o <= 1 for o in legs):
        raise ValueError(f"decimal odds must be above 1, got {[str(o) for o in legs]}")
    # Net odds after commission on winnings: 1 + (O-1)(1-c).
    net = [Decimal(1) + (o - Decimal(1)) * (Decimal(1) - commission) for o in legs]
    total_implied = sum(Decimal(1) / o for o in net)
    return float(Decimal(1) / total_implied - Decimal(1))


#: Smallest size on a leg that counts as a real price. Below this the quote exists but the
#: position does not: Set Betting books routinely show a nominal best back with a couple of
#: pounds behind it, and taking that number at face value is how the first version of this
#: scan reported a six-hundred-percent locked return.
MINIMUM_LEG_SIZE = 10.0


@dataclass(frozen=True)
class Leg:
    """One leg of a cross-market position: a price and the size actually available at it."""

    price: Decimal
    size: float


@dataclass(frozen=True)
class FillableDutch:
    """A position that could actually be built, and how large it could be."""

    unit_return: float
    max_total_stake: float
    limiting_leg: int


def fillable_dutch(
    legs: Sequence[Leg], *, commission: Decimal, minimum_size: float = MINIMUM_LEG_SIZE
) -> FillableDutch | None:
    """The position if every leg is genuinely takeable, else ``None``.

    Size limits *how much*, never *whether it is profitable* — the unit return is the same
    number :func:`dutch_return` gives for the same prices. What size decides is whether the
    position exists at all, and that is the question the price-only version cannot answer.

    Stakes are proportional to inverse net odds so every outcome pays the same. The position
    is therefore capped by whichever leg runs out of money first at that ratio, which is the
    leg reported.
    """
    if not legs:
        raise ValueError("need at least one leg")
    if any(leg.price <= 1 for leg in legs):
        raise ValueError(f"decimal odds must be above 1, got "
                         f"{[str(leg.price) for leg in legs]}")
    if any(leg.size < minimum_size for leg in legs):
        return None
    net = [Decimal(1) + (leg.price - Decimal(1)) * (Decimal(1) - commission)
           for leg in legs]
    weights = [float(Decimal(1) / o) for o in net]
    total_implied = sum(weights)
    # Scale the whole position until the first leg exhausts its available size.
    caps = [leg.size / w for leg, w in zip(legs, weights)]
    limiting = min(range(len(caps)), key=lambda i: caps[i])
    return FillableDutch(
        unit_return=float(Decimal(1) / Decimal(str(total_implied)) - Decimal(1)),
        max_total_stake=caps[limiting] * total_implied,
        limiting_leg=limiting,
    )


def align_sides(
    *, match_odds_names: Sequence[str], set_betting_names: Sequence[str]
) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
    """Set-betting indices grouped to match the Match Odds runner order, or ``None``.

    Returns ``(indices for match_odds_names[0], indices for match_odds_names[1])``.

    **This must be done by name, never by position or by sorting.** Betfair lists Match Odds
    runners in its own order and names the players inside the Set Betting runner strings; the
    two orders frequently disagree. Grouping set scores alphabetically and pairing them with
    Match Odds by position backs one player on Match Odds *and* that same player's set
    scores, covering one outcome twice and leaving the other uncovered. That is an unhedged
    double rather than a dutch, and it can report an arbitrarily large "guaranteed" return —
    which is exactly what it did.

    ``None`` whenever the two markets cannot be reconciled: an unparseable runner, a name
    that appears in one market and not the other, or a player with no scorelines. Refusing is
    the only safe answer, because an assumed alignment is invisible in the output.
    """
    if len(match_odds_names) != 2:
        return None
    parsed = [parse_set_runner(name) for name in set_betting_names]
    if any(p is None for p in parsed):
        return None
    grouped: dict[str, list[int]] = {}
    for index, entry in enumerate(parsed):
        assert entry is not None
        grouped.setdefault(entry[0], []).append(index)
    sides: list[tuple[int, ...]] = []
    for name in match_odds_names:
        indices = grouped.get(name.strip())
        if not indices:
            return None
        sides.append(tuple(indices))
    if len(grouped) != 2:
        return None
    return sides[0], sides[1]
