"""TE-0017 S9: the anchor temperature — δ = t−1 as a ridge-penalised pseudo-feature.

One nested parameter, shrunk toward the incumbent: δ=0 reproduces the exchange-anchored
model exactly, and the fitted probability is sigmoid((1+δ)·offset + Σβ·f). The honest
expectation, recorded at registration, is a kill — the test is well-powered only at the
top of its own +0.0001–0.0003 range, the 22 price-correlated features already partially
span the shrink direction, and the two mechanisms cited (errors-in-variables attenuation,
δ<0; favourite–longshot, δ>0) partially cancel.

**The governed exception, written down (TE-0017 §S9 pin):** the odds-in-features ban
exists to stop market information leaking into "fundamental" features. The pseudo-feature
here is the row's OWN offset at identical knowledge time — zero new information and no
new leakage surface; fitting δ merely rescales how hard the model leans on the anchor it
already uses. The name would not trip ``BANNED_FEATURE_TOKENS``, so this exception is
declared rather than slipped past the guard. Unlike the killed dispersion idea, this has
a live path: the served offset already IS an exchange-style price, so a fitted
temperature would deploy as one number with no new live inputs.

**Pins:** L2=25 and MIN_TRAIN=3000 untouched; the staleness interaction is dropped from
this registration (the held prints fields are post-horizon — lookahead); δ-by-stratum is
post-hoc diagnostic only and not computed here. Placebo: within-day permutation of the
pseudo-feature, judged on the PLACEBO'S CI (≤ 0), not its point estimate. Per-year δ
printed; sign stability required.

**Acceptance (family 4, 98.75%):** pass requires ALL of — paired CI clears zero at the
bar; δ sign-stable across years; placebo CI ≤ 0. A pass is measurement-only (serving δ
additionally requires stability across liquidity strata, because train-time noise differs
from serve-time input and attenuation-driven δ is expected not to transfer). Fail on any
criterion → record and stop; the row is never re-run to a different answer.
"""
from __future__ import annotations

import collections
import datetime as dt
import math
import random
from dataclasses import replace
from pathlib import Path
from typing import cast

from tennis_edge.exchange_prices import ExchangePrice, read_prices
from tennis_edge.experiments.exchange_anchor import (
    MIN_TRAIN,
    _log_score,
    _predict,
    _swap_offset,
    exchange_logit,
)
from tennis_edge.experiments.residual_edge import fit
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features

PRICES = Path("/home/user/tennis_edge_data/betfair_historical/"
              "exchange_prices_600s_v4.jsonl")
FAMILY_ALPHA = 0.0125
PSEUDO = "anchor_temp"
PLACEBO_SEED = 20260729


def _with_pseudo(row: Row, offset: float, value: float) -> Row:
    return replace(_swap_offset(row, offset),
                   features={**row.features, PSEUDO: value})


def _paired(name: str, pairs: list[tuple[dt.date, float]], *, alpha: float) -> None:
    mean = math.fsum(v for _d, v in pairs) / len(pairs)
    lo, hi = clustered_bootstrap(
        pairs, statistic=lambda items: math.fsum(  # type: ignore[arg-type,misc]
            v for _d, v in items) / len(items),  # type: ignore[union-attr]
        cluster_of=lambda item: cast(tuple[dt.date, float], item)[0],
        alpha=alpha)
    level = 100 * (1 - alpha)
    verdict = "clears zero" if lo > 0 else ("below zero" if hi < 0 else "spans zero")
    print(f"  {name:<44} {mean:+.6f} nats  CI{level:.2f}=[{lo:+.6f},{hi:+.6f}]  "
          f"{verdict}")


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    prices = {(p.date, p.tour, p.player_a, p.player_b): p for p in read_prices(PRICES)}
    covered = [(r, prices[(r.date, r.tour, r.player_a, r.player_b)]) for r in rows
               if (r.date, r.tour, r.player_a, r.player_b) in prices]
    by_year: dict[int, list[tuple[Row, ExchangePrice]]] = collections.defaultdict(list)
    for row, price in covered:
        by_year[row.date.year].append((row, price))

    rng = random.Random(PLACEBO_SEED)
    gains: list[tuple[dt.date, float]] = []
    placebo_gains: list[tuple[dt.date, float]] = []
    per_year_delta: dict[int, float] = {}

    train: list[tuple[Row, ExchangePrice]] = []
    for year in sorted(by_year):
        if len(train) >= MIN_TRAIN:
            exch_rows = [_swap_offset(r, exchange_logit(p)) for r, p in train]
            temp_rows = [_with_pseudo(r, exchange_logit(p), exchange_logit(p))
                         for r, p in train]
            # The placebo: the pseudo-feature permuted WITHIN each training day, so its
            # marginal distribution survives and only the row alignment dies.
            by_day: dict[dt.date, list[int]] = collections.defaultdict(list)
            for index, (r, _p) in enumerate(train):
                by_day[r.date].append(index)
            permuted = list(range(len(train)))
            for indices in by_day.values():
                shuffled = indices[:]
                rng.shuffle(shuffled)
                for source, target in zip(indices, shuffled, strict=True):
                    permuted[source] = target
            placebo_rows = [
                _with_pseudo(train[i][0], exchange_logit(train[i][1]),
                             exchange_logit(train[permuted[i]][1]))
                for i in range(len(train))
            ]

            beta_base = fit(exch_rows, names)
            beta_temp = fit(temp_rows, [*names, PSEUDO])
            beta_placebo = fit(placebo_rows, [*names, PSEUDO])
            per_year_delta[year] = beta_temp.get(PSEUDO, 0.0)

            for row, price in by_year[year]:
                offset = exchange_logit(price)
                base = _predict(row, offset, beta_base)
                temp = _predict(_with_pseudo(row, offset, offset), offset, beta_temp)
                plac = _predict(_with_pseudo(row, offset, offset), offset, beta_placebo)
                gains.append((row.date,
                              _log_score(temp, row.won) - _log_score(base, row.won)))
                placebo_gains.append((row.date,
                                      _log_score(plac, row.won)
                                      - _log_score(base, row.won)))
            print(f"  {year}: trained {len(train):,}, scored {len(by_year[year]):,}, "
                  f"delta {per_year_delta[year]:+.4f}", flush=True)
        train.extend(by_year[year])

    print(f"\nscored out-of-sample: {len(gains):,}")
    print("\nTHE ROW (family 4)")
    _paired("temperature over exchange+features", gains, alpha=FAMILY_ALPHA)
    print("\nPLACEBO (within-day permutation; judged on ITS CI <= 0)")
    _paired("placebo over exchange+features", placebo_gains, alpha=0.05)

    deltas = list(per_year_delta.values())
    stable = all(d > 0 for d in deltas) or all(d < 0 for d in deltas)
    print("\nper-year delta: " + ", ".join(
        f"{y}:{d:+.4f}" for y, d in sorted(per_year_delta.items())))
    stability = ("YES" if stable
                 else "NO — recorded as noise even if the pooled CI clears")
    print(f"sign-stable: {stability}")
    print("\nACCEPTANCE: pass requires the row clearing at 98.75%, sign stability, and")
    print("the placebo CI <= 0 — all three. A pass is measurement-only; serving a fitted")
    print("temperature would additionally require cross-stratum stability. Fail on any")
    print("criterion: record and stop; this row is never re-run to a different answer.")


if __name__ == "__main__":
    main()
