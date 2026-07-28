"""TE-0017 S4: the information-coverage gate, measured on identical rows.

The predicate is parameter-free, binary and decision-time-knowable: **both players carry a
pyramid record** — concretely, the row's feature dict contains ``pyramid_elo_gap``, which
the builder emits only when both players clear MIN_PYRAMID_MATCHES and both rest dates are
known. On rows failing it the pyramid block contributes nothing, so the model there is
mostly the anchor plus noise, and every fired bet is estimation noise around the market
minus commission.

Fixed before any money-by-cohort split existed anywhere in the record (verified through
TE-0022: none exists). The aggregate tail was opened by TE-0019, so today's gated numbers
are a **policy refinement of seen data, labelled as such** — excising a
negative-expectation cohort predictably pushes the same sample over zero and is not new
evidence. The frozen gated policy is a declared secondary for any future prospective data.

Declared in advance (TE-0017 §S4 binding amendments):
- The uncovered share is reported over FIRED bets, never the OOS-match share.
- The paired money difference is a directional diagnostic and will plausibly not clear
  zero; a null triggers neither over-claiming nor retreat.
- Consistency checks, not evidence: (a) uncovered model-vs-control ROI difference ≈ 0 is
  near-tautological; (b) the 22-feature forecast split on the uncovered cohort is
  reported either way (the published +0.000000 was the 10-feature fit).
- **If the uncovered cohort earns — money edge living where the forecast edge is not —
  that is a suspected bug per house rules: stop and investigate.**
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

from tennis_edge.exchange_prices import read_prices
from tennis_edge.experiments.exchange_settlement import _sigmoid, report, settle
from tennis_edge.experiments.residual_edge import walk_forward
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.fill_evidence import FillSupport
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features

PRICES = Path("/home/user/tennis_edge_data/betfair_historical/"
              "exchange_prices_600s_v3.jsonl")

#: The frozen predicate. Feature presence, not a threshold: the builder already refuses
#: to emit the pyramid block on insufficient coverage, and this simply asks whether it did.
PREDICATE_FEATURE = "pyramid_elo_gap"


def covered_by_pyramid(row: Row) -> bool:
    return PREDICATE_FEATURE in row.features


def _forecast_split(scored: list[tuple[Row, float]], label: str) -> None:
    """Paired log-score gain of the 22-feature model over the market, day-clustered."""
    diffs: list[tuple[dt.date, float]] = []
    for row, model_p in scored:
        market_p = _sigmoid(row.market_logit)
        p_model = min(max(model_p, 1e-12), 1 - 1e-12)
        p_market = min(max(market_p, 1e-12), 1 - 1e-12)
        if row.won:
            diffs.append((row.date, -math.log(p_market) + math.log(p_model)))
        else:
            diffs.append((row.date, -math.log(1 - p_market) + math.log(1 - p_model)))
    gain = sum(d for _, d in diffs) / len(diffs)
    lo, hi = clustered_bootstrap(
        diffs, statistic=lambda items: sum(d for _, d in items) / len(items),  # type: ignore[arg-type,misc]
        cluster_of=lambda item: item[0])  # type: ignore[union-attr,index]
    print(f"  {label:<40} n={len(diffs):6,}  {gain:+.6f} nats  "
          f"CI95=[{lo:+.6f},{hi:+.6f}]")


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    prices = {(p.date, p.tour, p.player_a, p.player_b): p for p in read_prices(PRICES)}
    print(f"prices: {len(prices):,} from {PRICES.name}")

    scored = walk_forward(rows, names)
    covered = [(r, p) for r, p in scored
               if (r.date, r.tour, r.player_a, r.player_b) in prices]
    gated_rows = [(r, p) for r, p in covered if covered_by_pyramid(r)]
    uncovered_rows = [(r, p) for r, p in covered if not covered_by_pyramid(r)]
    print(f"\nrows with a price: {len(covered):,}  predicate true: {len(gated_rows):,}  "
          f"false: {len(uncovered_rows):,}")

    ungated_model = settle(covered, prices, use_model=True)
    gated_model = settle(gated_rows, prices, use_model=True)
    uncovered_model = settle(uncovered_rows, prices, use_model=True)
    uncovered_control = settle(uncovered_rows, prices, use_model=False)

    share = len(uncovered_model) / len(ungated_model)
    print(f"\nUNCOVERED SHARE OF FIRED BETS (the binding denominator): "
          f"{len(uncovered_model):,} of {len(ungated_model):,} ({100 * share:.1f}%)")

    print("\nUNGATED — the policy as measured everywhere else")
    report("model, all fills", ungated_model)
    report("model, supported only",
           [b for b in ungated_model if b.support is FillSupport.SUPPORTED])

    print("\nGATED — predicate true only (policy refinement of seen data, NOT new "
          "evidence)")
    report("model, all fills", gated_model)
    report("model, supported only",
           [b for b in gated_model if b.support is FillSupport.SUPPORTED])

    print("\nUNCOVERED COHORT — where the gate says the model knows nothing")
    report("model, all fills", uncovered_model)
    report("model, supported only",
           [b for b in uncovered_model if b.support is FillSupport.SUPPORTED])
    report("control, all fills (consistency (a))", uncovered_control)

    print("\nFORECAST SPLIT ON THE 22-FEATURE MODEL (consistency (b); the published "
          "zero was the 10-feature fit)")
    _forecast_split(gated_rows, "features over market, covered rows")
    _forecast_split(uncovered_rows, "features over market, uncovered rows")

    supported_uncovered = [b for b in uncovered_model
                           if b.support is FillSupport.SUPPORTED]
    if supported_uncovered:
        mean = sum(b.profit for b in supported_uncovered) / len(supported_uncovered)
        lo, _hi = clustered_bootstrap(
            supported_uncovered,
            statistic=lambda bets: sum(b.profit for b in bets) / len(bets),  # type: ignore[arg-type,misc,union-attr]
            cluster_of=lambda b: b.date)  # type: ignore[union-attr]
        if lo > 0:
            print(f"\nSUSPECTED BUG (house rules): the uncovered cohort EARNS "
                  f"({mean * 100:+.2f}%, lower bound {lo * 100:+.2f}%) — money edge "
                  f"where the forecast edge is not. STOP AND INVESTIGATE before any "
                  f"use of this gate.")

    print("\nREADING")
    print("  The gate's justification is the structural zero-information identity, not")
    print("  the paired money difference, which was declared likely not to clear zero.")
    print("  All rows hypothetical trade-through returns; TE-0020's cost band applies.")


if __name__ == "__main__":
    main()
