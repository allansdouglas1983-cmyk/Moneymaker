"""TE-0017 S5 reading (2): money by staleness band, under the ALREADY-frozen gate.

Sequencing is the whole point: the refusal rule (STALENESS_REFUSAL_BANDS, refuse >600s)
was frozen from the log-loss strata and committed BEFORE this module ever ran — commit
9ef3544 precedes the first money-by-band number in the record. The trend primary was null
at the bar, so the rule is an assumption; nothing here may promote it to a measurement,
and a flattering gated number below changes nothing about that label.

Standard settlement policy throughout (the same fired-bet rule as TE-0019/0022), v4
table, three-way fill split per band, day-clustered intervals, hypothetical trade-through
returns with TE-0020's cost band applying to every row.
"""
from __future__ import annotations

from pathlib import Path

from tennis_edge.exchange_prices import (
    STALENESS_BANDS,
    STALENESS_REFUSAL_BANDS,
    read_prices,
    row_band,
)
from tennis_edge.experiments.exchange_settlement import report, settle
from tennis_edge.experiments.residual_edge import walk_forward
from tennis_edge.fill_evidence import FillSupport
from tennis_edge.residual_features import build_residual_features

PRICES = Path("/home/user/tennis_edge_data/betfair_historical/"
              "exchange_prices_600s_v4.jsonl")


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    prices = {(p.date, p.tour, p.player_a, p.player_b): p for p in read_prices(PRICES)}
    print(f"prices: {len(prices):,} from {PRICES.name}")

    scored = walk_forward(rows, names)
    covered = [(r, p) for r, p in scored
               if (r.date, r.tour, r.player_a, r.player_b) in prices]

    def band_of(row: object) -> str | None:
        key = (row.date, row.tour, row.player_a, row.player_b)  # type: ignore[attr-defined]
        return row_band(prices[key])

    ungated = settle(covered, prices, use_model=True)
    kept = [(r, p) for r, p in covered if band_of(r) not in STALENESS_REFUSAL_BANDS]
    gated = settle(kept, prices, use_model=True)

    print("\nUNGATED (equals the TE-0022 interim look; v4 rows are v3 rows)")
    report("model, all fills", ungated)
    report("model, supported only",
           [b for b in ungated if b.support is FillSupport.SUPPORTED])

    print(f"\nGATED by the FROZEN rule (refuse {STALENESS_REFUSAL_BANDS}) — the rule is "
          f"an assumption, not a measurement, and this number cannot promote it")
    report("model, all fills", gated)
    report("model, supported only",
           [b for b in gated if b.support is FillSupport.SUPPORTED])

    print("\nPER-BAND MONEY AND FILL SPLIT (descriptive)")
    for band in STALENESS_BANDS:
        members = [(r, p) for r, p in covered if band_of(r) == band]
        bets = settle(members, prices, use_model=True)
        report(f"band {band}, all fills", bets)
        for support in FillSupport:
            cohort = [b for b in bets if b.support is support]
            share = 100 * len(cohort) / len(bets) if bets else 0.0
            print(f"      {support.value:<14} {len(cohort):6,} ({share:4.1f}%)")
        report(f"band {band}, supported only",
               [b for b in bets if b.support is FillSupport.SUPPORTED])

    print("\nREADING")
    print("  Hypothetical trade-through returns; TE-0020's execution-cost band applies")
    print("  to every row. The gate stays labelled an assumption whatever these show.")


if __name__ == "__main__":
    main()
