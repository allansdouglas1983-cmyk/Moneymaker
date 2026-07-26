"""The residual-model policy. A new vintage, not an edit to the old one.

:mod:`tennis_edge.policy` treats the market as the answer and the model as a labelled
challenger, shrunk hard toward the price. That was the right rule when it was frozen: four
architectures had been measured and all four were flat, so a rule that leaned on any of them
would have been leaning on nothing.

TE-0007 changed the premise. A model that beats the closing price now exists — +0.000862
nats out-of-sample on 63,576 matches, day-clustered interval excluding zero, against a
placebo of −0.000114 — because the corrections were unbundled and allowed to take their own
signs, and because ratings that can see below the main tour were added. So v2 uses the
model's probability directly rather than as a challenger to be shrunk away.

**Why this is a separate module and not a change to v1.** The integrity claim of the whole
weekly loop is that a policy's code and constants were committed at a hash dated *before* the
matches it is later judged on existed. Editing v1 would retroactively change what its
existing ledger rows mean while leaving them labelled `frozen-policy-v1`. A new version with
its own digest keeps both claims intact: v1's record still says what v1 decided, and v2 earns
its own record from scratch.

**The model is inside the digest, not beside it.** Two policies with identical thresholds but
different coefficients are different rules, and a ledger row has to be able to tell them
apart. :func:`policy_digest_v2` takes the model and folds its digest in.

**What this is not.** It emits recommendations *into a ledger*, which is a measurement
instrument, not advice. TE-0007 measured the model's exchange performance as undecided at
the available power, and the Pinnacle confidence interval includes zero. Nothing here
authorises a stake, and :mod:`tennis_edge.upcoming` — the tool a person actually points at a
fixture — pins its recommendation field to ``NOT_EVALUATED`` regardless of what this decides.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from typing import Mapping

from tennis_edge.digests import digest_of
from tennis_edge.residual_model import ResidualModel

__all__ = [
    "POLICY_VERSION",
    "COMMISSION",
    "MIN_EDGE",
    "WATCH_EDGE",
    "Status",
    "DecisionV2",
    "policy_digest_v2",
    "decide_v2",
]

POLICY_VERSION = "residual-policy-v2"

#: Betfair Rewards flat rate, applied even when the recorded price is a bookmaker's. The
#: exchange is where a bet would actually go, and pricing it any cheaper flatters the rule.
COMMISSION = 0.02

#: Probability the model must clear the commission-aware break-even by before a
#: recommendation is recorded. Not a tuned threshold: it is roughly the per-match edge the
#: measured +0.000862 nats corresponds to at typical prices, so a rule firing below it would
#: be claiming more precision than the evidence supports. A threshold chosen to produce a
#: pleasing number of tips would be a fitted parameter, which is why this one is derived and
#: then frozen into the digest.
MIN_EDGE = 0.02

#: Worth recording but not acting on.
WATCH_EDGE = 0.01


@unique
class Status(Enum):
    """What the rule concluded. No state authorises real money."""

    RECOMMEND_A = "RECOMMEND_A"
    RECOMMEND_B = "RECOMMEND_B"
    WATCH = "WATCH"
    NO_BET = "NO_BET"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class DecisionV2:
    """One decision, with both edges kept so the losing side is auditable too."""

    status: Status
    market_probability_a: float | None
    model_probability_a: float | None
    edge_a: float
    edge_b: float
    quoted_odds: float | None
    side: str | None
    reason: str


def _break_even(odds: float, commission: float = COMMISSION) -> float:
    """``1 / (1 + (O-1)(1-c))``. Not ``1/O`` — commission is charged on net winnings."""
    return 1.0 / (1.0 + (odds - 1.0) * (1.0 - commission))


def policy_digest_v2(model: ResidualModel) -> str:
    """Digest over every constant *and* the model. Both define the rule."""
    return digest_of({
        "policy_version": POLICY_VERSION,
        "commission": repr(COMMISSION),
        "min_edge": repr(MIN_EDGE),
        "watch_edge": repr(WATCH_EDGE),
        "model_digest": model.digest,
    })


def decide_v2(
    *,
    market_probability_a: float | None,
    features: Mapping[str, float],
    odds_a: float | None,
    odds_b: float | None,
    model: ResidualModel,
    commission: float = COMMISSION,
) -> DecisionV2:
    """Apply the frozen v2 rule to one match.

    A missing market price or a missing quote BLOCKS. The model corrects a price; with no
    price there is nothing to correct, and inventing one would put fiction in the ledger
    under a digest that claims otherwise.
    """
    if market_probability_a is None or odds_a is None or odds_b is None:
        return DecisionV2(
            status=Status.BLOCKED, market_probability_a=market_probability_a,
            model_probability_a=None, edge_a=0.0, edge_b=0.0, quoted_odds=None,
            side=None, reason="NO_REFERENCE_PRICE",
        )

    market_logit = _logit(market_probability_a)
    probability_a = model.probability(market_logit, features)
    edge_a = probability_a - _break_even(odds_a, commission)
    edge_b = (1.0 - probability_a) - _break_even(odds_b, commission)

    best_edge = max(edge_a, edge_b)
    side = "A" if edge_a >= edge_b else "B"
    odds = odds_a if side == "A" else odds_b

    if best_edge >= MIN_EDGE:
        status = Status.RECOMMEND_A if side == "A" else Status.RECOMMEND_B
        reason = "EDGE_ABOVE_MINIMUM"
    elif best_edge >= WATCH_EDGE:
        status, reason = Status.WATCH, "EDGE_BELOW_MINIMUM"
    else:
        status, reason = Status.NO_BET, "NO_EDGE_AT_QUOTED_PRICE"

    return DecisionV2(
        status=status,
        market_probability_a=market_probability_a,
        model_probability_a=probability_a,
        edge_a=edge_a,
        edge_b=edge_b,
        quoted_odds=odds if status in {Status.RECOMMEND_A, Status.RECOMMEND_B} else None,
        side=side if status in {Status.RECOMMEND_A, Status.RECOMMEND_B} else None,
        reason=reason,
    )


def _logit(p: float) -> float:
    import math

    clipped = min(max(p, 1e-12), 1.0 - 1e-12)
    return math.log(clipped / (1.0 - clipped))
