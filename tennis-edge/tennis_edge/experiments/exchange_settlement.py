"""Settle the model at real exchange prices, over six and a half years instead of eleven months.

Every money conclusion this project has drawn about Betfair rested on 3,742 matches from a
single eleven-month window, because that is all the Tennis-Data `BFE` column covers. TE-0012
established what that was worth: at the per-bet variance this rule produces, resolving a 2%
return needs on the order of 31,000 bets, and there were 2,760. The answer was not "no edge";
it was "no information".

The Betfair Historical BASIC archive supplies **27,209 priced matches, 2015-07-01 to
2022-03-14**. That is the sample problem addressed. This is the measurement.

**Three readings, and the difference between them is the point.**

1. **All fills credited.** What a conventional backtest reports. Every bet the rule fires is
   assumed to have been matched at the last-traded price.
2. **Supported fills only.** A bet counts only where the market later traded at that price or
   better before the off, so somebody demonstrably was matched there after us. Across the
   table, 64.4% of side-prices are SUPPORTED, 18.7% UNSUPPORTED and 16.9% NO_EVIDENCE — a
   conventional backtest credits itself with roughly a third of fills the record does not
   support, and the gap between readings 1 and 2 is exactly that error, priced.
3. **The control**, under both. The identical rule driven by the *market's own* de-vigged
   probability instead of the model's. On the exchange this is not an idle comparison: it is
   a Bet365-versus-Betfair disagreement play, and it has beaten the model twice already on
   the small sample. If it beats the model here too, the edge such as it is belongs to the
   price difference and not to the forecast.

**What this cannot say.** BASIC is a last-trade trace with no ladder and no traded volume, so
none of these numbers is a proven realised return, and none is reported as one. The
traded-through test converts an unstated assumption into a stated, falsifiable one; it does
not conjure depth. `DR-TENNIS-MICROSTRUCTURE-001` asks what standard a trace-only money claim
should meet, and until that returns these are hypothetical returns with their evidence split
shown alongside.

**Clustering.** Intervals are block-bootstrapped over whole days, never over bets. Bets on the
same day share a market state and are not independent; treating them as independent is the
single easiest way to manufacture a confident wrong answer.
"""
from __future__ import annotations

import collections
import datetime as dt
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from tennis_edge.experiments.residual_edge import _sigmoid, walk_forward
from tennis_edge.exchange_prices import ExchangePrice, read_prices
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.fill_evidence import FillSupport, LiquidityStratum, stratify
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features
from tennis_edge.upcoming import break_even_probability

#: Betfair Rewards flat rate, charged on net winnings. Confirmation of current UK mechanics
#: is DR-TENNIS-MICROSTRUCTURE-001 question 6; 2% is what the platform has always modelled.
COMMISSION = Decimal("0.02")

BOOTSTRAP_DRAWS = 2000

DEFAULT_PRICES = ("/home/user/tennis_edge_data/betfair_historical/"
                  "exchange_prices_600s.jsonl")


@dataclass(frozen=True)
class Bet:
    date: dt.date
    profit: float
    support: FillSupport
    stratum: LiquidityStratum
    odds: float
    #: Joined back to the raw trace by the execution-cost band; the readings above never
    #: look at them.
    market_id: str = ""
    side: str = ""
    won: bool = False


def _mean(items: Sequence[object]) -> float:
    bets = [i for i in items if isinstance(i, Bet)]
    return sum(b.profit for b in bets) / len(bets) if bets else 0.0


def _day(item: object) -> dt.date:
    assert isinstance(item, Bet)
    return item.date


