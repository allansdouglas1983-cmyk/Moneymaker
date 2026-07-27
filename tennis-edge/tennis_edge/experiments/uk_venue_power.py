"""Where can this actually be bet, and is there enough data there to know anything?

Every money conclusion in this project has to survive two filters, and only the first one
was being applied. The first is *is the forecast good?* The second is *is there a counter to
place the bet at?* — and the columns Tennis-Data publishes are mostly not counters. Pinnacle
has not taken a UK customer since November 2014. ``Max`` is the best of about twenty books on
each match, which is a statistic about the table, not an offer. Reporting either as a return
describes money nobody in this country could have collected.

Stripping those out leaves a short list, and the short list is the whole problem:

- **Betfair Exchange** — UK, and the only venue here that does not close an account for
  winning. It is therefore the one that decides whether any of this is real. Tennis-Data
  began carrying the column in 2025, so it covers about 4% of the corpus and two seasons.
- **Bet365** — UK, open, and the only column spanning the whole corpus (2002 onward). It
  will restrict a consistent winner, so a return here is real for as long as the account is
  allowed to live.
- **Ladbrokes** — UK, open, priced in this data 2008-2018. A second UK reading over a
  different decade. Also restricts winners.
- **Unibet** — UK and open, but the column stops in 2009. Reported for completeness and
  believed by nobody.

So this asks three questions the earlier report could not.

**How much data would it take?** Given the per-bet variance this rule actually produces, the
sample needed to resolve a plausible edge at conventional power. If the answer is far beyond
two seasons then the exchange question is not currently answerable and no amount of
modelling changes that.

**Is 2025-26 simply a bad period?** The decisive control, and it must be run at a UK venue
or it proves nothing about anything reachable. The same model, the same rule, the same
matches, settled at **Bet365** — first over its whole history, then restricted to exactly
the window where Betfair prices exist. If Bet365 also goes flat in that window, the Betfair
figure is a period effect rather than a venue effect.

**Does the exchange pay for itself?** Betfair and Bet365 both priced 2025-26. Settled on the
same matches, the difference between them is the exchange's structural advantage — no margin
in the quote, 2% commission on winnings — measured rather than assumed.

Pinnacle is still computed, in one clearly-labelled block at the end, for one reason: it is a
low-margin book that does not limit winners, so beating it is evidence the forecast is sharp.
That is a statement about the model. It is not money and it is not available.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from tennis_edge.experiments.residual_edge import walk_forward
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features
from tennis_edge.upcoming import break_even_probability
from tennis_edge.venues import Kind, benchmark_keys, by_key, uk_settlement_keys

#: Betfair Rewards flat rate, charged on net winnings. A bookmaker's margin is already inside
#: its quote, so its commission is zero and that is not a favour to the strategy.
EXCHANGE_COMMISSION = 0.02

#: The effect worth resolving. Not tuned to any result: it is the order of magnitude an
#: edge would have to be to be worth running this at all, and it is fixed before looking at
#: the venue-by-venue numbers so it cannot be walked down to fit them.
TARGET_ROI = 0.02

#: Conventional two-sided 5% test at 80% power.
Z_ALPHA = 1.959963984540054
Z_POWER = 0.8416212335729143


@dataclass(frozen=True)
class Bet:
    date: dt.date
    profit: float


def commission_for(book: str) -> float:
    """Only an exchange charges commission; a book's margin is already in the quote."""
    return EXCHANGE_COMMISSION if by_key(book).kind is Kind.EXCHANGE else 0.0


def settle(scored: list[tuple[Row, float]], book: str,
           window: tuple[dt.date, dt.date] | None = None) -> list[Bet]:
    """Flat one unit whenever the model clears the commission-aware break-even.

    Identical rule to the money report, so the numbers here are comparable to it. The
    optional window restricts to a date range without refitting anything — the model is the
    same, only the settlement venue and period change.
    """
    commission = Decimal(str(commission_for(book)))
    rate = float(commission)
    bets: list[Bet] = []
    for row, probability in scored:
        if window is not None and not (window[0] <= row.date <= window[1]):
            continue
        for side, model_p in ((("a"), probability), (("b"), 1.0 - probability)):
            odds = (row.odds_a if side == "a" else row.odds_b).get(book)
            if odds is None or odds <= 1.0:
                continue
            break_even = break_even_probability(Decimal(str(odds)), commission=commission)
            if model_p <= break_even:
                continue
            won = (row.won == 1) if side == "a" else (row.won == 0)
            # Commission is charged on net winnings, so a winner returns (O-1)(1-c).
            profit = (odds - 1.0) * (1.0 - rate) if won else -1.0
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
        print(f"  {name:<38} no bets")
        return
    roi = _mean(bets)
    lo, hi = clustered_bootstrap(bets, statistic=_mean, cluster_of=_day)
    need = required_sample(bets)
    span = (hi - lo) * 100
    print(f"  {name:<38} bets={len(bets):6,}  ROI={roi * 100:+6.2f}%  "
          f"CI95=[{lo * 100:+6.2f}%,{hi * 100:+6.2f}%]  width={span:5.2f}pp  "
          f"n*={need:,}")


