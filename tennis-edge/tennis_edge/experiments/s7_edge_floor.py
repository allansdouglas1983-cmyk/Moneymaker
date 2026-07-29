"""TE-0017 S7: the Roll-band edge floor and the edge-monotonicity diagnostic.

The current rule bets any positive edge over break-even, including edges smaller than the
price's own measurement noise. The gate tested here is not a fitted constant — it is the
market's own measured cost, per market — so nothing is tuned against returns.

**Pins, frozen before any gated computation (TE-0017 §S7):**

- The gate compares POINT edge vs the Roll-implied HALF-spread, converted to probability
  points by the S6 frozen conversion (`edge_band`), recorded as such.
- The market's spread is the worse side's estimate over the full pre-off series — the
  same window and convention the spreads table was built with, unchanged.
- Positive-autocovariance (Roll-refused) markets are a TYPED EXCLUSION with their own
  reported cohort: the gate is structurally blind exactly in the trending/steam class it
  targets, and that blindness is disclosed, never patched.
- Roll-coverage composition is cross-tabbed against the TE-0014 liquidity strata so a
  gate "effect" is distinguishable from the known stratum result.
- **The archive reading is EXPLORATORY and stated in advance to be expected to span
  zero** (gating shrinks n below n*); the confirmatory test is future data under this
  frozen spec. No narrative either way.
- Monotonicity under equivalence framing: fired bets deciled by predicted edge; the
  per-bet OLS slope of net return on predicted edge, day-clustered CI. A calibrated edge
  has slope 1; the pre-declared minimum useful slope is 0.5. The negative capability
  claim ("edge magnitude carries no selection value") is licensed ONLY if the slope's
  upper confidence bound excludes 0.5 — a flat point estimate alone licenses nothing,
  and the interval width is the published power arithmetic.
- Any live minimum-edge buffer remains a founder decision (§2.12); this produces
  evidence only.
"""
from __future__ import annotations

import collections
import math
from decimal import Decimal
from pathlib import Path
from typing import cast

from tennis_edge.display_band import edge_band
from tennis_edge.exchange_prices import read_prices
from tennis_edge.experiments.exchange_settlement import Bet, report, settle
from tennis_edge.experiments.residual_edge import walk_forward
from tennis_edge.experiments.roll_band import read_spreads
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features

PRICES = Path("/home/user/tennis_edge_data/betfair_historical/"
              "exchange_prices_600s_v4.jsonl")

#: A calibrated predicted edge pays itself: slope 1. Half of that is the pre-declared
#: minimum at which edge magnitude would still be worth selecting on.
MINIMUM_USEFUL_SLOPE = 0.5


def _slope(items: object) -> float:
    bets = [cast(Bet, b) for b in items]  # type: ignore[union-attr]
    n = len(bets)
    if n < 2:
        return 0.0
    mean_x = math.fsum(b.edge for b in bets) / n
    mean_y = math.fsum(b.profit for b in bets) / n
    var = math.fsum((b.edge - mean_x) ** 2 for b in bets)
    if var == 0.0:
        return 0.0
    return math.fsum((b.edge - mean_x) * (b.profit - mean_y) for b in bets) / var


def main() -> None:
    spreads = read_spreads()
    prices = {(p.date, p.tour, p.player_a, p.player_b): p for p in read_prices(PRICES)}
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    scored = walk_forward(rows, names)
    covered = [(r, p) for r, p in scored
               if (r.date, r.tour, r.player_a, r.player_b) in prices]
    fired = settle(covered, prices, use_model=True)

    def market_roll(market_id: str) -> float | None:
        entry = spreads.get(market_id)
        if entry is None:
            return None
        measured = [float(v) for v in entry["spreads"].values() if v is not None]
        return max(measured) if measured else None

    gated: list[Bet] = []
    refused: list[Bet] = []
    below_floor: list[Bet] = []
    for bet in fired:
        roll = market_roll(bet.market_id)
        if roll is None:
            refused.append(bet)
            continue
        floor = edge_band(Decimal(str(bet.odds)), roll)
        (gated if bet.edge > floor else below_floor).append(bet)

    print("UNGATED — the standing policy")
    report("all fired bets", fired)
    print("\nGATED — point edge above the market's own Roll half-spread floor "
          "(EXPLORATORY; expected in advance to span zero)")
    report("edge above floor", gated)
    report("edge below floor (the excised cohort)", below_floor)
    print("\nTYPED EXCLUSION — Roll-refused (positive autocovariance) markets, where the")
    print("gate is structurally blind in exactly the trending class it targets:")
    report("refused-market bets", refused)

    print("\nROLL COVERAGE x TE-0014 LIQUIDITY STRATA (a gate effect must be")
    print("distinguishable from the known stratum result)")
    cross: collections.Counter = collections.Counter()
    for bet in fired:
        cohort = ("refused" if market_roll(bet.market_id) is None else "measured")
        cross[(cohort, bet.stratum.value)] += 1
    strata = sorted({s for _c, s in cross})
    print(f"  {'':<10}" + "".join(f"{s:>12}" for s in strata))
    for cohort in ("measured", "refused"):
        print(f"  {cohort:<10}" + "".join(f"{cross.get((cohort, s), 0):>12,}"
                                          for s in strata))

    print("\nEDGE MONOTONICITY (equivalence framing; minimum useful slope "
          f"{MINIMUM_USEFUL_SLOPE})")
    deciles: dict[int, list[Bet]] = collections.defaultdict(list)
    ordered = sorted(fired, key=lambda b: b.edge)
    for index, bet in enumerate(ordered):
        deciles[min(9, 10 * index // len(ordered))].append(bet)
    for decile in range(10):
        bets = deciles[decile]
        mean_edge = math.fsum(b.edge for b in bets) / len(bets)
        mean_roi = math.fsum(b.profit for b in bets) / len(bets)
        print(f"  decile {decile}: n={len(bets):5,}  mean edge {mean_edge:+.4f}  "
              f"ROI {mean_roi * 100:+6.2f}%")
    slope = _slope(fired)
    lo, hi = clustered_bootstrap(
        fired, statistic=_slope,  # type: ignore[arg-type]
        cluster_of=lambda b: cast(Bet, b).date)  # type: ignore[union-attr]
    print(f"\n  per-bet slope of net return on predicted edge: {slope:+.3f}  "
          f"CI95=[{lo:+.3f},{hi:+.3f}]")
    if hi < MINIMUM_USEFUL_SLOPE:
        print(f"  upper bound excludes {MINIMUM_USEFUL_SLOPE}: the negative capability "
              f"claim is licensed — edge magnitude carries no selection value at the "
              f"declared minimum.")
    else:
        print(f"  upper bound does NOT exclude {MINIMUM_USEFUL_SLOPE}: no equivalence "
              f"claim; the interval above is the power arithmetic, published as such.")

    print("\nREADING")
    print("  Hypothetical trade-through returns throughout; TE-0020's band applies. The")
    print("  gate is frozen evidence for a future founder decision, never a live change.")


if __name__ == "__main__":
    main()
