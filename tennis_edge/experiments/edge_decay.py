"""Is the edge still there, or did it live in the 2010s?

The pooled result — +0.000862 nats over fifteen years — is the average of fifteen annual
answers, and an average is exactly the wrong summary if the thing being averaged is dying.
Betting markets get sharper: more participants, better models, faster information. An edge
measured over 2012–2026 could be a large effect in 2013 that has since been arbitraged away,
and the pooled number would look identical either way.

That matters more here than it usually would, because the *reason* the model works is that
the closing price under-weights information from below the main tour. Lower-tier data has
become far more available over the period being measured. If anything in this programme was
going to decay, it is this.

Three views of the same walk-forward, none of which needs a new fit:

1. **Year by year.** The gain in each out-of-sample year, with its own day-clustered
   interval. Noisy individually; the shape is the point.
2. **Recent versus early.** The two halves, each with an interval, so "is it smaller now"
   gets a number rather than an impression.
3. **A trend test.** Regress the per-match gain on the year index. A negative slope that
   excludes zero is decay; anything else is not, and the interval is reported either way so
   a flat result cannot be read as reassurance it has not earned.

Run after ``residual_edge``; this reads the same cached features and costs seconds.
"""
import collections
import datetime as dt
import math
from typing import cast

from tennis_edge.experiments.residual_edge import (
    BOOTSTRAP_DRAWS,
    _day_of,
    _mean_gain,
    _sigmoid,
    walk_forward,
)
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features

#: Smallest year worth reporting an interval for.
MIN_YEAR_ROWS = 500


def _gain(row: Row, p: float) -> float:
    base = _sigmoid(row.market_logit)
    return (math.log(p if row.won else 1 - p)
            - math.log(base if row.won else 1 - base))


def _interval(block: list[tuple[dt.date, float]]) -> tuple[float, float, float]:
    mean = math.fsum(g for _d, g in block) / len(block)
    lo, hi = clustered_bootstrap(block, statistic=_mean_gain, cluster_of=_day_of,
                                 draws=BOOTSTRAP_DRAWS)
    return mean, lo, hi


def _slope(points: list[tuple[float, float]]) -> float:
    """Ordinary least squares slope of gain on year index."""
    n = len(points)
    mean_x = math.fsum(x for x, _y in points) / n
    mean_y = math.fsum(y for _x, y in points) / n
    denominator = math.fsum((x - mean_x) ** 2 for x, _y in points)
    if denominator <= 0:
        return 0.0
    return math.fsum((x - mean_x) * (y - mean_y) for x, y in points) / denominator


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    scored = walk_forward(rows, names)
    print(f"\nout-of-sample matches: {len(scored):,}")

    by_year: dict[int, list[tuple[dt.date, float]]] = collections.defaultdict(list)
    for row, p in scored:
        by_year[row.date.year].append((row.date, _gain(row, p)))

    print("\n1. YEAR BY YEAR")
    print(f"   {'year':>6}{'n':>9}{'gain':>13}{'95% CI (day-clustered)':>32}")
    years = sorted(by_year)
    for year in years:
        block = by_year[year]
        if len(block) < MIN_YEAR_ROWS:
            print(f"   {year:>6}{len(block):>9,}   (too few to score)")
            continue
        mean, lo, hi = _interval(block)
        marker = "  *" if lo > 0 or hi < 0 else "   "
        print(f"   {year:>6}{len(block):>9,}{mean:>+13.6f}   "
              f"[{lo:+.6f}, {hi:+.6f}]{marker}")

    print("\n2. EARLY VERSUS RECENT")
    midpoint = years[len(years) // 2]
    halves = {
        f"{years[0]}-{midpoint - 1}": [g for y in years if y < midpoint
                                       for g in by_year[y]],
        f"{midpoint}-{years[-1]}": [g for y in years if y >= midpoint
                                    for g in by_year[y]],
    }
    for label, block in halves.items():
        mean, lo, hi = _interval(block)
        print(f"   {label:<14}{len(block):>9,}{mean:>+13.6f}   [{lo:+.6f}, {hi:+.6f}]")

    print("\n3. TREND")
    # One point per match, so the slope is per-match gain against year. Bootstrapping whole
    # days rather than matches for the same reason every other interval here does: matches
    # on one day share tournament conditions and are not independent evidence.
    points = [(float(date.year), gain)
              for block in by_year.values() for date, gain in block]
    slope = _slope(points)

    def slope_statistic(sample: object) -> float:
        rows = cast(list[tuple[dt.date, float]], sample)
        return _slope([(float(d.year), g) for d, g in rows])

    everything = [entry for block in by_year.values() for entry in block]
    lo, hi = clustered_bootstrap(everything, statistic=slope_statistic,
                                 cluster_of=_day_of, draws=BOOTSTRAP_DRAWS)
    verdict = ("DECAYING — the slope is negative and excludes zero" if hi < 0 else
               "STRENGTHENING — the slope is positive and excludes zero" if lo > 0 else
               "no detectable trend either way at this power")
    print(f"   gain per additional year  {slope:+.8f}  [{lo:+.8f}, {hi:+.8f}]")
    print(f"   -> {verdict}")
    print("\n   A flat slope is not proof the edge is durable; it is failure to detect")
    print("   decay on fifteen annual points, which is a weak test by construction.")


if __name__ == "__main__":
    main()
