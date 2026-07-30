"""DIAGNOSTIC: what the frozen rule's equity curve actually does at flat stakes.

Staking literature is full of formulas that need an edge as input. This measures the
other half — the SHAPE of the realised bet sequence — so any staking discussion starts
from this system's own variance rather than a textbook's assumptions.

Reported, all in units of one flat stake:
  * terminal P&L, longest losing run, worst single day
  * maximum drawdown on the observed chronological order
  * the DISTRIBUTION of maximum drawdown under a day-block bootstrap, because the
    observed order is one realisation and the worst case matters more than the mean
  * ruin frequency: for a set of candidate budgets, the fraction of resampled histories
    that would have hit the floor at some point before recovering

LABELLED DIAGNOSTIC. These are hypothetical trade-through returns (TE-0019 supported
class), so the drawdowns are hypothetical too. Nothing here sizes a stake, changes a
threshold, or authorises spend: staking is deterministic tested code under human
approval, and an LLM never sizes a stake (CLAUDE.md rule 3).

Run from tennis-edge/: python tools/drawdown_profile.py
"""
from __future__ import annotations

import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.exchange_prices import read_prices  # noqa: E402
from tennis_edge.experiments.exchange_settlement import (  # noqa: E402
    DEFAULT_PRICES,
    settle,
)
from tennis_edge.experiments.residual_edge import walk_forward  # noqa: E402
from tennis_edge.fill_evidence import FillSupport  # noqa: E402
from tennis_edge.residual_features import build_residual_features  # noqa: E402

#: Fixed so two runs of this diagnostic report the same numbers.
SEED = 20260730
DRAWS = 2000
BUDGETS = (20, 30, 50, 75, 100, 150, 200)


def max_drawdown(profits: list[float]) -> tuple[float, float]:
    """Worst peak-to-trough decline, and the worst absolute level reached."""
    equity = 0.0
    peak = 0.0
    worst_dd = 0.0
    worst_level = 0.0
    for p in profits:
        equity += p
        peak = max(peak, equity)
        worst_dd = max(worst_dd, peak - equity)
        worst_level = min(worst_level, equity)
    return worst_dd, worst_level


def longest_losing_run(profits: list[float]) -> int:
    run = best = 0
    for p in profits:
        run = run + 1 if p < 0 else 0
        best = max(best, run)
    return best


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    prices = {(p.date, p.tour, p.player_a, p.player_b): p
              for p in read_prices(Path(DEFAULT_PRICES))}
    scored = walk_forward(rows, names)
    covered = [(r, p) for r, p in scored
               if (r.date, r.tour, r.player_a, r.player_b) in prices]
    bets = [b for b in settle(covered, prices, use_model=True)
            if b.support is FillSupport.SUPPORTED]
    bets.sort(key=lambda b: b.date)

    by_day: dict[object, list[float]] = defaultdict(list)
    for b in bets:
        by_day[b.date].append(b.profit)
    days = [by_day[d] for d in sorted(by_day)]
    profits = [p for day in days for p in day]

    total = sum(profits)
    observed_dd, observed_floor = max_drawdown(profits)
    print(f"bets {len(profits):,} over {len(days):,} days "
          f"(flat 1 unit, 2% commission, SUPPORTED fills only)\n")
    print(f"  terminal P&L           {total:+,.1f} units "
          f"({100 * total / len(profits):+.2f}% ROI)")
    print(f"  longest losing run     {longest_losing_run(profits)} bets")
    print(f"  worst single day       {min(sum(d) for d in days):+.1f} units")
    print(f"  max drawdown           {observed_dd:,.1f} units (observed order)")
    print(f"  deepest level reached  {observed_floor:+,.1f} units")

    # Day-block bootstrap: same days, resampled order. Preserves within-day correlation
    # (several bets on one card share conditions) while asking what other orderings of
    # the same history would have looked like.
    rng = random.Random(SEED)
    dds: list[float] = []
    floors: list[float] = []
    for _ in range(DRAWS):
        order = [days[rng.randrange(len(days))] for _ in range(len(days))]
        flat = [p for day in order for p in day]
        dd, floor = max_drawdown(flat)
        dds.append(dd)
        floors.append(floor)
    dds.sort()
    floors.sort()

    def q(values: list[float], p: float) -> float:
        return values[min(len(values) - 1, int(p * len(values)))]

    print(f"\n  day-block bootstrap, {DRAWS:,} resampled histories:")
    print(f"    max drawdown  median {q(dds, 0.5):,.1f}   "
          f"p90 {q(dds, 0.9):,.1f}   p99 {q(dds, 0.99):,.1f}   "
          f"worst {dds[-1]:,.1f} units")
    print(f"    deepest level median {q(floors, 0.5):+,.1f}   "
          f"p10 {q(floors, 0.1):+,.1f}   p1 {q(floors, 0.01):+,.1f}   "
          f"worst {floors[0]:+,.1f} units")

    print("\n  ruin frequency — fraction of resampled histories whose running P&L")
    print("  ever touches minus the budget (budget expressed in flat stakes):")
    for budget in BUDGETS:
        hit = sum(1 for f in floors if f <= -budget)
        print(f"    budget {budget:>4} units   {100 * hit / DRAWS:5.1f}% of histories "
              f"would have hit the floor")

    print("\nDIAGNOSTIC ONLY. Hypothetical trade-through returns; drawdowns are")
    print("hypothetical too. Nothing here sizes a stake or changes any threshold.")


if __name__ == "__main__":
    main()
