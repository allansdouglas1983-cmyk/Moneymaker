"""The last untested modelling architecture: a boosted residual on the market.

Everything so far has failed the same way — a model is built, compared to the closing line,
and found to add nothing. This asks the question differently. The market's logit enters as a
fixed **offset** (`init_score`), so boosting round zero *is* the market. Every tree after
that can only earn its place by predicting where the market is wrong. If the model has
nothing, early stopping fires almost immediately and the answer is unambiguous.

The features are deliberately **deviations from the market**, not levels: `elo_logit -
market_logit`, `point_model_logit - market_logit`. That makes the learner's job "when my
models disagree with the price, is that disagreement informative?" — the actual question —
and makes "no signal" the natural default rather than something it has to discover.

Capacity is kept tiny on purpose. Any real residual here is worth a few thousandths of a nat
per match; a deep tree will manufacture that much from noise without difficulty.

Note the LightGBM trap this code works around: `init_score` is a training-time construct.
`predict()` does **not** add it back and it is not saved with the model, so the offset has to
be re-applied by hand at inference. Forgetting that produces predictions centred on zero and
a spectacular, entirely fake, apparent edge.

Run with ``python -m tennis_edge.experiments.residual_gbm``.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import numpy.typing as npt

from tennis_edge.backtest import market_probability
from tennis_edge.corpus import group_by_day, load_corpus
from tennis_edge.devig import DevigMethod
from tennis_edge.experiments.residual_vs_market import TRAIN, VALIDATE
from tennis_edge.features import FEATURE_NAMES, build_features
from tennis_edge.ratings import RatingEngine, elo_expected
from tennis_edge.sackmann import load_matches
from tennis_edge.serve_stats import ServeEstimator

__all__ = ["PARAMS", "GbmResult", "run", "main"]

#: Deliberately small. Depth 3 and thousands of rows per leaf mean a tree can only express a
#: broad, repeated pattern — which is the only kind that could survive out of sample.
PARAMS: dict[str, object] = {
    "objective": "binary",
    "metric": "binary_logloss",
    "learning_rate": 0.01,
    "num_leaves": 7,
    "max_depth": 3,
    "min_data_in_leaf": 2000,
    "feature_fraction": 0.5,
    "bagging_fraction": 0.7,
    "bagging_freq": 1,
    "lambda_l2": 50.0,
    "verbose": -1,
    "seed": 20260725,
    "deterministic": True,
    "num_threads": 4,
}

_ARCHIVE_FROM = dt.date(2003, 1, 1)
_SCORING_FROM = dt.date(2005, 1, 1)
_MIN_SERVE_POINTS = 300.0

_FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class GbmResult:
    """What the residual model achieved, and how hard it tried."""

    rows: int
    validate_n: int
    market_log_loss: float
    model_log_loss: float
    best_iteration: int
    top_features: tuple[tuple[str, float], ...]
    clustered_t: float
    clusters: int

    @property
    def improvement(self) -> float:
        return self.market_log_loss - self.model_log_loss

    @property
    def verdict(self) -> str:
        if self.best_iteration <= 5:
            return "early stopping fired almost immediately — no residual signal at all"
        if self.improvement <= 0:
            return "the residual model is worse than the market out of sample"
        if self.clustered_t > 3.0:
            return f"improves log loss by {self.improvement:.5f} nats/match, and it holds up"
        return (
            f"improves log loss by {self.improvement:.5f} nats/match, but t="
            f"{self.clustered_t:.2f} is below the t>3 hurdle for a multi-variant search"
        )

    def report(self) -> str:
        lines = [
            f"rows {self.rows:,} | validate {self.validate_n:,}",
            f"  market          {self.market_log_loss:.5f}",
            f"  residual GBM    {self.model_log_loss:.5f}",
            f"  best iteration  {self.best_iteration}",
            f"  day-clustered DM t = {self.clustered_t:+.3f} over {self.clusters:,} clusters",
            f"  VERDICT: {self.verdict}",
        ]
        if self.top_features:
            lines.append("  most-used features:")
            lines += [f"     {name:<28}{gain:>10.1f}" for name, gain in self.top_features]
        return "\n".join(lines)


def _logit(p: float) -> float:
    clipped = min(max(p, 1e-6), 1.0 - 1e-6)
    return math.log(clipped / (1.0 - clipped))


def run() -> GbmResult:
    """Build the deviation panel and fit the offset model."""
    matches, _ = load_corpus()
    engine = RatingEngine()
    estimator = ServeEstimator()
    estimator.queue(
        load_matches(
            families=("main", "qual_chall"), since=_ARCHIVE_FROM, require_serve_stats=True
        )
    )

    names = list(FEATURE_NAMES) + ["elo_minus_market", "point_minus_market", "point_available"]
    rows: list[list[float]] = []
    offsets: list[float] = []
    outcomes: list[int] = []
    days: list[dt.date] = []

    for day, batch in group_by_day(matches):
        if day >= _SCORING_FROM:
            estimator.advance_to(day)
            for match in sorted(batch, key=lambda m: (m.tour, m.player_a, m.player_b)):
                probability = market_probability(
                    match, book="pinnacle", method=DevigMethod.POWER
                )
                if probability is None:
                    continue
                market_logit = _logit(probability)
                base = list(build_features(engine, match))
                elo_logit = _logit(
                    elo_expected(
                        engine.blended(match.tour, match.player_a, match.surface),
                        engine.blended(match.tour, match.player_b, match.surface),
                    )
                )
                estimate = estimator.estimate(
                    match.tour, match.player_a, match.player_b, day
                )
                if estimate is not None and estimate.coverage >= _MIN_SERVE_POINTS:
                    point_logit = _logit(estimate.match_probability(best_of=match.best_of))
                    point_deviation = point_logit - market_logit
                    available = 1.0
                else:
                    point_deviation = 0.0
                    available = 0.0
                rows.append(base + [elo_logit - market_logit, point_deviation, available])
                offsets.append(market_logit)
                outcomes.append(1 if match.winner_is_a else 0)
                days.append(day)
        engine.observe(batch)

    features = np.asarray(rows, dtype=np.float64)
    offset = np.asarray(offsets, dtype=np.float64)
    y = np.asarray(outcomes, dtype=int)
    date_array = np.asarray(days, dtype=object)
    train = (date_array >= TRAIN[0]) & (date_array <= TRAIN[1])
    validate = (date_array >= VALIDATE[0]) & (date_array <= VALIDATE[1])

    train_set = lgb.Dataset(
        features[train], label=y[train], init_score=offset[train], feature_name=names
    )
    valid_set = lgb.Dataset(
        features[validate], label=y[validate], init_score=offset[validate],
        reference=train_set, feature_name=names,
    )
    booster = lgb.train(
        PARAMS, train_set, num_boost_round=3000, valid_sets=[valid_set],
        callbacks=[lgb.early_stopping(200, verbose=False)],
    )

    # init_score is NOT re-applied by predict(); the offset must be added back by hand.
    raw = np.asarray(booster.predict(features[validate], raw_score=True), dtype=np.float64)
    combined = 1.0 / (1.0 + np.exp(-(raw + offset[validate])))
    market_only = 1.0 / (1.0 + np.exp(-offset[validate]))

    def log_loss(p: _FloatArray) -> float:
        clipped = np.clip(p, 1e-15, 1.0 - 1e-15)
        target = y[validate]
        return float(
            -np.mean(target * np.log(clipped) + (1 - target) * np.log(1.0 - clipped))
        )

    def loss_terms(p: _FloatArray) -> _FloatArray:
        clipped = np.clip(p, 1e-15, 1.0 - 1e-15)
        target = y[validate]
        return np.asarray(
            -(target * np.log(clipped) + (1 - target) * np.log(1.0 - clipped)),
            dtype=np.float64,
        )

    difference = loss_terms(market_only) - loss_terms(combined)
    cluster_totals: dict[dt.date, float] = {}
    for when, value in zip(date_array[validate], difference):
        cluster_totals[when] = cluster_totals.get(when, 0.0) + float(value)
    totals = np.asarray(list(cluster_totals.values()), dtype=np.float64)
    standard_error = totals.std(ddof=1) * math.sqrt(len(totals)) / len(difference)
    t_statistic = float(difference.mean() / standard_error) if standard_error > 0 else 0.0

    gains = booster.feature_importance(importance_type="gain")
    ranked = sorted(zip(names, gains), key=lambda item: -item[1])[:6]

    return GbmResult(
        rows=len(y),
        validate_n=int(validate.sum()),
        market_log_loss=log_loss(market_only),
        model_log_loss=log_loss(combined),
        best_iteration=int(booster.best_iteration or 0),
        top_features=tuple((name, float(gain)) for name, gain in ranked if gain > 0),
        clustered_t=t_statistic,
        clusters=len(totals),
    )


def main() -> None:
    print(run().report())


if __name__ == "__main__":
    main()
