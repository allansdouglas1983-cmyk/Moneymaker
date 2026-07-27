"""The frozen decision rule that the weekly loop evaluates.

Deliberately plain, because nothing in this project has earned complexity. Four
architectures have been measured against the market and all four were flat, so the policy
treats the **market probability as the answer** and the model as a labelled challenger. A
recommendation only appears when the model disagrees with the price by more than a frozen
margin *and* the disagreement is still positive-expectation after commission at the price
actually recorded.

The expected outcome is that these recommendations lose. That is the point: the loop is
built to measure the rule honestly and would detect an edge if one ever appeared, rather
than to produce advice. Nothing here is a tip and nothing authorises a bet.

Every constant is part of :func:`policy_digest`. Changing one starts a new policy vintage
rather than quietly redefining the old one, so a ledger row can always be traced to the exact
rule that produced it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, unique
from typing import Mapping

from tennis_edge.corpus import Match
from tennis_edge.devig import DevigMethod
from tennis_edge.digests import digest_of

__all__ = [
    "POLICY_VERSION",
    "PREFERRED_BOOKS",
    "COMMISSION",
    "TIP_MARGIN",
    "WATCH_MARGIN",
    "MODEL_SHRINKAGE",
    "Status",
    "Decision",
    "policy_digest",
    "decide",
]

POLICY_VERSION = "frozen-policy-v1"

#: Books tried in order for the **reference price** — the market's opinion, used as model
#: input. This is not a settlement venue and reachability does not apply to it: an
#: information price is worth using because it is sharp, not because an account can be
#: opened at it. Pinnacle is first for exactly that reason, and it is the last place in this
#: codebase where that ordering is correct. Where money is settled the venue must be one a
#: UK resident can reach — see :mod:`tennis_edge.venues`.
#:
#: Frozen: every constant here is inside :func:`policy_digest`, so this tuple cannot be
#: reordered without minting a new policy vintage.
PREFERRED_BOOKS: tuple[str, ...] = ("pinnacle", "b365", "avg")

DEVIG_METHOD = DevigMethod.POWER

#: Betfair Rewards flat rate. Applied even when the recorded price is a bookmaker's, because
#: the exchange is where a bet would actually go and pricing it any cheaper flatters the rule.
COMMISSION = 0.02

#: The model must beat the market by this much, in probability, before a recommendation is
#: even considered. Set from the measured facts rather than chosen for tip volume: the model
#: layers came in at roughly 0.05 log-odds of incremental weight, so anything below a five
#: point disagreement is inside the noise those measurements established.
TIP_MARGIN = 0.05

#: Disagreement worth recording but not acting on.
WATCH_MARGIN = 0.03

#: The model view is shrunk toward the market before use. b1 was measured at -0.027 for the
#: rating layer and +0.056 for the point model, so the honest weight on the model is close to
#: zero; 0.10 is a deliberately small allowance that keeps the rule from being pure market
#: echo while staying inside what the evidence supports.
MODEL_SHRINKAGE = 0.10


@unique
class Status(Enum):
    """What the rule concluded. There is no state that authorises real money."""

    RECOMMEND_A = "RECOMMEND_A"
    RECOMMEND_B = "RECOMMEND_B"
    WATCH = "WATCH"
    NO_BET = "NO_BET"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class Decision:
    """One frozen-policy decision, with everything needed to re-derive it."""

    status: Status
    book: str | None
    market_probability_a: float | None
    model_probability_a: float | None
    blended_probability_a: float | None
    quoted_odds: float | None
    side: str | None
    expected_value: float | None
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value, "book": self.book,
            "market_probability_a": self.market_probability_a,
            "model_probability_a": self.model_probability_a,
            "blended_probability_a": self.blended_probability_a,
            "quoted_odds": self.quoted_odds, "side": self.side,
            "expected_value": self.expected_value, "reason": self.reason,
        }


def policy_digest() -> str:
    """Digest over every frozen constant. Changing one changes this."""
    return digest_of(
        {
            "version": POLICY_VERSION,
            "books": list(PREFERRED_BOOKS),
            "devig": DEVIG_METHOD.value,
            "commission": COMMISSION,
            "tip_margin": TIP_MARGIN,
            "watch_margin": WATCH_MARGIN,
            "model_shrinkage": MODEL_SHRINKAGE,
        }
    )


def _logit(p: float) -> float:
    clipped = min(max(p, 1e-9), 1.0 - 1e-9)
    return math.log(clipped / (1.0 - clipped))


def _reference_price(match: Match) -> tuple[str, tuple[float, float]] | None:
    from tennis_edge.backtest import market_probability  # local: avoids an import cycle

    for book in PREFERRED_BOOKS:
        pair = match.odds.pair(book)
        if pair is None:
            continue
        if market_probability(match, book=book, method=DEVIG_METHOD) is None:
            continue
        return book, pair
    return None


def decide(match: Match, model_probability_a: float | None) -> Decision:
    """Apply the frozen rule to one match.

    ``model_probability_a`` is whatever view the model layers produced, or None when they
    could not price the match — in which case the market stands alone and the answer is
    NO_BET rather than a guess.
    """
    from tennis_edge.backtest import market_probability

    reference = _reference_price(match)
    if reference is None:
        return Decision(
            status=Status.BLOCKED, book=None, market_probability_a=None,
            model_probability_a=model_probability_a, blended_probability_a=None,
            quoted_odds=None, side=None, expected_value=None,
            reason="no usable price from any preferred book",
        )
    book, quotes = reference
    market = market_probability(match, book=book, method=DEVIG_METHOD)
    if market is None:  # pragma: no cover - _reference_price already proved it prices
        raise RuntimeError("reference book lost its price between checks")

    if model_probability_a is None:
        return Decision(
            status=Status.NO_BET, book=book, market_probability_a=market,
            model_probability_a=None, blended_probability_a=market,
            quoted_odds=None, side=None, expected_value=None,
            reason="no model view; the market stands alone",
        )

    blended = 1.0 / (
        1.0
        + math.exp(
            -((1.0 - MODEL_SHRINKAGE) * _logit(market)
              + MODEL_SHRINKAGE * _logit(model_probability_a))
        )
    )
    disagreement = blended - market
    side = "A" if disagreement > 0 else "B"
    probability = blended if side == "A" else 1.0 - blended
    quoted = quotes[0] if side == "A" else quotes[1]
    net_odds = 1.0 + (quoted - 1.0) * (1.0 - COMMISSION)
    expected_value = probability * net_odds - 1.0

    magnitude = abs(disagreement)
    if magnitude >= TIP_MARGIN and expected_value > 0.0:
        status = Status.RECOMMEND_A if side == "A" else Status.RECOMMEND_B
        reason = f"model disagrees by {magnitude:.3f} and EV is {expected_value:+.3f}"
    elif magnitude >= WATCH_MARGIN:
        status = Status.WATCH
        reason = (
            f"disagreement {magnitude:.3f} above watch margin but "
            f"{'below tip margin' if magnitude < TIP_MARGIN else 'EV not positive'}"
        )
    else:
        status = Status.NO_BET
        reason = f"disagreement {magnitude:.3f} inside the noise band"

    return Decision(
        status=status, book=book, market_probability_a=market,
        model_probability_a=model_probability_a, blended_probability_a=blended,
        quoted_odds=quoted if status in (Status.RECOMMEND_A, Status.RECOMMEND_B) else None,
        side=side if status in (Status.RECOMMEND_A, Status.RECOMMEND_B) else None,
        expected_value=expected_value, reason=reason,
    )


def constants() -> Mapping[str, object]:
    """The frozen constants, for reporting alongside a ledger."""
    return {
        "version": POLICY_VERSION, "digest": policy_digest(),
        "books": PREFERRED_BOOKS, "devig": DEVIG_METHOD.value, "commission": COMMISSION,
        "tip_margin": TIP_MARGIN, "watch_margin": WATCH_MARGIN,
        "model_shrinkage": MODEL_SHRINKAGE,
    }
