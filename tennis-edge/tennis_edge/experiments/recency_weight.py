"""TE-0041 item 18: is the stationarity assumption wrong? Recency-weighted vs equal-weighted training.

THE QUESTION. Training weights 2003-2026 equally, yet three independent diagnostics mark
a 2023/24 break: TE-0019 (the exchange anchor's lead over Bet365 halved when 2023-2026
entered), TE-0028 (the anchor-temperature parameter flips sign across the boundary), and
the TE-0024/0029 staleness family. TE-0033's decomposition exonerated composition with
precision and showed the MODEL'S own edge held — but nobody has asked the training
question: does a fit that trusts recent matches more than old ones price the next year
better than the fit that trusts 2003 as much as 2025? This is the cheapest offline test
of the regime hypothesis, and it has never been run.

DECLARATIONS — committed before any result is computed.

Q1 (PRIMARY). Exponential recency weighting, half-life 3 YEARS, versus the deployed
equal-weighted fit, under the frozen walk-forward protocol (fit strictly on prior years,
predict the next; identical folds, identical features, identical L2 = 25). Endpoint: the
paired per-match log-score difference d = loss_stationary - loss_weighted over ALL
out-of-sample scored matches, mean with a day-clustered bootstrap 95% CI (2,000 draws,
library seed). Positive d favours weighting. Verdict rule: CI above zero -> stationarity
is wrong and an era-weighted registration becomes a governed candidate; CI spans zero ->
unresolved; CI below zero -> the regime hypothesis loses its cheapest support.

WHY HALF-LIFE 3 YEARS, FIXED A PRIORI: it is the length of the post-break era
(2024-2026) at measurement time — the structure the diagnostics point at — chosen from
the calendar, not from any result. It is NOT tuned; the grid below cannot promote a
different value.

Q2 (SECONDARY, declared). The same paired difference restricted to prediction years
2024-2026, where the regime hypothesis predicts the help concentrates. Reported with its
own CI, labelled secondary — it cannot rescue a null Q1.

EXPLORATORY (declared as such). Half-lives {1, 2, 5, 8} years, reported without
verdicts. Multiplicity note: FIVE weighted fits run in total; only Q1 carries a verdict,
so no correction is applied to it; the grid is descriptive and none of its cells may be
quoted as a finding.

WEIGHT DEFINITION. For a training row aged `a` days at the fold's first prediction day:
w = 0.5 ** (a / (h * 365.25)). Ages are recomputed per fold — a 2015 match is old when
pricing 2026 and young when pricing 2016 — so weighting respects knowledge time exactly
as the walk-forward does. L2 stays 25, deliberately: down-weighting old rows shrinks the
effective sample so the ridge binds relatively harder, and that is part of what "trust
recent data more" operationally means. Declared, not compensated.

GUARD (runs before any result is read). With all weights forced to 1.0 the weighted fit
must reproduce `fit_coefficients` exactly (max |delta beta| < 1e-10 on the first fold).
If the guard fails the run aborts — a weighted refit that cannot reproduce the
unweighted answer at uniform weights is measuring its own bug.

SCOPE. Forecast quality only (log score vs outcome). No money reading, no firing rule,
no serving change from this run regardless of outcome — adoption would be a separate
governed slice with its own registration (repo convention, cf. TE-0023/TE-0026 labels).

Run from tennis-edge/:  python -m tennis_edge.experiments.recency_weight
"""
from __future__ import annotations

import collections
import datetime as dt
import math
from typing import Sequence

from tennis_edge.experiments.residual_edge import (
    FIRST_SCORED_YEAR,
    _sigmoid,
    predict,
)
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features
from tennis_edge.residual_model import L2, fit_coefficients

PRIMARY_HALF_LIFE_YEARS = 3.0
EXPLORATORY_HALF_LIVES = (1.0, 2.0, 5.0, 8.0)
SECONDARY_ERA_FIRST_YEAR = 2024
BOOTSTRAP_DRAWS = 2000
_DAYS_PER_YEAR = 365.25
_MAX_NEWTON_STEPS = 50
_MAX_HALVINGS = 20
_GUARD_TOLERANCE = 1e-10


def _weights(train: Sequence[Row], as_of: dt.date, half_life_years: float) -> list[float]:
    """w = 0.5 ** (age_days / half_life_days), age measured at the fold boundary."""
    half_life_days = half_life_years * _DAYS_PER_YEAR
    return [0.5 ** ((as_of - row.date).days / half_life_days) for row in train]


