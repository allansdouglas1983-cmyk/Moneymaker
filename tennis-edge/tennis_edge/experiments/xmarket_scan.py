"""Do Betfair's own tennis markets agree with each other? Scan of the June 2026 corpus.

Eight findings in this programme are about beating the market's forecast, and they say that
is hard and worth little. This asks something the market can get wrong without anybody being
wrong about tennis: **Match Odds and Set Betting on the same match are related by identity**,
since for a best-of-three P(A wins) is exactly P(A 2-0) + P(A 2-1). If they disagree, one of
them is wrong, and which one does not matter to someone taking both sides.

The scan reports two things and never conflates them:

1. **The coherence gap**, on de-vigged probabilities — how much the two markets disagree.
   Expected to be common: Set Betting is thinner and slower than Match Odds.
2. **The dutch return**, on the actual **best-back prices** with commission — whether that
   disagreement can be transacted. Back A on Match Odds, back every one of B's set scores,
   and see whether the guaranteed payout beats the outlay. This is the only number that is
   worth anything, and it is reported per horizon because a lock that exists a day out and
   not at the off is not a lock.

Doubles are excluded throughout: the runner names carry a slash, the corpus is full of them,
and they are a different market with different liquidity.

**What would make this real.** A positive dutch return, at a size the book can absorb,
appearing often enough to be worth watching for. Unlike a forecasting edge it needs no
argument about whether the model is better than the market — it either locks or it does not.
"""
import collections
import statistics
import sys
from decimal import Decimal
from pathlib import Path

from tennis_edge.betfair import MarketHistory, Runner, read_markets
from tennis_edge.xmarket import (
    MINIMUM_LEG_SIZE,
    Leg,
    SetBettingView,
    align_sides,
    coherence_gap,
    fillable_dutch,
)

ROOT = ("/tmp/claude-0/-home-user-Moneymaker/"
        "b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted")
HORIZONS = (21_600, 3_600, 600)
#: Betfair TENNIS market base rate, charged on net winnings per market (TE-0042).
COMMISSION = Decimal("0.05")
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


def _best_backs(market: MarketHistory, horizon: int) -> dict[int, Leg] | None:
    """Best back price AND the size behind it, for every runner, or None if any is missing.

    Size is carried from here on. The first version of this scan returned prices alone and
    reported a six-hundred-percent locked return, which was entirely an artefact of thin Set
    Betting legs showing a nominal quote with a couple of pounds behind it.
    """
    out: dict[int, Leg] = {}
    for runner in market.runners:
        level = market.best_back_at(runner.selection_id, seconds_before_off=horizon)
        if level is None:
            return None
        out[runner.selection_id] = Leg(price=level.price, size=float(level.size))
    return out


def _aligned_sides(
    match_odds: MarketHistory, set_betting: MarketHistory, active: list[Runner]
) -> tuple[list[int], list[int]] | None:
    """Set-betting selection ids grouped to match the Match Odds runner order.

    By name, never by position. The two markets order their runners independently, and
    assuming they agree backs one player on Match Odds together with that same player's set
    scores — an unhedged double reported as a locked position.
    """
    aligned = align_sides(
        match_odds_names=tuple(r.name for r in active),
        set_betting_names=tuple(r.name for r in set_betting.runners),
    )
    if aligned is None:
        return None
    ids = [r.selection_id for r in set_betting.runners]
    return [ids[i] for i in aligned[0]], [ids[i] for i in aligned[1]]


