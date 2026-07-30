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
from tennis_edge.refresh import latest_vintage  # noqa: E402
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


def difference_interval(
    hi_days: dict[object, list[float]],
    lo_days: dict[object, list[float]],
    seed: int,
) -> tuple[float, float]:
    """Day-clustered bootstrap of the DIFFERENCE of two stratum means.

    Resample days, then recompute each stratum's mean within the resample and take the
    difference. Pooling one stratum's gains with the other's negated gains and averaging
    the pool is NOT this quantity — it is a size-weighted blend, and with strata of very
    different sizes it lands somewhere else entirely. That error produced an interval
    that did not contain its own point estimate, which is how it was caught.
    """
    days = sorted(set(hi_days) | set(lo_days))
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(DRAWS):
        hi_vals: list[float] = []
        lo_vals: list[float] = []
        for _ in range(len(days)):
            d = days[rng.randrange(len(days))]
            hi_vals.extend(hi_days.get(d, ()))
            lo_vals.extend(lo_days.get(d, ()))
        if hi_vals and lo_vals:
            draws.append(sum(hi_vals) / len(hi_vals) - sum(lo_vals) / len(lo_vals))
    draws.sort()
    return draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws))]


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

    vintage = latest_vintage(default_vintage_root())
    assert vintage is not None
    matches, _stats = load_corpus(vintage.root)
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
        lo, hi = difference_interval(by_round[hi_g], by_round[lo_g], SEED)
        point = inferential[hi_g] - inferential[lo_g]
        n = sum(len(v) for v in by_round[hi_g].values()) + \
            sum(len(v) for v in by_round[lo_g].values())
        print(f"\n  PRIMARY CONTRAST ({hi_g} minus {lo_g}), day-clustered:")
        print(f"    difference {point:+.6f}  CI95=[{lo:+.6f},{hi:+.6f}]  "
              f"{'CLEARS ZERO' if lo > 0 or hi < 0 else 'SPANS ZERO'}  (n={n:,})")

    # SELECTION ADJUSTMENT. The declared test is "highest minus lowest stratum", which
    # PICKS the extremes and then tests them. A naive interval on a selected contrast is
    # anti-conservative: with three strata you are effectively taking the largest of
    # three pairwise gaps and judging it as though it were the only one. The declaration
    # said max-minus-min, so that is what is reported above — but the honest reading
    # needs the null distribution of THAT statistic, not of a pre-chosen pair.
    #
    # Cluster-respecting null: centre every stratum on its own mean (so all strata truly
    # have equal expectation), then resample days and recompute max-minus-min. Variance,
    # stratum sizes and within-day correlation are all preserved; only the signal is
    # removed.
    groups = [g for g in ("EARLY", "MIDDLE", "LATE") if by_round[g]]
    if len(groups) >= 2:
        centred = {g: {d: [x - means[g] for x in vals]
                       for d, vals in by_round[g].items()} for g in groups}
        all_days = sorted({d for g in groups for d in centred[g]})
        rng = random.Random(SEED)
        null_spreads = []
        for _ in range(DRAWS):
            picked = [all_days[rng.randrange(len(all_days))] for _ in range(len(all_days))]
            draw_means = {}
            for g in groups:
                vals = [x for d in picked for x in centred[g].get(d, ())]
                if vals:
                    draw_means[g] = sum(vals) / len(vals)
            if len(draw_means) >= 2:
                null_spreads.append(max(draw_means.values()) - min(draw_means.values()))
        null_spreads.sort()
        observed = max(means[g] for g in groups) - min(means[g] for g in groups)
        exceed = sum(1 for s in null_spreads if s >= observed)
        p = (exceed + 1) / (len(null_spreads) + 1)
        crit = null_spreads[int(0.95 * len(null_spreads))]
        print(f"\n  SELECTION-ADJUSTED (null distribution of max-minus-min):")
        print(f"    observed spread {observed:+.6f}   null 95th pct {crit:+.6f}   "
              f"p={p:.4f}   "
              f"{'SURVIVES selection' if p < 0.05 else 'DOES NOT survive selection'}")

    print("\nTE-0038 pre-registered. Licenses no rule change, no filter, no threshold.")


if __name__ == "__main__":
    main()
