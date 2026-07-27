"""Is the Betfair result evidence of no edge, or is it not evidence of anything?

Every money conclusion in this project has hung on one venue, because Betfair is the only
one that cannot limit a winning account. That test returned +0.48% on 2,854 bets with an
interval four points wide either side of zero, and I reported it as "undecided". Undecided
is right, but it understates the problem: tennis-data.co.uk only began carrying Betfair
prices in 2025, so the exchange column covers **4% of the corpus and two seasons**, against
twenty-four for Bet365 and twenty-three for Pinnacle.

An interval that wide on a sample that small cannot distinguish a 3% edge from a 3% loss.
Calling it "no edge on Betfair" would be reading a conclusion out of an absence of data.

This asks two questions the earlier report could not:

**How much data would it take?** Given the observed per-bet variance, the sample needed to
resolve a plausible edge at conventional power. If the answer is far beyond two seasons then
the Betfair question is not currently answerable and no amount of modelling changes that.

**Is 2025-26 simply a bad period?** The decisive control. The same rule, the same model, the
same matches, settled at Pinnacle — first over Pinnacle's whole history, then restricted to
exactly the window where Betfair prices exist. If Pinnacle also goes flat in that window,
the Betfair figure is a period effect and not a venue effect, and the two seasons say
nothing about the exchange in particular.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Sequence

from tennis_edge.experiments.residual_edge import fit, predict, walk_forward
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features
from tennis_edge.upcoming import break_even_probability

from decimal import Decimal

#: Betfair Rewards flat rate, charged on net winnings.
COMMISSION = 0.02

#: The effect worth resolving. Not tuned: it is roughly the return the Pinnacle and Max
#: columns show, so it is the size of edge this model would plausibly have if it has one.
TARGET_ROI = 0.02

#: Conventional two-sided 5% test at 80% power.
Z_ALPHA = 1.959963984540054
Z_POWER = 0.8416212335729143


@dataclass(frozen=True)
class Bet:
    date: dt.date
    profit: float


def settle(scored: list[tuple[Row, float]], book: str,
           window: tuple[dt.date, dt.date] | None = None) -> list[Bet]:
    """Flat one unit whenever the model clears the commission-aware break-even.

    Identical rule to the money report, so the numbers here are comparable to it. The
    optional window restricts to a date range without refitting anything — the model is the
    same, only the settlement venue and period change.
    """
    bets: list[Bet] = []
    for row, probability in scored:
        if window is not None and not (window[0] <= row.date <= window[1]):
            continue
        for side, model_p in ((("a"), probability), (("b"), 1.0 - probability)):
            odds = (row.odds_a if side == "a" else row.odds_b).get(book)
            if odds is None or odds <= 1.0:
                continue
            break_even = break_even_probability(Decimal(str(odds)),
                                                commission=Decimal(str(COMMISSION)))
            if model_p <= break_even:
                continue
            won = (row.won == 1) if side == "a" else (row.won == 0)
            # Commission is charged on net winnings, so a winner returns (O-1)(1-c).
            profit = (odds - 1.0) * (1.0 - COMMISSION) if won else -1.0
            bets.append(Bet(date=row.date, profit=profit))
    return bets


def _mean(items: Sequence[object]) -> float:
    bets = [i for i in items if isinstance(i, Bet)]
    return sum(b.profit for b in bets) / len(bets) if bets else 0.0


def _day(item: object) -> dt.date:
    assert isinstance(item, Bet)
    return item.date


def required_sample(bets: list[Bet], target: float = TARGET_ROI) -> int:
    """Bets needed to resolve a ``target`` return at 5% / 80%, given observed variance.

    n = (z_a + z_b)^2 * sigma^2 / delta^2. The variance is per-bet profit variance, which on
    a flat stake is dominated by the price distribution rather than by the edge — so this is
    a property of the betting rule, not of whether the rule is any good.
    """
    if len(bets) < 2:
        return 0
    mean = _mean(bets)
    variance = sum((b.profit - mean) ** 2 for b in bets) / (len(bets) - 1)
    return math.ceil((Z_ALPHA + Z_POWER) ** 2 * variance / (target ** 2))


def report(name: str, bets: list[Bet]) -> None:
    if not bets:
        print(f"  {name:<34} no bets")
        return
    roi = _mean(bets)
    lo, hi = clustered_bootstrap(bets, statistic=_mean, cluster_of=_day)
    need = required_sample(bets)
    span = (hi - lo) * 100
    print(f"  {name:<34} bets={len(bets):6,}  ROI={roi * 100:+6.2f}%  "
          f"CI95=[{lo * 100:+6.2f}%,{hi * 100:+6.2f}%]  width={span:5.2f}pp  "
          f"n*={need:,}")


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})

    betfair_rows = [r for r in rows if "betfair" in r.odds_a and "betfair" in r.odds_b]
    if not betfair_rows:
        raise SystemExit("no Betfair prices in the corpus")
    first = min(r.date for r in betfair_rows)
    last = max(r.date for r in betfair_rows)
    print(f"corpus: {len(rows):,} priceable matches")
    print(f"Betfair prices: {len(betfair_rows):,} matches "
          f"({100 * len(betfair_rows) / len(rows):.1f}%), {first} to {last}")
    pinnacle_rows = [r for r in rows if "pinnacle" in r.odds_a]
    print(f"Pinnacle prices: {len(pinnacle_rows):,} matches "
          f"({100 * len(pinnacle_rows) / len(rows):.1f}%), "
          f"{min(r.date for r in pinnacle_rows)} to {max(r.date for r in pinnacle_rows)}")

    print("\nwalk-forward:")
    scored = walk_forward(rows, names)

    print("\nSETTLED AT EACH VENUE (same model, same rule, flat 1u)")
    report("betfair, all available", settle(scored, "betfair"))
    report("pinnacle, all available", settle(scored, "pinnacle"))

    print("\nTHE CONTROL: the same window, a different venue")
    print(f"  restricting Pinnacle to {first} .. {last}, where Betfair prices exist")
    report("pinnacle, betfair window", settle(scored, "pinnacle", window=(first, last)))
    report("max, betfair window", settle(scored, "max", window=(first, last)))

    print("\nREADING")
    print("  n* is the sample a 2% return would need to be resolved at 5%/80% given the")
    print("  variance this rule actually produces. Compare it to the bet counts above.")
    print("  If Pinnacle stays positive in the Betfair window while Betfair does not, the")
    print("  difference is the venue. If Pinnacle also goes flat there, it is the period,")
    print("  and two seasons of exchange prices say nothing about the exchange.")


if __name__ == "__main__":
    main()
