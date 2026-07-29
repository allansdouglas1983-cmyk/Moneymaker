"""TE-0034: the frozen money rule on the founder-supplied May-July 2026 archive.

The money question froze at 2026-05-12 because the exchange archive did. The founder has
now supplied the missing months (may_jul.tar, sha256:4fda22c9..., BASIC May/Jun/Jul 2026,
49,903 members). This is the one evaluation that file makes possible: the EXACT frozen
pipeline — same link bridge, same horizon, same bet rule, same settlement, same fill
falsification — run once over roughly ten weeks of exchange prices that did not exist on
this machine when every rule was frozen. Nothing is fitted, tuned or chosen on this window.

DECLARATIONS, fixed before the new priced table is examined
-----------------------------------------------------------
- Priced table: built by the v3/v4 pipeline verbatim (read_extract -> doubles filter ->
  market_id dedup -> build_prices at 600s against the current corpus vintage). Only rows
  dated AFTER 2026-05-12 enter, and any market_id already present in the frozen v4 table
  is excluded — this window may not double-count a single frozen row.
- Model: the exact TE-0019 configuration — ridge logistic residual on the Bet365 de-vig
  offset, L2 untouched, names from rows — fitted ONCE on all cached feature rows dated
  on or before 2026-05-12. The window never trains anything.
- Bet rule and settlement: exchange_settlement.settle VERBATIM — flat one unit on either
  side whenever the probability clears the commission-aware break-even at the T-600
  exchange price, no edge buffer, 2% commission on wins, three-way fill split
  (SUPPORTED / UNSUPPORTED / NO_EVIDENCE by trade-through), day-clustered bootstrap.
- PRIMARY (single confirmatory question, 95%): the SUPPORTED-fills model ROI on this
  window. Secondary context, reported never headlined: all-fills ROI, the control
  (market's own probability) under both readings, forecast log-score gain vs the
  exchange baseline, and per-support bet counts.
- Every number is a hypothetical trade-through return; TE-0020's execution-cost band
  applies unchanged; nothing here is a realised return and none is reported as one.
- One run, recorded whatever it says (TE-0034). The window is then spent.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

from tennis_edge.exchange_prices import read_prices
from tennis_edge.experiments.exchange_settlement import (
    Bet,
    report,
    settle,
)
from tennis_edge.experiments.residual_edge import fit, predict
from tennis_edge.fill_evidence import FillSupport
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features

BASE = Path("/home/user/tennis_edge_data/betfair_historical")
NEW_PRICES = BASE / "exchange_prices_600s_mayjul.jsonl"
FROZEN_PRICES = BASE / "exchange_prices_600s_v4.jsonl"
BOUNDARY = dt.date(2026, 5, 12)


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(z, 35.0), -35.0)))


def main() -> None:
    frozen_ids = {p.market_id for p in read_prices(FROZEN_PRICES)}
    prices = {}
    overlap = 0
    for p in read_prices(NEW_PRICES):
        if p.market_id in frozen_ids:
            overlap += 1
            continue
        if p.date <= BOUNDARY:
            overlap += 1
            continue
        prices[(p.date, p.tour, p.player_a, p.player_b)] = p
    days = {d for d, _t, _a, _b in prices}
    print(f"window prices: {len(prices):,} matches on {len(days):,} days "
          f"({min(days)} .. {max(days)}); excluded as frozen/overlap: {overlap:,}")

    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    train = [r for r in rows if r.date <= BOUNDARY]
    test = [r for r in rows if (r.date, r.tour, r.player_a, r.player_b) in prices]
    print(f"trained on {len(train):,} rows (<= {BOUNDARY}); "
          f"window rows with an exchange price: {len(test):,}")

    beta = fit(train, names)
    scored = [(r, predict(r, beta)) for r in test]

    # Forecast context: paired log-score gain vs the exchange de-vig baseline.
    gains = []
    for row, p_model in scored:
        price = prices[(row.date, row.tour, row.player_a, row.player_b)]
        inv_a, inv_b = 1.0 / float(price.odds_a), 1.0 / float(price.odds_b)
        p_exch = inv_a / (inv_a + inv_b)
        g = (math.log(p_model if row.won else 1 - p_model)
             - math.log(p_exch if row.won else 1 - p_exch))
        gains.append((row.date, g))
    if gains:
        mean_g = sum(g for _, g in gains) / len(gains)
        lo, hi = clustered_bootstrap(
            gains, statistic=lambda xs: sum(g for _, g in xs) / len(xs),
            cluster_of=lambda x: x[0])
        print(f"\nforecast vs exchange baseline   n={len(gains):,}  {mean_g:+.6f} nats  "
              f"CI95=[{lo:+.6f},{hi:+.6f}]")

    model = settle(scored, prices, use_model=True)
    control = settle(scored, prices, use_model=False)

    print("\nALL FILLS CREDITED — what a conventional backtest reports")
    report("model", model)
    report("control (market's own probability)", control)

    print("\nPRIMARY — SUPPORTED FILLS ONLY (the market later traded there or better)")
    report("model", [b for b in model if b.support is FillSupport.SUPPORTED])
    report("control", [b for b in control if b.support is FillSupport.SUPPORTED])

    print("\nthe fills a conventional backtest would have invented:")
    for support in (FillSupport.UNSUPPORTED, FillSupport.NO_EVIDENCE):
        subset = [b for b in model if b.support is support]
        print(f"  model {support.value:<14} {len(subset):,} bets")

    print("\nEvery number above is a hypothetical trade-through return; TE-0020's")
    print("execution-cost band applies unchanged. One run; the window is now spent.")


if __name__ == "__main__":
    main()
