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

from tennis_edge.betfair import MarketHistory, read_markets
from tennis_edge.xmarket import SetBettingView, coherence_gap, dutch_return, parse_set_runner

ROOT = ("/tmp/claude-0/-home-user-Moneymaker/"
        "b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted")
HORIZONS = (21_600, 3_600, 600)
COMMISSION = Decimal("0.02")
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


def _best_backs(market: MarketHistory, horizon: int) -> dict[int, Decimal] | None:
    """Best back price for every runner, or None if any is missing.

    All or nothing: a dutch needs every leg, and a partial book would invent a lock out of an
    incomplete market.
    """
    out: dict[int, Decimal] = {}
    for runner in market.runners:
        level = market.best_back_at(runner.selection_id, seconds_before_off=horizon)
        if level is None:
            return None
        out[runner.selection_id] = level.price
    return out


def _split_sides(market: MarketHistory) -> tuple[list[int], list[int]] | None:
    """Set-betting selections grouped by which player they belong to."""
    parsed = [(r.selection_id, parse_set_runner(r.name)) for r in market.runners]
    if any(p is None for _s, p in parsed):
        return None
    names = sorted({p[0] for _s, p in parsed if p is not None})
    if len(names) != 2:
        return None
    first, second = names
    a = [s for s, p in parsed if p is not None and p[0] == first]
    b = [s for s, p in parsed if p is not None and p[0] == second]
    return (a, b) if a and b else None


def main() -> None:
    gaps: dict[int, list[float]] = collections.defaultdict(list)
    returns: dict[int, list[float]] = collections.defaultdict(list)
    paired = 0
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
            sides = _split_sides(set_betting)
            active = [r for r in match_odds.runners
                      if r.status.upper() in {"ACTIVE", "WINNER", "LOSER"}]
            if sides is None or len(active) != 2:
                continue
            paired += 1

            for horizon in HORIZONS:
                mo = _best_backs(match_odds, horizon)
                sb = _best_backs(set_betting, horizon)
                if mo is None or sb is None:
                    continue
                # De-vig each market to a distribution before comparing them; comparing a
                # de-vigged number with a raw one reports the margin as a disagreement.
                mo_total = sum(1 / float(p) for p in mo.values())
                mo_a = (1 / float(mo[active[0].selection_id])) / mo_total
                sb_total = sum(1 / float(p) for p in sb.values())
                side_a, side_b = sides
                sb_a = sum(1 / float(sb[s]) for s in side_a) / sb_total
                view = SetBettingView(probability_a=sb_a, probability_b=1.0 - sb_a)
                gaps[horizon].append(coherence_gap(match_odds_a=mo_a, set_betting=view))

                # Both orientations: A on Match Odds against B's scores, and the mirror.
                for mo_side, sb_side in ((active[0].selection_id, side_b),
                                         (active[1].selection_id, side_a)):
                    returns[horizon].append(dutch_return(
                        match_odds_back_a=mo[mo_side],
                        set_back_prices_b=tuple(sb[s] for s in sb_side),
                        commission=COMMISSION,
                    ))
        print(f"  {day.parent.parent.name}-{day.parent.name}-{day.name}: "
              f"{paired:,} paired so far", flush=True)
        sys.stdout.flush()

    print(f"\nsingles Match Odds markets: {singles_events:,}")
    print(f"  with a Set Betting partner: {paired:,}")
    print(f"  without one:                {no_partner:,}")

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

    print(f"\nDUTCH RETURN at best-back prices, {float(COMMISSION):.0%} commission")
    print(f"{'horizon':>9}{'legs':>8}{'best':>10}{'p99':>10}{'positive':>11}")
    for horizon in HORIZONS:
        block = sorted(returns[horizon])
        if not block:
            continue
        p99 = block[int(0.99 * (len(block) - 1))]
        positive = sum(1 for r in block if r > 0)
        print(f"{horizon:>9}{len(block):>8,}{block[-1]:>+10.4f}{p99:>+10.4f}"
              f"{positive:>7,} ({positive / len(block):.2%})")

    print("\nA gap is the two markets disagreeing. A positive dutch return is the only")
    print("number that can be transacted, and it is reported separately for that reason.")


if __name__ == "__main__":
    main()
