"""The cheapest way to buy a whole tennis match, from every market Betfair offers on it.

TE-0009 asked whether Match Odds and Set Betting agree, and they do. This asks the strongest
available version of the same question, and one that cannot be improved on by adding another
market pair.

Match Odds, Set Betting and Number of Sets are all partitions of the same space — the final
set score. So the question is not "do these two books agree" but **"what is the cheapest way
to buy every outcome exactly once, using any runner from any of them"**. If that cheapest
cover costs less than one unit, the position is a lock regardless of which market was wrong.

A two-market check can only see a mispricing visible between those two books. This sees any
mispricing at all, because it prices the whole space directly.

Reported per horizon, with the same discipline TE-0009 arrived at the hard way: best-back
prices only, every leg required to carry real size, commission on winnings, and a cover that
is not exact is refused rather than scored.
"""
import collections
import statistics
import sys
from decimal import Decimal
from pathlib import Path

from tennis_edge.betfair import MarketHistory, read_markets
from tennis_edge.cover import best_cover, covered_outcomes, outcome_space
from tennis_edge.xmarket import MINIMUM_LEG_SIZE, Leg, surname_of

ROOT = ("/tmp/claude-0/-home-user-Moneymaker/"
        "b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted")
HORIZONS = (21_600, 3_600, 600)
#: Betfair TENNIS market base rate, charged on net winnings per market (TE-0042).
COMMISSION = Decimal("0.05")
MARKETS = ("MATCH_ODDS", "SET_BETTING", "NUMBER_OF_SETS")
MONTHS = {name: n for n, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1)}


def day_directories(root: str) -> list[Path]:
    days: list[Path] = []
    for tier in sorted(Path(root).iterdir()):
        for year in sorted(p for p in tier.iterdir() if p.is_dir()):
            for month in sorted(p for p in year.iterdir() if p.is_dir()):
                days.extend(p for p in month.iterdir() if p.is_dir())
    return sorted(days, key=lambda p: (int(p.parent.parent.name),
                                       MONTHS.get(p.parent.name, 0), int(p.name)))


def _infer_best_of(set_betting: MarketHistory | None) -> int | None:
    """Format from the Set Betting scorelines: a 3-x runner means best-of-five.

    Read from the market's own structure rather than assumed, and ``None`` when there is no
    Set Betting market to read it from — a guessed format would silently build the wrong
    outcome space and every cover over it would be meaningless.
    """
    if set_betting is None:
        return None
    from tennis_edge.xmarket import parse_set_runner
    wins = {p[1] for r in set_betting.runners
            if (p := parse_set_runner(r.name)) is not None}
    if wins == {2}:
        return 3
    if wins == {3}:
        return 5
    return None


def main() -> None:
    returns: dict[int, list[float]] = collections.defaultdict(list)
    stakes: dict[int, list[float]] = collections.defaultdict(list)
    leg_counts: collections.Counter[int] = collections.Counter()
    no_cover: collections.Counter[int] = collections.Counter()
    scanned = 0
    unusable = 0

    for day in day_directories(ROOT):
        markets = read_markets(day, market_types=MARKETS)
        by_event: dict[str, dict[str, MarketHistory]] = collections.defaultdict(dict)
        for market in markets:
            if "/" in market.event_name:      # doubles
                continue
            by_event[market.event_id][market.market_type] = market

        for _event, group in by_event.items():
            match_odds = group.get("MATCH_ODDS")
            if match_odds is None:
                continue
            active = [r for r in match_odds.runners
                      if r.status.upper() in {"ACTIVE", "WINNER", "LOSER"}]
            best_of = _infer_best_of(group.get("SET_BETTING"))
            if len(active) != 2 or best_of is None:
                unusable += 1
                continue
            sides = (active[0].name, active[1].name)
            if surname_of(sides[0]) == surname_of(sides[1]):
                unusable += 1
                continue
            space = outcome_space(best_of)
            scanned += 1

            for horizon in HORIZONS:
                candidates: list[tuple[frozenset[tuple[str, int, int]], Leg]] = []
                for kind, market in group.items():
                    for runner in market.runners:
                        outcomes = covered_outcomes(kind, runner.name, sides=sides,
                                                    best_of=best_of)
                        if outcomes is None:
                            continue
                        level = market.best_back_at(runner.selection_id,
                                                    seconds_before_off=horizon)
                        if level is None:
                            continue
                        candidates.append((frozenset(outcomes),
                                           Leg(price=level.price,
                                               size=float(level.size))))
                cover = best_cover(candidates, space, commission=COMMISSION,
                                   minimum_size=MINIMUM_LEG_SIZE)
                if cover is None:
                    no_cover[horizon] += 1
                    continue
                returns[horizon].append(cover.unit_return)
                stakes[horizon].append(cover.max_total_stake)
                leg_counts[len(cover.legs)] += 1

        print(f"  {day.parent.parent.name}-{day.parent.name}-{day.name}: "
              f"{scanned:,} matches scanned", flush=True)
        sys.stdout.flush()

    print(f"\nmatches with a usable market group: {scanned:,}  (unusable {unusable:,})")
    print(f"legs in the cheapest cover: {dict(sorted(leg_counts.items()))}")

    print(f"\nCHEAPEST EXACT COVER at best-back, size >= {MINIMUM_LEG_SIZE:.0f}, "
          f"{float(COMMISSION):.0%} commission")
    print(f"{'horizon':>9}{'covers':>9}{'none':>8}{'best':>10}{'p99':>10}"
          f"{'positive':>18}{'median stake':>14}")
    for horizon in HORIZONS:
        block = sorted(returns[horizon])
        if not block:
            print(f"{horizon:>9}{0:>9}{no_cover[horizon]:>8}   (no cover found)")
            continue
        p99 = block[int(0.99 * (len(block) - 1))]
        positive = [r for r in block if r > 0]
        print(f"{horizon:>9}{len(block):>9,}{no_cover[horizon]:>8,}"
              f"{block[-1]:>+10.4f}{p99:>+10.4f}"
              f"{len(positive):>10,} ({len(positive) / len(block):>5.2%})"
              f"{statistics.median(stakes[horizon]):>14.0f}")

    print("\nA cover costing under one unit is a lock whichever market was wrong. The")
    print("search is exhaustive over a four- or six-outcome space, so a negative best")
    print("here is not 'we did not find one' — it is 'there is not one'.")


if __name__ == "__main__":
    main()