def _coverage(rows: list[Row], book: str) -> tuple[int, dt.date, dt.date] | None:
    priced = [r for r in rows if book in r.odds_a and book in r.odds_b]
    if not priced:
        return None
    return len(priced), min(r.date for r in priced), max(r.date for r in priced)


def report_coverage(rows: list[Row]) -> None:
    """What each column actually covers. The reachability verdict sits in the same row.

    This table is the reason the module exists. A venue with a thirty-point interval is not
    telling you the edge is zero, and a venue you cannot open an account with is not telling
    you anything about money at all — both facts have to be visible next to the return, or
    the return gets quoted on its own.
    """
    print("PRICE COVERAGE BY VENUE")
    print(f"  {'venue':<20} {'reachable':<14} {'matches':>8}  {'from':<11} {'to':<11} share")
    for key in uk_settlement_keys() + benchmark_keys():
        venue = by_key(key)
        reach = "UK, open" if key in uk_settlement_keys() else venue.access.value
        cover = _coverage(rows, key)
        if cover is None:
            print(f"  {venue.name:<20} {reach:<14} {0:>8}  {'—':<11} {'—':<11}")
            continue
        count, first, last = cover
        print(f"  {venue.name:<20} {reach:<14} {count:>8,}  {first}  {last} "
              f"{100 * count / len(rows):5.1f}%")


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})

    print(f"corpus: {len(rows):,} priceable matches\n")
    report_coverage(rows)

    exchange = _coverage(rows, "betfair")
    if exchange is None:
        raise SystemExit("no Betfair prices in the corpus")
    _count, first, last = exchange

    print("\nwalk-forward:")
    scored = walk_forward(rows, names)

    print("\nBETTABLE FROM THE UK — same model, same rule, flat 1u")
    for key in uk_settlement_keys():
        venue = by_key(key)
        limits = "restricts winners" if venue.restricts_winners else "cannot limit winners"
        report(f"{venue.name} ({limits})", settle(scored, key))

    print("\nTHE CONTROL: the same window, a different UK venue")
    print(f"  restricting Bet365 to {first} .. {last}, where Betfair prices exist. Bet365")
    print("  is the only UK column covering both that window and the whole corpus, so it is")
    print("  the only one that can separate a period effect from a venue effect.")
    report("bet365, all available", settle(scored, "b365"))
    report("bet365, betfair window", settle(scored, "b365", window=(first, last)))
    report("betfair, all available", settle(scored, "betfair"))

    print("\nNOT BETTABLE FROM HERE — sharpness diagnostics, not returns")
    print("  Pinnacle left the UK in November 2014; the panel maximum and average are")
    print("  arithmetic over roughly twenty books rather than counters anyone stands at.")
    print("  Beating these says the forecast is sharp. It does not say anyone got paid.")
    for key in benchmark_keys():
        venue = by_key(key)
        report(f"{venue.name} [{venue.access.value}]", settle(scored, key))
        if key == "pinnacle":
            report("  pinnacle, betfair window", settle(scored, key, window=(first, last)))

    print("\nREADING")
    print("  n* is the sample a 2% return would need to be resolved at 5%/80% given the")
    print("  variance this rule actually produces. Compare it to the bet counts above.")
    print("  Betfair is the only venue whose result can survive being used repeatedly, and")
    print("  it is the one with the least data. If Bet365 stays positive in the Betfair")
    print("  window while Betfair does not, the difference is the venue. If Bet365 also")
    print("  goes flat there, it is the period, and two seasons of exchange prices say")
    print("  nothing about the exchange.")


if __name__ == "__main__":
    main()
