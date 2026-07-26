"""The predictor: one match in, one probability out, with its reasons and its limits.

**What seventeen years of out-of-sample fitting actually found.** Given free rein to weight
a model against the market by maximum likelihood, refitted every year on prior years only
and scored on 72,669 unseen matches:

* the model's weight ``alpha`` is **indistinguishable from zero in every single year**
  (t between −0.4 and +0.3), and is frequently negative;
* the market's weight ``beta`` sits at **≈0.95 with t between 55 and 69** — overwhelming;
* the model adds **+0.00001 nats** on top of simply shrinking the market's own logit, which
  itself is worth +0.00015.

So the honest predictor is the **de-vigged market price with its logit shrunk ~5%**. That is
not a disappointing substitute for a model; it is the measured answer, and a tool that
dressed a market echo up as a proprietary model would be lying about where its number comes
from.

The model view is still computed and still reported — as a *labelled diagnostic*, never as
the answer, and every prediction carries :attr:`Prediction.model_weight` so its
insignificance is visible at the point of use rather than buried in a report.

**This states probabilities. It never recommends a bet.** ``recommendation`` is pinned to
``NOT_EVALUATED`` for every possible input, and a test asserts that no combination of
inputs can produce anything else.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique

from price_contracts.ladder import is_on_ladder
from tennis_edge.combine import Combination, combination_interval
from tennis_edge.exchange import COMMISSION, expected_value

__all__ = ["Basis", "Reason", "Prediction", "predict", "NEGLIGIBLE_MODEL_WEIGHT"]

#: Below this share of total fitted weight, the model is doing nothing worth mentioning
#: except to say so. The measured value across 17 years is under 0.02.
NEGLIGIBLE_MODEL_WEIGHT = 0.05

#: Logit gap between model and market above which the disagreement is worth surfacing.
DISAGREEMENT_LOGITS = 0.75


@unique
class Basis(Enum):
    """What the number actually rests on. Never blended silently across these."""

    MARKET_RECALIBRATED = "MARKET_RECALIBRATED"
    MARKET_ONLY = "MARKET_ONLY"
    MODEL_ONLY = "MODEL_ONLY"


@unique
class Reason(Enum):
    """Deterministic, numeric-core-derived. No causal language, no LLM-invented reasons."""

    NO_MARKET_PRICE = "NO_MARKET_PRICE"
    NO_MODEL_VIEW = "NO_MODEL_VIEW"
    MODEL_WEIGHT_NEGLIGIBLE = "MODEL_WEIGHT_NEGLIGIBLE"
    MODEL_DISAGREES_WITH_MARKET = "MODEL_DISAGREES_WITH_MARKET"
    PRICE_ABOVE_FAIR = "PRICE_ABOVE_FAIR"
    PRICE_BELOW_FAIR = "PRICE_BELOW_FAIR"


@dataclass(frozen=True)
class Prediction:
    """One match's probability, with everything needed to judge how much to trust it."""

    probability_a: float
    probability_b: float
    low: float
    high: float
    basis: Basis
    p_model: float | None
    p_market: float | None
    #: Share of fitted weight sitting on the model. Measured under 0.02; reported on every
    #: prediction so it cannot be quietly overstated downstream.
    model_weight: float
    fair_odds_a: Decimal
    fair_odds_b: Decimal
    expected_value_a: float | None
    reasons: tuple[Reason, ...]
    #: Hard-pinned. This tool states probabilities and never authorises a bet.
    recommendation: str = "NOT_EVALUATED"


def _logit(p: float) -> float:
    clipped = min(max(p, 1e-12), 1.0 - 1e-12)
    return math.log(clipped / (1.0 - clipped))


def _fair(probability: float) -> Decimal:
    return (Decimal(1) / Decimal(str(probability))).quantize(Decimal("0.001"))


def predict(
    *,
    p_model: float | None,
    p_market: float | None,
    combination: Combination,
    quoted_odds_a: Decimal | None = None,
    commission: Decimal = COMMISSION,
) -> Prediction:
    """Combine a model view and a market price into one probability for player A.

    Either input may be absent and the basis records which. Both absent raises: there is no
    default probability, and inventing one would be the worst possible failure mode for a
    tool whose only job is to be honest about what it knows.
    """
    if p_model is None and p_market is None:
        raise ValueError(
            "no price and no model view — there is nothing to predict from, and this "
            "returns no default probability"
        )

    reasons: list[Reason] = []
    if p_market is None:
        basis = Basis.MODEL_ONLY
        assert p_model is not None
        probability = low = high = p_model
        reasons.append(Reason.NO_MARKET_PRICE)
    elif p_model is None:
        basis = Basis.MARKET_ONLY
        market_only = Combination(alpha=0.0, beta=combination.beta,
                                  n_train=combination.n_train,
                                  beta_se=combination.beta_se)
        low, probability, high = combination_interval(market_only, p_market, p_market)
        reasons.append(Reason.NO_MODEL_VIEW)
    else:
        basis = Basis.MARKET_RECALIBRATED
        low, probability, high = combination_interval(combination, p_model, p_market)
        if abs(_logit(p_model) - _logit(p_market)) >= DISAGREEMENT_LOGITS:
            reasons.append(Reason.MODEL_DISAGREES_WITH_MARKET)

    if basis is not Basis.MODEL_ONLY and combination.model_share < NEGLIGIBLE_MODEL_WEIGHT:
        reasons.append(Reason.MODEL_WEIGHT_NEGLIGIBLE)

    expected: float | None = None
    if quoted_odds_a is not None:
        if not is_on_ladder(quoted_odds_a):
            raise ValueError(f"quoted odds {quoted_odds_a} are off-ladder")
        expected = expected_value(probability=probability, price=quoted_odds_a,
                                  commission=commission)
        reasons.append(Reason.PRICE_ABOVE_FAIR if expected > 0 else Reason.PRICE_BELOW_FAIR)

    return Prediction(
        probability_a=probability,
        probability_b=1.0 - probability,
        low=low,
        high=high,
        basis=basis,
        p_model=p_model,
        p_market=p_market,
        model_weight=combination.model_share,
        fair_odds_a=_fair(probability),
        fair_odds_b=_fair(1.0 - probability),
        expected_value_a=expected,
        reasons=tuple(reasons),
    )
