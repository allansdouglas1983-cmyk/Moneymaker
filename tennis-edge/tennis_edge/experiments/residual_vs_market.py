"""Does anything we can compute add information the market has not already priced?

This is the central question of the whole project, asked in the least flattering way
available. Rather than building a model and comparing it to the market — where a mediocre
model can look respectable — the market's own logit is used as a fixed **offset**, and the
features are given the single job of predicting the market's *error*. If they cannot, they
have nothing to contribute, whatever they score on their own.

Three fits, all trained on 2010-2020 and judged on 2021-2023 (2024+ is a holdout that this
experiment does not read):

1. ``market``    — the de-vigged closing line alone, the benchmark.
2. ``residual``  — ``logit(p) = market_logit + w . features``; the offset is fixed at
   coefficient 1, so ``w`` is pure residual signal.
3. ``blend``     — ``logit(p) = a + b1 . model_logit + b2 . market_logit`` with both free.
   ``b1`` is the verdict: if it shrinks to zero out of sample, the model adds nothing.

Run with ``python -m tennis_edge.experiments.residual_vs_market``.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
import numpy.typing as npt

from tennis_edge.backtest import market_probability
from tennis_edge.corpus import Match, group_by_day, load_corpus
from tennis_edge.devig import DevigMethod
from tennis_edge.features import FEATURE_NAMES, build_features
from tennis_edge.ratings import RatingEngine

__all__ = ["Dataset", "build_dataset", "fit_logistic", "log_loss_of", "main"]

WARMUP_FROM = dt.date(2005, 1, 1)
TRAIN = (dt.date(2010, 1, 1), dt.date(2020, 12, 31))
VALIDATE = (dt.date(2021, 1, 1), dt.date(2023, 12, 31))
HOLDOUT_FROM = dt.date(2024, 1, 1)

_FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Dataset:
    """Features, market view and outcome, kept in separate arrays so they cannot mix."""

    features: _FloatArray
    market_logit: _FloatArray
    outcome: npt.NDArray[np.int_]
    dates: npt.NDArray[np.object_]
    matches: tuple[Match, ...]

    def mask(self, start: dt.date, end: dt.date | None = None) -> npt.NDArray[np.bool_]:
        selected = self.dates >= start
        if end is not None:
            selected &= self.dates <= end
        return np.asarray(selected, dtype=bool)


def _sigmoid(z: _FloatArray) -> _FloatArray:
    return np.asarray(1.0 / (1.0 + np.exp(-z)), dtype=np.float64)


def log_loss_of(probabilities: _FloatArray, outcomes: npt.NDArray[np.int_]) -> float:
    p = np.clip(probabilities, 1e-15, 1.0 - 1e-15)
    return float(-np.mean(outcomes * np.log(p) + (1 - outcomes) * np.log(1.0 - p)))


def build_dataset(
    matches: Sequence[Match], *, book: str = "pinnacle",
    method: DevigMethod = DevigMethod.POWER,
) -> Dataset:
    """Walk the corpus forward once, emitting a row per priced match.

    Ratings are read before the day is observed, so no feature can contain a same-day
    result. Matches without a price are skipped rather than imputed.
    """
    engine = RatingEngine()
    rows: list[tuple[float, ...]] = []
    logits: list[float] = []
    outcomes: list[int] = []
    dates: list[dt.date] = []
    kept: list[Match] = []
    for day, batch in group_by_day(matches):
        if day >= WARMUP_FROM:
            for match in sorted(batch, key=lambda m: (m.tour, m.player_a, m.player_b)):
                probability = market_probability(match, book=book, method=method)
                if probability is None:
                    continue
                clipped = min(max(probability, 1e-6), 1.0 - 1e-6)
                rows.append(build_features(engine, match))
                logits.append(math.log(clipped / (1.0 - clipped)))
                outcomes.append(1 if match.winner_is_a else 0)
                dates.append(day)
                kept.append(match)
        engine.observe(batch)
    return Dataset(
        features=np.asarray(rows, dtype=np.float64),
        market_logit=np.asarray(logits, dtype=np.float64),
        outcome=np.asarray(outcomes, dtype=int),
        dates=np.asarray(dates, dtype=object),
        matches=tuple(kept),
    )


def fit_logistic(
    design: _FloatArray,
    outcomes: npt.NDArray[np.int_],
    offset: _FloatArray,
    *,
    l2: float = 10.0,
    iterations: int = 60,
) -> _FloatArray:
    """Newton/IRLS logistic fit with a fixed offset and ridge penalty.

    The offset is what makes this a residual model: it enters the linear predictor with an
    implicit coefficient of 1 and is never estimated, so the fitted weights describe only
    what the offset failed to explain.
    """
    weights = np.zeros(design.shape[1], dtype=np.float64)
    for _ in range(iterations):
        mu = _sigmoid(offset + design @ weights)
        variance = np.clip(mu * (1.0 - mu), 1e-9, None)
        gradient = design.T @ (outcomes - mu) - l2 * weights
        hessian = (design * variance[:, None]).T @ design + l2 * np.eye(len(weights))
        step = np.linalg.solve(hessian, gradient)
        weights += step
        if np.max(np.abs(step)) < 1e-9:
            break
    return weights


def main() -> None:
    matches, stats = load_corpus()
    print(stats.summary())
    data = build_dataset(matches)
    train = data.mask(*TRAIN)
    validate = data.mask(*VALIDATE)
    holdout = data.mask(HOLDOUT_FROM)
    print(
        f"\n{len(data.outcome):,} priced matches | train {train.sum():,} "
        f"| validate {validate.sum():,} | holdout {holdout.sum():,} (untouched)\n"
    )

    mean = data.features[train].mean(axis=0)
    deviation = data.features[train].std(axis=0)
    deviation[deviation == 0] = 1.0
    scaled = (data.features - mean) / deviation

    print(f"{'model':<12}{'train':>10}{'validate':>11}")
    print("-" * 33)
    market_train = log_loss_of(_sigmoid(data.market_logit[train]), data.outcome[train])
    market_valid = log_loss_of(_sigmoid(data.market_logit[validate]), data.outcome[validate])
    print(f"{'market':<12}{market_train:>10.5f}{market_valid:>11.5f}")

    design_train = np.hstack([np.ones((int(train.sum()), 1)), scaled[train]])
    weights = fit_logistic(design_train, data.outcome[train], data.market_logit[train])
    residual_scores = []
    for mask in (train, validate):
        design = np.hstack([np.ones((int(mask.sum()), 1)), scaled[mask]])
        residual_scores.append(
            log_loss_of(_sigmoid(data.market_logit[mask] + design @ weights), data.outcome[mask])
        )
    print(f"{'residual':<12}{residual_scores[0]:>10.5f}{residual_scores[1]:>11.5f}")

    elo_column = FEATURE_NAMES.index("blended_elo_diff")
    elo_probability = np.clip(
        1.0 / (1.0 + 10.0 ** (-data.features[:, elo_column] / 400.0)), 1e-6, 1.0 - 1e-6
    )
    elo_logit = np.log(elo_probability / (1.0 - elo_probability))
    blend_design = np.column_stack(
        [np.ones(len(data.outcome)), elo_logit, data.market_logit]
    )
    blend = fit_logistic(
        blend_design[train], data.outcome[train],
        np.zeros(int(train.sum()), dtype=np.float64), l2=1e-6,
    )
    blend_scores = [
        log_loss_of(_sigmoid(blend_design[mask] @ blend), data.outcome[mask])
        for mask in (train, validate)
    ]
    print(f"{'blend':<12}{blend_scores[0]:>10.5f}{blend_scores[1]:>11.5f}")

    print(
        f"\nblend coefficients: intercept {blend[0]:+.4f}  "
        f"b1 model {blend[1]:+.4f}  b2 market {blend[2]:+.4f}"
    )
    verdict = (
        "the model adds nothing over the market"
        if abs(blend[1]) < 0.05 or residual_scores[1] >= market_valid
        else "the model adds measurable information over the market"
    )
    print(f"VERDICT: {verdict}")

    print("\nlargest residual coefficients (standardised):")
    for index in np.argsort(-np.abs(weights[1:]))[:8]:
        print(f"   {FEATURE_NAMES[index]:<22}{weights[1 + index]:+.4f}")


if __name__ == "__main__":
    main()
