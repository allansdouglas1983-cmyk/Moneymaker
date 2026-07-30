"""Which bets fire — the firing rule with every knob exposed.

WHY THIS IS ITS OWN MODULE. Expected profit is ``sum(S_i * ev_i)``. A staking rule
chooses the weights ``S_i`` and can never change any ``ev_i``. Selection chooses which
``ev_i`` enter the sum at all, so it is the only lever that moves per-bet expectation;
sizing decides whether the programme survives long enough to collect what selection
earns. Optimising one while holding the other fixed answers the wrong question, because
the two interact: a threshold firing fewer bets makes each a larger share of a fixed risk
budget.

So both get swept, and neither is hard-coded here. This module makes no claim about which
settings are right — it is apparatus.

THE BAR IS COMMISSION-AWARE. ``break_even(O, c) = 1/(1+(O-1)(1-c))``. The naive bar
``1/O`` ignores commission and is optimistic by roughly half a probability point at these
prices, every time, in the same direction — the class of error that is invisible in a
backtest which makes it consistently.

Exact Decimal throughout. A firing threshold compared against a float-contaminated bar
fires a different set of bets from the one declared, and no test of the strategy would
reveal it.
"""
from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from tennis_edge.staking.engine import Candidate

__all__ = [
    "ProbabilitySource",
    "SelectionRule",
    "break_even",
    "edge_of",
]


class ProbabilitySource(enum.Enum):
    """Whose opinion drives the rule.

    ``MARKET`` is not a curiosity: it is the control reading every published measurement
    in this project carries. The identical rule fired off the market's own de-vigged
    probability answers "does the edge belong to the forecast, or to the disagreement
    between two venues' prices". If the source cannot be swapped, the control does not
    exist.
    """

    MODEL = "MODEL"
    MARKET = "MARKET"


def break_even(odds: Decimal, commission: Decimal) -> Decimal:
    """The win probability at which a back bet breaks even, net of commission.

    ``1/(1 + (O-1)(1-c))``. Floats are refused rather than coerced: a bar that is
    approximately right fires an approximately different strategy.
    """
    if not isinstance(odds, Decimal) or not isinstance(commission, Decimal):
        raise TypeError("break_even requires exact Decimal inputs, not float — a "
                        "float-contaminated bar fires a different set of bets than the "
                        "one declared, and nothing downstream can detect it")
    return Decimal(1) / (Decimal(1) + (odds - 1) * (Decimal(1) - commission))


def edge_of(candidate: Candidate, commission: Decimal,
            source: ProbabilitySource) -> Decimal:
    """How far this side's probability clears the commission-aware bar. May be negative."""
    probability = (candidate.p_model if source is ProbabilitySource.MODEL
                   else candidate.p_market)
    return probability - break_even(candidate.odds, commission)


@dataclass(frozen=True)
class SelectionRule:
    """Every firing knob, in one frozen place.

    Defaults are deliberately permissive — no odds band, no support requirement — so that
    a sweep starts from "fire everything above the bar" and each restriction has to earn
    its place by measurement rather than arriving as an unexamined inherited constant.
    """

    #: A bet fires when its edge is STRICTLY greater than this. Strict, declared, because
    #: >= and > give different bet counts and the difference shows up in no summary.
    min_edge: Decimal = Decimal("0")
    #: Inclusive band. Adjacent bands therefore partition rather than overlap.
    min_odds: Decimal | None = None
    max_odds: Decimal | None = None
    #: Fill-evidence verdicts to keep. None keeps every verdict, which is what a
    #: conventional backtest does — and saying so is the point of the option existing.
    require_support: tuple[str, ...] | None = None
    source: ProbabilitySource = ProbabilitySource.MODEL

    def fires(self, candidate: Candidate, commission: Decimal) -> bool:
        if self.min_odds is not None and candidate.odds < self.min_odds:
            return False
        if self.max_odds is not None and candidate.odds > self.max_odds:
            return False
        if self.require_support is not None and candidate.support not in self.require_support:
            return False
        return edge_of(candidate, commission, self.source) > self.min_edge

    def fired(self, candidates: Sequence[Candidate],
              commission: Decimal) -> list[Candidate]:
        """The subset that fires, in the order given, each at most once.

        Order and multiplicity are preserved deliberately. A rule that duplicated a
        candidate would double an exposure; one that reordered would change nothing today
        and would silently matter the moment a staking rule reads its own history.
        """
        return [c for c in candidates if self.fires(c, commission)]
