"""The corpus's loss-budget derivation, run on the platform's OWN measured inputs.

Matrix C2 / DR-003's constructive result: for flat staking, zero-drift expected maximum
drawdown has the closed form E[MDD] = 1.2533 * sigma * sqrt(N) per unit stake
(Magdon-Ismail et al., J. Applied Probability 41(1), 2004). The matrix's §6.4 explicitly
refuses its own quoted constants ("odds-mix-dependent constants are unpinned... the
harness must recompute all of them from the platform's actual declared odds population"),
so sigma and the cadence here are MEASURED from the fired ledger, never quoted.

Two derived outputs, zero chosen constants:
  1. The tightest drawdown tolerance EXPRESSIBLE at a given bank — the target below
     which the required flat stake falls under the GBP 1 exchange minimum. This is where
     the corpus's ~30%-at-GBP100 shape comes from (C2: "tightest feasible ~31%").
  2. The policy-implied loss budget: under the registered D7 policy the maximum peak
     loss is d_max * bank with probability ONE (B5 cap, demonstrated exact in the
     TE-0047 study), so budget = d_max * bank is derived, not picked.

Deterministic; prints the derivation. Flat-stake basis, as the closed form covers —
for the D7 allocator the same GBP1-lattice pressure appears as measured skips (G3).
"""
from __future__ import annotations

import math
import statistics
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.staking.selection import ProbabilitySource, SelectionRule  # noqa: E402
from tennis_edge.staking.sequence import load_sequence  # noqa: E402

SEQUENCE = Path("/home/user/tennis_edge_data/bet_sequence__exchange_prices_600s_v4.jsonl")
COMMISSION = Decimal("0.02")
MDD_CONSTANT = 1.2533          # 2*sqrt(pi/8), Magdon-Ismail zero-drift
MIN_STAKE = 1.0                # GBP, DR-005 verified


def main() -> None:
    header, pool = load_sequence(SEQUENCE)
    rule = SelectionRule(min_edge=Decimal("0.02"), source=ProbabilitySource.MODEL,
                         require_support=("SUPPORTED",))
    fired = rule.fired(pool, COMMISSION)
    returns = [float((c.odds - 1) * (Decimal(1) - COMMISSION)) if c.won else -1.0
               for c in fired]
    sigma = statistics.pstdev(returns)
    span_years = (max(c.date for c in fired) - min(c.date for c in fired)).days / 365.25
    cadence = len(fired) / span_years
    n_six_months = cadence / 2
    emdd_per_unit = MDD_CONSTANT * sigma * math.sqrt(n_six_months)

    print(f"ledger {header.get('price_table')}: {len(fired):,} fired bets over "
          f"{span_years:.1f} years -> cadence {cadence:.0f} bets/yr")
    print(f"measured per-unit sigma at c={COMMISSION}: {sigma:.4f} "
          f"(matrix's modelled 0.9364 NOT used, per its own §6.4 instruction)")
    print(f"zero-drift E[MDD], GBP1 flat stake, six months (N={n_six_months:.0f}): "
          f"GBP {emdd_per_unit:.1f}")
    print("\nTightest EXPRESSIBLE six-month drawdown tolerance by bank "
          "(below it the required stake is under the GBP1 minimum):")
    for bank in (100, 200, 500, 1000, 2000):
        frontier = emdd_per_unit * MIN_STAKE / bank
        print(f"  GBP{bank:>5}: {frontier:.1%} of bank"
              f"   -> policy-implied loss budget at cap d_max=~frontier: "
              f"GBP {bank * max(frontier, 0.0):.0f}")
    print("\nPolicy-implied budget under the CURRENT registered cap (d_max = 0.30):")
    for bank in (100, 200, 500, 1000, 2000):
        print(f"  GBP{bank:>5}: maximum possible peak loss = GBP {0.30 * bank:.0f} "
              f"(probability one, B5 cap; TE-0047 measured 0 breaches in 56,000 histories)")


if __name__ == "__main__":
    main()