def settle(scored: list[tuple[Row, float]], prices: dict[tuple[dt.date, str, str, str],
                                                         ExchangePrice],
           *, use_model: bool) -> list[Bet]:
    """Flat one unit whenever the probability clears the commission-aware break-even.

    No required-edge buffer. A threshold is the classic place to launder an overfit, since
    every threshold is a parameter and the best one is always found after the fact.
    """
    rate = float(COMMISSION)
    bets: list[Bet] = []
    for row, model_p in scored:
        price = prices.get((row.date, row.tour, row.player_a, row.player_b))
        if price is None:
            continue
        probability = model_p if use_model else _sigmoid(row.market_logit)
        for probability_side, odds, won, support, prints, side in (
            (probability, price.odds_a, price.won_a, price.support_a, price.prints_a,
             "a"),
            (1.0 - probability, price.odds_b, not price.won_a, price.support_b,
             price.prints_b, "b"),
        ):
            if odds <= 1:
                continue
            if probability_side <= float(break_even_probability(odds,
                                                               commission=COMMISSION)):
                continue
            gross = float(odds) - 1.0
            bets.append(Bet(
                date=row.date,
                profit=gross * (1.0 - rate) if won else -1.0,
                support=support,
                stratum=stratify(prints),
                odds=float(odds),
                market_id=price.market_id,
                side=side,
                won=won,
            ))
    return bets


def report(name: str, bets: list[Bet]) -> None:
    if len(bets) < 100:
        print(f"  {name:<40} {len(bets)} bets — too few to score")
        return
    roi = _mean(bets)
    lo, hi = clustered_bootstrap(bets, statistic=_mean, cluster_of=_day,
                                 draws=BOOTSTRAP_DRAWS)
    days = len({b.date for b in bets})
    verdict = "clears zero" if lo > 0 else ("below zero" if hi < 0 else "spans zero")
    print(f"  {name:<40} bets={len(bets):6,}  days={days:5,}  ROI={roi * 100:+6.2f}%  "
          f"CI95=[{lo * 100:+6.2f}%,{hi * 100:+6.2f}%]  {verdict}")


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})

    path = Path(DEFAULT_PRICES)
    prices = {(p.date, p.tour, p.player_a, p.player_b): p for p in read_prices(path)}
    print(f"exchange prices: {len(prices):,} matches from {path.name}")
    days = {d for d, _t, _a, _b in prices}
    print(f"  span {min(days)} .. {max(days)}   {len(days):,} distinct days")

    print("\nwalk-forward:")
    scored = walk_forward(rows, names)
    covered = [(r, p) for r, p in scored
               if (r.date, r.tour, r.player_a, r.player_b) in prices]
    print(f"\nout-of-sample matches with an exchange price: {len(covered):,} "
          f"of {len(scored):,} scored")

    model = settle(covered, prices, use_model=True)
    control = settle(covered, prices, use_model=False)

    print("\nALL FILLS CREDITED — what a conventional backtest reports")
    report("model", model)
    report("control (market's own probability)", control)

    print("\nSUPPORTED FILLS ONLY — the market later traded there or better")
    report("model", [b for b in model if b.support is FillSupport.SUPPORTED])
    report("control", [b for b in control if b.support is FillSupport.SUPPORTED])

    print("\nTHE FILLS A CONVENTIONAL BACKTEST WOULD HAVE INVENTED")
    for support in (FillSupport.UNSUPPORTED, FillSupport.NO_EVIDENCE):
        report(f"model, {support.value.lower()}",
               [b for b in model if b.support is support])

    print("\nMODEL BY LIQUIDITY STRATUM (prints after the horizon)")
    for stratum in LiquidityStratum:
        report(f"model, {stratum.value.lower()}",
               [b for b in model if b.stratum is stratum])

    counts = collections.Counter(b.support for b in model)
    total = sum(counts.values())
    if total:
        print("\nFILL EVIDENCE OVER THE BETS THE RULE ACTUALLY FIRED")
        for support in FillSupport:
            print(f"  {support.value:<14} {counts[support]:6,}  "
                  f"({100 * counts[support] / total:5.1f}%)")

    print("\nREADING")
    print("  None of these is a realised return. BASIC is a last-trade trace with no ladder")
    print("  and no traded volume, so a fill is supported or unsupported by the record, not")
    print("  proven. The gap between 'all fills' and 'supported only' is the size of the")
    print("  assumption a conventional backtest makes silently.")


if __name__ == "__main__":
    main()
