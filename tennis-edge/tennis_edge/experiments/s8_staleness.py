"""TE-0017 S8: pricing the weekly-cadence staleness penalty.

Every published gain was measured with day-fresh engine state; the product serves from a
Monday snapshot, so a Friday prediction misses up to six days of results and
``state_stale_days`` is displayed without anyone knowing what a stale day costs.

**Pre-check result (recorded before this ran):** the provider's own Last-Modified stamps
show weekly publication (current-season files stamped Sun/Mon evening, then untouched for
the following six days). The daily-recovery arm is therefore structurally ~zero and the
family-3 switch rule CANNOT fire; this sweep prices the penalty honestly, nothing more.

**Declared (TE-0017 §S8, binding):**

- Lag applies to SCORED features only; training stays day-fresh, mirroring deployment.
- The baseline builder is untouched (lag modes are a separate additive walk with their
  own cache keys), so the lag=0 acceptance criterion — published numbers byte-for-byte —
  holds by construction: lag 0 IS the published cache.
- **Primary endpoint: Monday-schedule mode vs day-fresh on the DEPLOYED configuration**,
  family 3 at the four-family bar (98.75%). The registration named the then-deployed
  10-feature model; the deployed model today is the 22-feature fit, and a penalty quoted
  from an undeployed configuration measures a product that does not exist — so the
  deployed-today set is primary, stated here rather than slipped.
- Other lags {1,3,5,7} are a descriptive dose-response curve; monotonicity is a validity
  check; **stale beating fresh is a suspected harness bug per house rules**, never a
  finding.
- Estimand: average per-match log-loss penalty over all scored rows — automatically
  weighted by the historical match-day distribution. **No post-hoc day-of-week
  re-slicing.**
- Row-alignment discipline: a row present in one build and not the other (a player
  crossing the 5-match floor at the shifted cutoff) is a typed count, and the paired
  statistic runs on the intersection.
- Honesty note, pre-stated: the serve and pyramid engines hold tournaments to week close
  by construction, so the penalty loads on the Elo/durability engines and the
  same-tournament-form story is structurally muted.
"""
from __future__ import annotations

import collections
import datetime as dt
import math
from typing import cast

from tennis_edge.experiments.residual_edge import _sigmoid, fit
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_lagged_features, build_residual_features

FAMILY_ALPHA = 0.0125
MODES = ("monday", "lag1", "lag3", "lag5", "lag7")
FIRST_SCORED_YEAR = 2012
MIN_TRAIN = 5000


def _log_loss(p: float, won: int) -> float:
    q = min(max(p, 1e-12), 1 - 1e-12)
    return -math.log(q if won else 1.0 - q)


def _predict(row: Row, beta: dict[str, float]) -> float:
    return _sigmoid(row.market_logit + math.fsum(
        b * row.features[n] for n, b in beta.items() if n in row.features))


def _paired(name: str, pairs: list[tuple[dt.date, float]], *, alpha: float) -> None:
    mean = math.fsum(v for _d, v in pairs) / len(pairs)
    lo, hi = clustered_bootstrap(
        pairs, statistic=lambda items: math.fsum(  # type: ignore[arg-type,misc]
            v for _d, v in items) / len(items),  # type: ignore[union-attr]
        cluster_of=lambda item: cast(tuple[dt.date, float], item)[0],
        alpha=alpha)
    level = 100 * (1 - alpha)
    verdict = "clears zero" if lo > 0 else ("below zero" if hi < 0 else "spans zero")
    print(f"  {name:<34} n={len(pairs):6,}  {mean:+.6f} nats  "
          f"CI{level:.2f}=[{lo:+.6f},{hi:+.6f}]  {verdict}")


def main() -> None:
    fresh = build_residual_features()
    names = sorted({n for r in fresh for n in r.features})
    fresh_by_key = {(r.date, r.tour, r.player_a, r.player_b): r for r in fresh}
    by_year: dict[int, list[Row]] = collections.defaultdict(list)
    for row in fresh:
        by_year[row.date.year].append(row)
    years = [y for y in sorted(by_year) if y >= FIRST_SCORED_YEAR]

    # One set of day-fresh fits, reused for every mode: training mirrors deployment.
    betas: dict[int, dict[str, float]] = {}
    train: list[Row] = [r for y in sorted(by_year) if y < years[0] for r in by_year[y]]
    for year in years:
        if len(train) >= MIN_TRAIN:
            betas[year] = fit(train, names)
        train.extend(by_year[year])
    print(f"day-fresh fits for {len(betas)} scored years", flush=True)

    results: dict[str, tuple[float, float, float]] = {}
    for mode in MODES:
        lagged = build_lagged_features(mode)
        lag_by_key = {(r.date, r.tour, r.player_a, r.player_b): r for r in lagged}
        pairs: list[tuple[dt.date, float]] = []
        only_fresh = only_lag = 0
        for key, row in fresh_by_key.items():
            if row.date.year not in betas:
                continue
            lag_row = lag_by_key.get(key)
            if lag_row is None:
                only_fresh += 1
                continue
            beta = betas[row.date.year]
            penalty = (_log_loss(_predict(lag_row, beta), row.won)
                       - _log_loss(_predict(row, beta), row.won))
            pairs.append((row.date, penalty))
        scored_keys = {k for k in fresh_by_key
                       if fresh_by_key[k].date.year in betas}
        only_lag = sum(1 for k in lag_by_key
                       if k not in fresh_by_key and lag_by_key[k].date.year in betas)
        alpha = FAMILY_ALPHA if mode == "monday" else 0.05
        label = "PRIMARY monday-schedule" if mode == "monday" else f"dose {mode}"
        print(f"\n{label}: aligned {len(pairs):,} of {len(scored_keys):,} scored rows "
              f"(fresh-only {only_fresh:,}, lag-only {only_lag:,})")
        _paired("stale-minus-fresh log-loss penalty", pairs, alpha=alpha)
        mean = math.fsum(v for _d, v in pairs) / len(pairs)
        results[mode] = (mean, 0.0, 0.0)

    print("\nDOSE-RESPONSE (validity check: penalty should not shrink as lag grows)")
    for mode in ("lag1", "lag3", "lag5", "lag7"):
        if mode in results:
            print(f"  {mode}: {results[mode][0]:+.6f} nats")

    print("\nREADING")
    print("  The provider publishes weekly (pre-check), so the switch rule cannot fire;")
    print("  this number is what state_stale_days silently costs, on the record. A")
    print("  negative penalty clearing zero would be a suspected harness bug, not a")
    print("  finding. Decision threshold context: 0.0002 nats (durability scale).")


if __name__ == "__main__":
    main()
