"""TE-0032: the untouched ten weeks — the frozen pipeline scored on data it never saw.

The exchange archive ends 2026-05-12 (a hard external fact: newer BASIC months would
need a Betfair login, which ADR 0015 rules out absolutely; the existing archives were
founder-provided files). The corpus runs to 2026-07-19. Every registered money
measurement therefore stops at the archive's edge — which leaves 2026-05-13 to
2026-07-19 as a window whose matches no money reading, no gate and no coefficient of
the frozen evaluations ever consumed.

DECLARATIONS, fixed before the run
----------------------------------
- Window: scored rows are corpus matches with 2026-05-13 <= date <= 2026-07-19, from
  the standard feature cache (vintage-2026-07-26; features are day-fresh walk-forward
  by construction). Both endpoints are external facts, not choices.
- Training: all cached rows with date <= 2026-05-12. ONE fold. The model is the same
  frozen machinery every prior harness used — ridge logistic residual on the Bet365
  de-vig market logit offset, L2 untouched, feature names taken from the rows.
- PRIMARY: mean paired per-match log-score gain (model minus market baseline) over the
  window; 95% day-clustered bootstrap CI (seed 20260725). A single new screening
  question, judged alone at alpha = 0.05.
- Diagnostics (licence nothing): per-month gains; window calibration slope of the
  model's logits.
- HONESTY LABELS: (1) this is quasi-prospective for the PIPELINE — the window's rows
  have appeared inside feature-delta measurements this month (S3/S8/S9 walked the full
  cache), but no threshold, feature choice or coefficient was ever tuned on them, and
  the coefficients used here are fit strictly on pre-window data; (2) the anchor is
  Bet365, NOT the exchange — the deployed exchange-anchored claim and every money
  number (fills, supported class, Roll band) remain UNTESTABLE on this window until an
  archive covering it exists. This run licenses a forecast-quality statement only.
- Stop rule: one run, recorded either way. A negative or null result is recorded with
  the same prominence as a positive one.
"""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from typing import cast

from tennis_edge.experiments.residual_edge import fit, predict
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features

TRAIN_THROUGH = dt.date(2026, 5, 12)
WINDOW_END = dt.date(2026, 7, 19)
ALPHA = 0.05


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(z, 35.0), -35.0)))


def main() -> None:
    rows = build_residual_features()
    train = [r for r in rows if r.date <= TRAIN_THROUGH]
    test = [r for r in rows if TRAIN_THROUGH < r.date <= WINDOW_END]
    print(f"cache rows {len(rows):,}; trained on {len(train):,} (<= {TRAIN_THROUGH}); "
          f"scored {len(test):,} in the untouched window")

    names = sorted({n for r in train for n in r.features})
    beta = fit(train, names)

    gains: list[tuple[dt.date, float]] = []
    by_month: dict[str, list[float]] = defaultdict(list)
    logits, wins = [], []
    for row in test:
        p = predict(row, beta)
        base = _sigmoid(row.market_logit)
        g = (math.log(p if row.won else 1 - p)
             - math.log(base if row.won else 1 - base))
        gains.append((row.date, g))
        by_month[row.date.strftime("%Y-%m")].append(g)
        logits.append(math.log(p / (1 - p)))
        wins.append(1.0 if row.won else 0.0)

    mean = math.fsum(g for _, g in gains) / len(gains)
    lo, hi = clustered_bootstrap(
        gains,
        statistic=lambda xs: math.fsum(
            cast(tuple[dt.date, float], x)[1] for x in xs) / len(xs),
        cluster_of=lambda x: cast(tuple[dt.date, float], x)[0],
        alpha=ALPHA)
    verdict = "clears zero" if lo > 0 else ("clears zero (negative)" if hi < 0
                                            else "spans zero")
    print(f"\nPRIMARY  model-minus-market log-score gain, Bet365 anchor")
    print(f"  n={len(gains):,}  {mean:+.6f} nats  CI95=[{lo:+.6f},{hi:+.6f}]  {verdict}")

    print("\nper-month (diagnostic):")
    for month in sorted(by_month):
        ms = by_month[month]
        print(f"  {month}: n={len(ms):,}  {math.fsum(ms)/len(ms):+.6f}")

    # Calibration slope: logistic of outcome on the model's own logit (Newton, 25 it).
    b0, b1 = 0.0, 1.0
    for _ in range(25):
        g0 = g1 = h00 = h01 = h11 = 0.0
        h00 = h11 = 1e-9
        for z, y in zip(logits, wins):
            mu = _sigmoid(b0 + b1 * z)
            w = mu * (1 - mu)
            e = y - mu
            g0 += e
            g1 += e * z
            h00 += w
            h01 += w * z
            h11 += w * z * z
        det = h00 * h11 - h01 * h01
        b0 += (h11 * g0 - h01 * g1) / det
        b1 += (h00 * g1 - h01 * g0) / det
    print(f"\ncalibration slope on the window (diagnostic): {b1:+.3f}")
    print("\nScope: forecast quality only; Bet365 anchor; every money claim remains")
    print("untestable on this window until an exchange archive covering it exists.")


if __name__ == "__main__":
    main()
