"""TE-0039: run the TE-0038 pre-registered round/tier stratification.

Declarations are in docs/TE-0038-round-tier-preregistration.md, committed before this
ran. Nothing here may deviate from them. Metric is log-score gain over the exchange
de-vigged price; strata and the single inferential contrast are fixed in advance.

Run from tennis-edge/: python tools/round_tier_strata.py
"""
from __future__ import annotations

import math
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.corpus import default_vintage_root, load_corpus  # noqa: E402
from tennis_edge.exchange_prices import read_prices  # noqa: E402
from tennis_edge.experiments.exchange_settlement import DEFAULT_PRICES  # noqa: E402
from tennis_edge.experiments.residual_edge import walk_forward  # noqa: E402
from tennis_edge.residual_features import build_residual_features  # noqa: E402

SEED = 20260730
DRAWS = 2000

#: Fixed by TE-0038 before any result was seen.
ROUND_GROUPS = {
    "1st Round": "EARLY", "2nd Round": "EARLY",
    "3rd Round": "MIDDLE", "4th Round": "MIDDLE", "Quarterfinals": "MIDDLE",
    "Semifinals": "LATE", "The Final": "LATE",
}
TIER_GROUPS = {
    "Grand Slam": "SLAM",
    # Amendment 1: the WTA renamed its tiers in 2021, so WTA1000/500/250 are the same
    # rungs as Premier Mandatory / Premier / International. Recorded in TE-0038.
    "Masters 1000": "MASTERS", "Masters": "MASTERS", "Masters Cup": "MASTERS",
    "Premier Mandatory": "MASTERS", "WTA1000": "MASTERS",
    "ATP500": "MID", "Premier": "MID", "Premier 5": "MID", "WTA500": "MID",
    "ATP250": "BASE", "International": "BASE", "International Gold": "BASE",
    "WTA250": "BASE",
}


def clustered_interval(days: list[list[float]], seed: int) -> tuple[float, float]:
    rng = random.Random(seed)
    draws = []
    for _ in range(DRAWS):
        sample: list[float] = []
        for _ in range(len(days)):
            sample.extend(days[rng.randrange(len(days))])
        draws.append(sum(sample) / len(sample) if sample else 0.0)
    draws.sort()
    return draws[int(0.025 * DRAWS)], draws[int(0.975 * DRAWS)]


def report(label: str, by_day: dict[object, list[float]]) -> float:
    days = list(by_day.values())
    flat = [g for d in days for g in d]
    if len(days) < 5 or not flat:
        print(f"    {label:<10} n={len(flat):>6,}  too few to score")
        return 0.0
    mean = sum(flat) / len(flat)
    lo, hi = clustered_interval(days, SEED)
    verdict = "clears zero" if lo > 0 else ("below zero" if hi < 0 else "spans zero")
    print(f"    {label:<10} n={len(flat):>6,}  days={len(days):>5,}  "
          f"gain={mean:+.6f}  CI95=[{lo:+.6f},{hi:+.6f}]  {verdict}")
    return mean


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    prices = {(p.date, p.tour, p.player_a, p.player_b): p
              for p in read_prices(Path(DEFAULT_PRICES))}

    vintage = default_vintage_root()
    matches, _stats = load_corpus(vintage)
    context = {(m.match_date, m.tour, m.player_a, m.player_b): (m.round_name, m.tier)
               for m in matches}

    scored = walk_forward(rows, names)
    by_round: dict[str, dict[object, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_tier: dict[str, dict[object, list[float]]] = defaultdict(lambda: defaultdict(list))
    unjoined = 0
    total = 0

    for row, p_model in scored:
        price = prices.get((row.date, row.tour, row.player_a, row.player_b))
        if price is None:
            continue
        ctx = context.get((row.date, row.tour, row.player_a, row.player_b))
        if ctx is None:
            unjoined += 1
            continue
        inv_a, inv_b = 1.0 / float(price.odds_a), 1.0 / float(price.odds_b)
        p_market = inv_a / (inv_a + inv_b)
        won = bool(row.won)
        gain = (math.log(p_model if won else 1 - p_model)
                - math.log(p_market if won else 1 - p_market))
        round_name, tier = ctx
        by_round[ROUND_GROUPS.get(round_name, "OTHER")][row.date].append(gain)
        by_tier[TIER_GROUPS.get(tier, "OTHER")][row.date].append(gain)
        total += 1

    print(f"joined {total:,} scored+priced rows; {unjoined:,} excluded (no corpus "
          f"context)\n")
    print("  BY ROUND (pre-registered strata):")
    means = {g: report(g, by_round[g]) for g in ("EARLY", "MIDDLE", "LATE", "OTHER")
             if by_round[g]}
    print("\n  BY TIER (secondary, descriptive):")
    for g in ("SLAM", "MASTERS", "MID", "BASE", "OTHER"):
        if by_tier[g]:
            report(g, by_tier[g])

    # THE declared inferential test: highest minus lowest round stratum, day-clustered.
    inferential = {g: m for g, m in means.items() if g in ("EARLY", "MIDDLE", "LATE")}
    if len(inferential) >= 2:
        hi_g = max(inferential, key=lambda g: inferential[g])
        lo_g = min(inferential, key=lambda g: inferential[g])
        pooled_days = sorted(set(by_round[hi_g]) | set(by_round[lo_g]))
        paired = [[g for g in by_round[hi_g].get(d, [])]
                  + [-g for g in by_round[lo_g].get(d, [])] for d in pooled_days]
        paired = [d for d in paired if d]
        flat = [x for d in paired for x in d]
        lo, hi = clustered_interval(paired, SEED)
        print(f"\n  PRIMARY CONTRAST ({hi_g} minus {lo_g}), day-clustered:")
        print(f"    difference {inferential[hi_g] - inferential[lo_g]:+.6f}  "
              f"paired-pool CI95=[{lo:+.6f},{hi:+.6f}]  "
              f"{'CLEARS ZERO' if lo > 0 or hi < 0 else 'SPANS ZERO'}  (n={len(flat):,})")

    print("\nTE-0038 pre-registered. Licenses no rule change, no filter, no threshold.")


if __name__ == "__main__":
    main()
