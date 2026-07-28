"""Does the network layer add forecast value? Closes the DR-FORECAST-LIT screening round.

Paired exactly like every kept layer: same rows, same walk-forward, same penalty, one
feature-set difference — baseline 22 features against baseline plus ``common_opponent_gap``,
``intransitivity`` and ``common_opponents``, day-clustered bootstrap on the per-match
log-score differences.

The estimator is advanced day by day alongside the rows under the standard eight-day
tournament lag, fed the full archive (main, qualifying/Challenger, ITF families) so the
shared-opponent graph spans the fields where players actually met.

**This run closes the multiplicity round.** Two families from the same research round were
screened: dispersion (+0.000082 [+0.000025, +0.000139]) and this. With two tests the
Bonferroni-adjusted bar is 97.5% per family; a result that clears 95% but not the adjusted
bar dies, and that pre-commitment applies to both members of the round, dispersion included.
"""
import math
from dataclasses import replace

from tennis_edge.experiments.residual_edge import (
    BOOTSTRAP_DRAWS,
    _day_of,
    _mean_gain,
    walk_forward,
)
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.network import NetworkEstimator, network_features
from tennis_edge.residual_features import build_residual_features
from tennis_edge.sackmann import load_matches

NEW = ("common_opponent_gap", "intransitivity", "common_opponents")


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})

    estimator = NetworkEstimator()
    estimator.queue(load_matches(families=("main", "qual_chall", "futures")))
    print("archive queued", flush=True)

    augmented = []
    covered = 0
    current = None
    for row in sorted(rows, key=lambda r: r.date):
        if row.date != current:
            estimator.advance_to(row.date)
            current = row.date
        extra = network_features(estimator, row.tour, row.player_a, row.player_b,
                                 when=row.date)
        if extra:
            covered += 1
            augmented.append(replace(row, features={**row.features, **extra}))
        else:
            augmented.append(row)
    print(f"rows {len(rows):,}  network features on {covered:,} "
          f"({100 * covered / len(rows):.1f}%)", flush=True)

    print("\nbaseline walk-forward:")
    base = walk_forward(sorted(rows, key=lambda r: r.date), names)
    print("\n+network walk-forward:")
    aug = walk_forward(augmented, list(names) + list(NEW))

    diffs = []
    for (row_b, p_b), (_row_a, p_a) in zip(base, aug):
        won = row_b.won == 1
        diffs.append((row_b.date,
                      math.log(p_a if won else 1 - p_a)
                      - math.log(p_b if won else 1 - p_b)))
    mean = math.fsum(g for _d, g in diffs) / len(diffs)
    lo, hi = clustered_bootstrap(diffs, statistic=_mean_gain, cluster_of=_day_of,
                                 draws=BOOTSTRAP_DRAWS)
    print(f"\nNETWORK LAYER, paired over {len(diffs):,} matches")
    print(f"  gain {mean:+.6f} nats  CI95=[{lo:+.6f},{hi:+.6f}]  "
          f"-> {'clears zero' if lo > 0 else 'does NOT clear zero'}")
    print("\n  This closes the screening round (two families: dispersion, network).")
    print("  Verdicts apply at the Bonferroni-adjusted bar, not the bare 95%.")


if __name__ == "__main__":
    main()