def _compile(rows: Sequence[Row], names: Sequence[str]) -> list[tuple[float, int, list[tuple[int, float]]]]:
    index = {name: i for i, name in enumerate(names)}
    compiled = []
    for row in rows:
        pairs = [(index[n], x) for n, x in row.features.items() if n in index]
        compiled.append((row.market_logit, int(row.won), pairs))
    return compiled


def _penalised_loglik(compiled, beta: list[float], weights: Sequence[float], l2: float) -> float:
    total = -0.5 * l2 * sum(b * b for b in beta)
    for (offset, won, pairs), w in zip(compiled, weights):
        z = offset
        for i, x in pairs:
            z += beta[i] * x
        p = min(max(_sigmoid(z), 1e-12), 1 - 1e-12)
        total += w * (math.log(p) if won else math.log(1.0 - p))
    return total


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting — mirrors residual_model._solve."""
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("singular")
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(col + 1, n):
            factor = a[r][col] / a[col][col]
            for c in range(col, n + 1):
                a[r][c] -= factor * a[col][c]
    out = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = a[r][n] - sum(a[r][c] * out[c] for c in range(r + 1, n))
        out[r] = s / a[r][r]
    return out


def fit_weighted(rows: Sequence[Row], names: Sequence[str],
                 weights: Sequence[float], *, l2: float = L2) -> dict[str, float]:
    """The residual_model Newton fit with per-row weights on the likelihood.

    Identical structure to `fit_coefficients` — same offset treatment, same ridge, same
    line search — with every row's gradient/Hessian/log-likelihood contribution scaled
    by its weight. At uniform weights it must reproduce the unweighted fit exactly; the
    harness runs that identity as a hard guard before any result is read.
    """
    compiled = _compile(rows, names)
    width = len(names)
    beta = [0.0] * width
    current = _penalised_loglik(compiled, beta, weights, l2)
    for _ in range(_MAX_NEWTON_STEPS):
        gradient = [-l2 * b for b in beta]
        hessian = [[l2 if i == j else 0.0 for j in range(width)] for i in range(width)]
        for (offset, won, pairs), w in zip(compiled, weights):
            z = offset
            for i, x in pairs:
                z += beta[i] * x
            p = _sigmoid(z)
            residual = w * (won - p)
            curvature = w * p * (1 - p)
            for i, x in pairs:
                gradient[i] += x * residual
                wx = curvature * x
                for j, y in pairs:
                    hessian[i][j] += wx * y
        try:
            step = _solve(hessian, gradient)
        except ValueError:
            break
        scale = 1.0
        for _attempt in range(_MAX_HALVINGS):
            candidate = [b + scale * s for b, s in zip(beta, step)]
            value = _penalised_loglik(compiled, candidate, weights, l2)
            if value >= current:
                beta, current = candidate, value
                break
            scale *= 0.5
        else:
            break
        if max(abs(scale * s) for s in step) < 1e-10:
            break
    return dict(zip(names, beta))


def _log_loss(p: float, won: int) -> float:
    q = min(max(p if won else 1.0 - p, 1e-12), 1.0 - 1e-12)
    return -math.log(q)


def walk_forward_weighted(rows: list[Row], names: list[str],
                          half_life_years: float) -> list[tuple[Row, float]]:
    """The frozen walk-forward protocol, with per-fold recency weights on the fit."""
    by_year: dict[int, list[Row]] = collections.defaultdict(list)
    for row in rows:
        by_year[row.date.year].append(row)
    ordered = sorted(by_year)
    years = [y for y in ordered if y >= FIRST_SCORED_YEAR]
    out: list[tuple[Row, float]] = []
    train: list[Row] = [r for y in ordered if y < years[0] for r in by_year[y]]
    for year in years:
        if len(train) >= 5000:
            as_of = dt.date(year, 1, 1)
            beta = fit_weighted(train, names, _weights(train, as_of, half_life_years))
            for row in by_year[year]:
                out.append((row, predict(row, beta)))
            print(f"  h={half_life_years:g}y {year}: trained on {len(train):,}, "
                  f"scored {len(by_year[year]):,}", flush=True)
        train.extend(by_year[year])
    return out


def _guard(rows: list[Row], names: list[str]) -> None:
    """Uniform weights must reproduce the unweighted fit. Aborts the run otherwise."""
    by_year: dict[int, list[Row]] = collections.defaultdict(list)
    for row in rows:
        by_year[row.date.year].append(row)
    ordered = sorted(by_year)
    first_train = [r for y in ordered if y < FIRST_SCORED_YEAR for r in by_year[y]]
    reference = fit_coefficients(first_train, names, l2=L2)
    uniform = fit_weighted(first_train, names, [1.0] * len(first_train), l2=L2)
    worst = max(abs(reference[n] - uniform[n]) for n in names)
    if worst >= _GUARD_TOLERANCE:
        raise SystemExit(f"GUARD FAILED: uniform-weight fit diverges from "
                         f"fit_coefficients by {worst:.3e} — the weighted fit is "
                         f"measuring its own bug. No results were read.")
    print(f"guard: uniform-weight identity holds (max |dbeta| = {worst:.2e})", flush=True)


def _paired(stationary: list[tuple[Row, float]], weighted: list[tuple[Row, float]],
            *, era_from: int | None = None) -> tuple[int, float, float, float]:
    weighted_by_key = {(r.date, r.tour, r.player_a, r.player_b): p for r, p in weighted}
    diffs: list[tuple[dt.date, float]] = []
    for row, p_stationary in stationary:
        if era_from is not None and row.date.year < era_from:
            continue
        p_weighted = weighted_by_key.get((row.date, row.tour, row.player_a, row.player_b))
        if p_weighted is None:
            continue
        diffs.append((row.date,
                      _log_loss(p_stationary, int(row.won))
                      - _log_loss(p_weighted, int(row.won))))
    mean = sum(d for _day, d in diffs) / len(diffs)
    lo, hi = clustered_bootstrap(
        diffs, statistic=lambda items: sum(d for _x, d in items) / len(items),  # type: ignore[misc]
        cluster_of=lambda item: item[0],  # type: ignore[union-attr,index]
        draws=BOOTSTRAP_DRAWS)
    return len(diffs), mean, lo, hi


def _report(label: str, n: int, mean: float, lo: float, hi: float) -> None:
    verdict = ("WEIGHTING WINS" if lo > 0 else
               ("stationary wins" if hi < 0 else "unresolved (spans zero)"))
    print(f"  {label:<28} n={n:6,}  d={mean:+.6f} nats  "
          f"CI95 [{lo:+.6f}, {hi:+.6f}]  {verdict}", flush=True)


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    print(f"rows: {len(rows):,}   features: {len(names)}", flush=True)

    _guard(rows, names)

    print("\nstationary (the deployed protocol):", flush=True)
    from tennis_edge.experiments.residual_edge import walk_forward
    stationary = walk_forward(rows, names)

    print(f"\nPRIMARY: half-life {PRIMARY_HALF_LIFE_YEARS:g} years", flush=True)
    primary = walk_forward_weighted(rows, names, PRIMARY_HALF_LIFE_YEARS)

    print("\nQ1 — pooled paired log-score difference (positive favours weighting):")
    _report("Q1 pooled (PRIMARY)", *_paired(stationary, primary))
    print("Q2 — 2024-2026 era only (SECONDARY, declared):")
    _report("Q2 post-2024", *_paired(stationary, primary, era_from=SECONDARY_ERA_FIRST_YEAR))

    print("\nEXPLORATORY grid — descriptive only, no verdicts, may not be quoted:")
    for half_life in EXPLORATORY_HALF_LIVES:
        scored = walk_forward_weighted(rows, names, half_life)
        n, mean, lo, hi = _paired(stationary, scored)
        print(f"  h={half_life:g}y pooled              n={n:6,}  d={mean:+.6f}  "
              f"[{lo:+.6f}, {hi:+.6f}]", flush=True)
        n, mean, lo, hi = _paired(stationary, scored, era_from=SECONDARY_ERA_FIRST_YEAR)
        print(f"  h={half_life:g}y post-2024           n={n:6,}  d={mean:+.6f}  "
              f"[{lo:+.6f}, {hi:+.6f}]", flush=True)

    print("\nREADING")
    print("  One run, as declared. Q1 carries the only verdict; Q2 is secondary and the")
    print("  grid is descriptive. No serving rule changes from this run regardless —")
    print("  adopting a weighted fit would be its own governed slice.")


if __name__ == "__main__":
    main()
