"""Does the point-based serve model add information the closing line has not priced?

The rating layer answered this with a flat no (``b1 = -0.027``). Serve and return counts are
the first genuinely different information in the system — they describe *how* points were
won, not just who won — so the question is worth asking again with the point model in place
of Elo.

The test is Diebold-Mariano on per-match log loss, clustered by day, following the form used
in the published encompassing tests. It is run on every priced match rather than on a
selected bet list, because that is far higher-powered: a betting simulation throws away most
of the sample and adds staking noise on top.

Two numbers decide it. ``b1`` is the weight a free logistic fit wants to put on the point
model given the market. The DM t-statistic says whether the resulting improvement is
distinguishable from zero. The bar is not 1.96: after multiple testing across model variants
the accepted hurdle in this literature is t > 3.

Run with ``python -m tennis_edge.experiments.point_model_vs_market``.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from tennis_edge.backtest import market_probability
from tennis_edge.corpus import group_by_day, load_corpus
from tennis_edge.devig import DevigMethod
from tennis_edge.experiments.residual_vs_market import TRAIN, VALIDATE, fit_logistic
from tennis_edge.sackmann import load_matches
from tennis_edge.serve_stats import ServeEstimator

__all__ = ["MIN_SERVE_POINTS", "DiagnosticResult", "run", "main"]

#: Decayed serve points required on BOTH sides before an estimate is used. Below this the
#: serve percentage is mostly prior, and the match model would amplify what noise remains.
MIN_SERVE_POINTS = 300.0

_ARCHIVE_FROM = dt.date(2003, 1, 1)
_SCORING_FROM = dt.date(2005, 1, 1)

_FloatArray = npt.NDArray[np.float64]


def _sigmoid(z: _FloatArray) -> _FloatArray:
    return np.asarray(1.0 / (1.0 + np.exp(-z)), dtype=np.float64)


def _log_loss_terms(p: _FloatArray, y: npt.NDArray[np.int_]) -> _FloatArray:
    clipped = np.clip(p, 1e-15, 1.0 - 1e-15)
    return np.asarray(
        -(y * np.log(clipped) + (1 - y) * np.log(1.0 - clipped)), dtype=np.float64
    )


@dataclass(frozen=True)
class DiagnosticResult:
    """Everything needed to judge the increment, including how it was judged."""

    validate_n: int
    market_log_loss: float
    point_model_log_loss: float
    blend_log_loss: float
    b1_point_model: float
    b2_market: float
    mean_improvement: float
    clustered_t: float
    clusters: int
    matches_for_significance: int

    @property
    def verdict(self) -> str:
        if self.clustered_t > 3.0:
            return "the point model adds information over the market"
        if self.clustered_t > 1.96:
            return "suggestive but below the multiple-testing hurdle of t > 3"
        return "no measurable information over the market"

    def report(self) -> str:
        return (
            f"validate n={self.validate_n:,}\n"
            f"  market            {self.market_log_loss:.5f}\n"
            f"  point model       {self.point_model_log_loss:.5f}\n"
            f"  blend             {self.blend_log_loss:.5f}\n"
            f"  b1 point={self.b1_point_model:+.4f}  b2 market={self.b2_market:+.4f}\n"
            f"  improvement {self.mean_improvement:+.6f} nats/match; "
            f"day-clustered DM t = {self.clustered_t:+.3f} over {self.clusters:,} clusters\n"
            f"  matches needed for significance at this effect size: "
            f"{self.matches_for_significance:,}\n"
            f"  VERDICT: {self.verdict}"
        )


def run(*, min_serve_points: float = MIN_SERVE_POINTS) -> DiagnosticResult:
    """Build the joined panel, fit the encompassing regression, and test the increment."""
    matches, _ = load_corpus()
    estimator = ServeEstimator()
    estimator.queue(
        load_matches(
            families=("main", "qual_chall"), since=_ARCHIVE_FROM, require_serve_stats=True
        )
    )

    days: list[dt.date] = []
    outcomes: list[int] = []
    market: list[float] = []
    model: list[float] = []
    for day, batch in group_by_day(matches):
        if day < _SCORING_FROM:
            continue
        estimator.advance_to(day)
        for match in sorted(batch, key=lambda m: (m.tour, m.player_a, m.player_b)):
            probability = market_probability(match, book="pinnacle", method=DevigMethod.POWER)
            if probability is None:
                continue
            estimate = estimator.estimate(match.tour, match.player_a, match.player_b, day)
            if estimate is None or estimate.coverage < min_serve_points:
                continue
            days.append(day)
            outcomes.append(1 if match.winner_is_a else 0)
            market.append(probability)
            model.append(estimate.match_probability(best_of=match.best_of))

    date_array = np.asarray(days, dtype=object)
    y = np.asarray(outcomes, dtype=int)
    market_p = np.clip(np.asarray(market, dtype=np.float64), 1e-6, 1.0 - 1e-6)
    model_p = np.clip(np.asarray(model, dtype=np.float64), 1e-6, 1.0 - 1e-6)
    market_logit = np.log(market_p / (1.0 - market_p))
    model_logit = np.log(model_p / (1.0 - model_p))

    train = (date_array >= TRAIN[0]) & (date_array <= TRAIN[1])
    validate = (date_array >= VALIDATE[0]) & (date_array <= VALIDATE[1])

    design = np.column_stack([np.ones(len(y)), model_logit, market_logit])
    weights = fit_logistic(
        design[train], y[train], np.zeros(int(train.sum()), dtype=np.float64), l2=1e-6
    )

    blend = _sigmoid(design[validate] @ weights)
    market_terms = _log_loss_terms(_sigmoid(market_logit[validate]), y[validate])
    blend_terms = _log_loss_terms(blend, y[validate])
    difference = market_terms - blend_terms

    clusters: dict[dt.date, float] = {}
    for when, value in zip(date_array[validate], difference):
        clusters[when] = clusters.get(when, 0.0) + float(value)
    cluster_totals = np.asarray(list(clusters.values()), dtype=np.float64)
    standard_error = (
        cluster_totals.std(ddof=1) * math.sqrt(len(cluster_totals)) / len(difference)
    )
    mean_improvement = float(difference.mean())
    t_statistic = mean_improvement / standard_error if standard_error > 0 else 0.0
    spread = float(difference.std(ddof=1))
    needed = (
        int(round((1.96 * spread / abs(mean_improvement)) ** 2))
        if mean_improvement != 0.0
        else 0
    )

    return DiagnosticResult(
        validate_n=int(validate.sum()),
        market_log_loss=float(market_terms.mean()),
        point_model_log_loss=float(
            _log_loss_terms(_sigmoid(model_logit[validate]), y[validate]).mean()
        ),
        blend_log_loss=float(blend_terms.mean()),
        b1_point_model=float(weights[1]),
        b2_market=float(weights[2]),
        mean_improvement=mean_improvement,
        clustered_t=float(t_statistic),
        clusters=len(cluster_totals),
        matches_for_significance=needed,
    )


def main() -> None:
    print(run().report())


if __name__ == "__main__":
    main()
