"""Stage-two market combination — how much weight does the model actually earn?

``score = alpha * logit(p_model) + beta * logit(p_market)``, both weights fitted by maximum
likelihood on the winner. This is the canonical form (SPEC-032's shape, and the standard
construction in the forecasting literature), and it exists here to replace an assertion with
a measurement.

The frozen policy in :mod:`tennis_edge.policy` uses a fixed 10% shrinkage toward the market.
That constant *asserts* how much the model is worth. Fitting alpha and beta asks the data,
and the answer is allowed to be "nothing": if outcomes follow the price alone, alpha comes
back at zero. A method that cannot return that is not a measurement, so the tests pin it.

**The fit must be strictly time-respecting.** A combination fitted on data that includes the
match it later prices is not a forecast, and the inflation lands precisely where it would
most mislead. :func:`fit_combination` is a pure function of the rows it is given; keeping
those rows in the past is the caller's job, and
:mod:`tennis_edge.experiments.combination_walk_forward` does it with an expanding window.

Separation is refused rather than regularised. An all-winners or all-losers training block
cannot identify a logistic fit — the weights run away to infinity — and a quiet ridge penalty
there would return a confident number with no information in it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

__all__ = [
    "Combination",
    "MARKET_ONLY",
    "logit",
    "fit_combination",
    "apply_combination",
]

#: Below this a fit is noise, not an estimate.
MIN_TRAIN_ROWS = 50

_MAX_ITER = 100
_TOLERANCE = 1e-10
#: Weights beyond this indicate separation or a degenerate design, not a strong signal.
_MAX_WEIGHT = 20.0


@dataclass(frozen=True)
class Combination:
    """Fitted weights on the model and market logits."""

    alpha: float
    beta: float
    n_train: int

    @property
    def model_share(self) -> float:
        """Fraction of total weight sitting on the model. 0.0 means the market alone."""
        total = abs(self.alpha) + abs(self.beta)
        return 0.0 if total == 0.0 else abs(self.alpha) / total


#: The null combination: the market, unchanged. The thing every fit must beat to matter.
MARKET_ONLY = Combination(alpha=0.0, beta=1.0, n_train=0)


def logit(p: float) -> float:
    clipped = min(max(p, 1e-12), 1.0 - 1e-12)
    return math.log(clipped / (1.0 - clipped))


def _sigmoid(z: float) -> float:
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


def fit_combination(
    rows: Sequence[tuple[float, float, int]], *, min_rows: int = MIN_TRAIN_ROWS
) -> Combination:
    """Fit ``(alpha, beta)`` by Newton-Raphson on the binomial log-likelihood.

    ``rows`` are ``(p_model, p_market, outcome)`` with outcome 1 when player A won. There is
    deliberately no intercept: an intercept would let the fit correct a base-rate error that
    a well-formed choice set cannot have, and would mask a miscalibrated input rather than
    exposing it.
    """
    if len(rows) < min_rows:
        raise ValueError(
            f"need at least {min_rows} rows to fit a combination, got {len(rows)}"
        )
    outcomes = {y for _m, _k, y in rows}
    if len(outcomes) < 2:
        raise ValueError(
            "training rows contain both outcomes or the fit is unidentified; got "
            f"only {outcomes}. Separation is refused rather than regularised — a ridge "
            "penalty here returns a confident number carrying no information."
        )

    design = [(logit(model), logit(market), float(y)) for model, market, y in rows]
    alpha, beta = 0.0, 1.0
    for _ in range(_MAX_ITER):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x0, x1, y in design:
            p = _sigmoid(alpha * x0 + beta * x1)
            residual = y - p
            weight = p * (1.0 - p)
            g0 += x0 * residual
            g1 += x1 * residual
            h00 += x0 * x0 * weight
            h01 += x0 * x1 * weight
            h11 += x1 * x1 * weight
        determinant = h00 * h11 - h01 * h01
        if abs(determinant) < 1e-12:
            break
        step0 = (h11 * g0 - h01 * g1) / determinant
        step1 = (h00 * g1 - h01 * g0) / determinant
        alpha += step0
        beta += step1
        if not (math.isfinite(alpha) and math.isfinite(beta)):
            raise ValueError("combination fit diverged; the design is degenerate")
        if abs(step0) < _TOLERANCE and abs(step1) < _TOLERANCE:
            break

    if max(abs(alpha), abs(beta)) > _MAX_WEIGHT:
        raise ValueError(
            f"combination fit ran away (alpha={alpha:.3g}, beta={beta:.3g}); that is "
            "separation or a degenerate design, not a strong signal"
        )
    return Combination(alpha=alpha, beta=beta, n_train=len(rows))


def apply_combination(
    combination: Combination, p_model: float, p_market: float
) -> float:
    """Combined probability for player A. Always strictly inside (0, 1)."""
    score = combination.alpha * logit(p_model) + combination.beta * logit(p_market)
    return min(max(_sigmoid(score), 1e-12), 1.0 - 1e-12)
