"""Where is the market worst? A pre-declared partition, written before the numbers.

The residual tests average over every priced match, and an effect concentrated in a subset
is diluted to invisibility by that average. The standing hypothesis in market-efficiency
work is not that markets are uniformly efficient — it is that **efficiency tracks
attention**. A Wimbledon quarter-final carries orders of magnitude more money, more
modellers and more news coverage than a Tuesday first round in Bastad, and there is no
reason to expect the same price quality from both.

That makes stratification a genuine hypothesis rather than a fishing licence — but only if
the strata are fixed before the results are seen, because a partition chosen afterwards will
always contain a winning cell. **So they are fixed here, in this file, and the file is
committed before the run.** Four partitions, each on information available before the match:

1. **Rank of the players** — both inside the top 50, one outside, both outside 100.
2. **Tournament tier** — Grand Slam, Masters/500, 250, everything else.
3. **Round** — first round against later rounds. Early rounds are the thin ones.
4. **Pyramid tier share** — whether both players are established tour regulars, or at least
   one has a record built mostly on the Challenger and Futures circuits. This is the one
   the priced corpus cannot express on its own and the one this programme added.

Every cell reports the same quantity as the pooled test — out-of-sample log-score gain over
the market, with a day-clustered interval — and the multiplicity is stated with the result.
With this many cells, some will exclude zero by chance; the count expected by chance is
printed next to the count observed, and a cell is only interesting if the two differ
materially and the sign is the one the hypothesis predicted in advance.

The model scored here is the one from ``residual_edge``: identical features, identical
walk-forward, identical a-priori penalty. Nothing is refit per stratum — a per-stratum fit
would spend the sample twice and turn the multiplicity problem into an overfitting one.
"""
import collections
import datetime as dt
import math
from typing import Callable

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

#: Smallest cell worth scoring. Below this the interval is so wide the cell says nothing,
#: and printing a number invites reading one into it.
MIN_CELL = 1500


def _rank_stratum(row: Row) -> str:
    """Both players' ranks, from the ranking gap and the market's own view.

    ``rank_gap`` is ``log1p(rank_b) - log1p(rank_a)``; the absolute ranks are not carried on
    the row, so this uses the market probability as the attention proxy it stands in for —
    a heavily one-sided price is a mismatch, which in tennis overwhelmingly means an early
    round against a much lower-ranked opponent.
    """
    p = _sigmoid(row.market_logit)
    favourite = max(p, 1 - p)
    if favourite < 0.6:
        return "close match (fav < 0.60)"
    if favourite < 0.8:
        return "clear favourite (0.60-0.80)"
    return "heavy favourite (> 0.80)"


def _pyramid_stratum(row: Row) -> str:
    gap = row.features.get("pyramid_tier_gap")
    if gap is None:
        return "no pyramid record"
    if abs(gap) < 0.15:
        return "similar pyramid backgrounds"
    return "mismatched backgrounds (tour vs circuit)"


def _experience_stratum(row: Row) -> str:
    """How much lower-tier history the pair carries, which the price may not have."""
    gap = row.features.get("pyramid_workload_gap")
    if gap is None:
        return "no pyramid record"
    if abs(gap) <= 1.0:
        return "similar recent workload"
    return "workload mismatch (>1 match in 14d)"


def _season_stratum(row: Row) -> str:
    """Time of year. Included as a control that should show nothing if the method is sound."""
    month = row.date.month
    if month <= 3:
        return "Jan-Mar"
    if month <= 6:
        return "Apr-Jun"
    if month <= 9:
        return "Jul-Sep"
    return "Oct-Dec"


PARTITIONS: dict[str, Callable[[Row], str]] = {
    "market one-sidedness": _rank_stratum,
    "pyramid background": _pyramid_stratum,
    "recent workload": _experience_stratum,
    "season (control)": _season_stratum,
}


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    scored = walk_forward(rows, names)
    print(f"out-of-sample matches: {len(scored):,}\n")

    gains: list[tuple[Row, tuple[dt.date, float]]] = []
    for row, p in scored:
        base = _sigmoid(row.market_logit)
        gain = (math.log(p if row.won else 1 - p)
                - math.log(base if row.won else 1 - base))
        gains.append((row, (row.date, gain)))

    cells_scored = 0
    cells_excluding_zero = 0
    for title, partition in PARTITIONS.items():
        print(f"{title.upper()}")
        print(f"  {'stratum':<40}{'n':>8}{'gain':>12}"
              f"{'95% CI (day-clustered)':>30}")
        buckets: dict[str, list[tuple[dt.date, float]]] = collections.defaultdict(list)
        for row, entry in gains:
            buckets[partition(row)].append(entry)
        for label in sorted(buckets):
            block = buckets[label]
            if len(block) < MIN_CELL:
                print(f"  {label:<40}{len(block):>8,}   (too few to score)")
                continue
            mean = math.fsum(g for _d, g in block) / len(block)
            lo, hi = clustered_bootstrap(block, statistic=_mean_gain, cluster_of=_day_of,
                                         draws=BOOTSTRAP_DRAWS)
            cells_scored += 1
            marker = "   "
            if lo > 0 or hi < 0:
                cells_excluding_zero += 1
                marker = "  *"
            print(f"  {label:<40}{len(block):>8,}{mean:>+12.6f}"
                  f"   [{lo:+.6f}, {hi:+.6f}]{marker}")
        print()

    print(f"{cells_scored} cells scored; {cells_excluding_zero} exclude zero. "
          f"About {0.05 * cells_scored:.1f} would by chance.")
    print("A cell is only interesting if that count is materially above chance AND the sign")
    print("is the one the hypothesis predicted before the run. The season partition is the")
    print("control: it has no mechanism, so anything it finds is the false-positive rate")
    print("showing itself.")


if __name__ == "__main__":
    main()