def main() -> None:
    gaps: dict[int, list[float]] = collections.defaultdict(list)
    returns: dict[int, list[float]] = collections.defaultdict(list)
    stakes: dict[int, list[float]] = collections.defaultdict(list)
    unfillable: collections.Counter[int] = collections.Counter()
    paired = 0
    unaligned = 0
    singles_events = 0
    no_partner = 0

    for day in day_directories(ROOT):
        markets = read_markets(day, market_types=("MATCH_ODDS", "SET_BETTING"))
        by_event: dict[str, dict[str, MarketHistory]] = collections.defaultdict(dict)
        for market in markets:
            if "/" in market.event_name:      # doubles
                continue
            by_event[market.event_id][market.market_type] = market

        for _event, pair in by_event.items():
            match_odds = pair.get("MATCH_ODDS")
            set_betting = pair.get("SET_BETTING")
            if match_odds is None:
                continue
            singles_events += 1
            if set_betting is None:
                no_partner += 1
                continue
            active = [r for r in match_odds.runners
                      if r.status.upper() in {"ACTIVE", "WINNER", "LOSER"}]
            if len(active) != 2:
                continue
            sides = _aligned_sides(match_odds, set_betting, active)
            if sides is None:
                unaligned += 1
                continue
            paired += 1

            for horizon in HORIZONS:
                mo = _best_backs(match_odds, horizon)
                sb = _best_backs(set_betting, horizon)
                if mo is None or sb is None:
                    continue
                # De-vig each market to a distribution before comparing them; comparing a
                # de-vigged number with a raw one reports the margin as a disagreement.
                mo_total = sum(1 / float(leg.price) for leg in mo.values())
                mo_a = (1 / float(mo[active[0].selection_id].price)) / mo_total
                sb_total = sum(1 / float(leg.price) for leg in sb.values())
                side_a, side_b = sides
                sb_a = sum(1 / float(sb[s].price) for s in side_a) / sb_total
                view = SetBettingView(probability_a=sb_a, probability_b=1.0 - sb_a)
                gaps[horizon].append(coherence_gap(match_odds_a=mo_a, set_betting=view))

                # Both orientations: A on Match Odds against B's scores, and the mirror.
                for mo_side, sb_side in ((active[0].selection_id, side_b),
                                         (active[1].selection_id, side_a)):
                    position = fillable_dutch(
                        (mo[mo_side], *(sb[s] for s in sb_side)),
                        commission=COMMISSION, minimum_size=MINIMUM_LEG_SIZE,
                    )
                    if position is None:
                        unfillable[horizon] += 1
                        continue
                    returns[horizon].append(position.unit_return)
                    stakes[horizon].append(position.max_total_stake)
        print(f"  {day.parent.parent.name}-{day.parent.name}-{day.name}: "
              f"{paired:,} paired so far", flush=True)
        sys.stdout.flush()

    print(f"\nsingles Match Odds markets: {singles_events:,}")
    print(f"  with a Set Betting partner: {paired:,}")
    print(f"  without one:                {no_partner:,}")
    print(f"  unaligned by name:          {unaligned:,}")

    print(f"\n{'horizon':>9}{'n':>8}{'median |gap|':>14}{'p90 |gap|':>12}"
          f"{'gap > 5pts':>12}")
    for horizon in HORIZONS:
        block = gaps[horizon]
        if not block:
            continue
        absolute = sorted(abs(g) for g in block)
        p90 = absolute[int(0.9 * (len(absolute) - 1))]
        big = sum(1 for g in absolute if g > 0.05) / len(absolute)
        print(f"{horizon:>9}{len(block):>8,}{statistics.median(absolute):>14.4f}"
              f"{p90:>12.4f}{big:>11.1%}")

    print(f"\nDUTCH RETURN at best-back prices with size >= {MINIMUM_LEG_SIZE:.0f}, "
          f"{float(COMMISSION):.0%} commission")
    print(f"{'horizon':>9}{'fillable':>10}{'unfillable':>12}{'best':>10}{'p99':>10}"
          f"{'positive':>18}{'median stake':>14}")
    for horizon in HORIZONS:
        block = sorted(returns[horizon])
        if not block:
            print(f"{horizon:>9}{0:>10}{unfillable[horizon]:>12}   (none fillable)")
            continue
        p99 = block[int(0.99 * (len(block) - 1))]
        positive = [r for r in block if r > 0]
        median_stake = statistics.median(stakes[horizon])
        print(f"{horizon:>9}{len(block):>10,}{unfillable[horizon]:>12,}"
              f"{block[-1]:>+10.4f}{p99:>+10.4f}"
              f"{len(positive):>10,} ({len(positive) / len(block):>5.2%})"
              f"{median_stake:>14.0f}")

    print("\nA gap is the two markets disagreeing. A positive dutch return is the only")
    print("number that can be transacted, and it is reported separately for that reason.")


if __name__ == "__main__":
    main()
