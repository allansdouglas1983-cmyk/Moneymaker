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
    "SetBettingView",
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
