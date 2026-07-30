"""Sweep the FIRING rule at a flat unit stake, so selection is measured without sizing.

THE QUESTION. Expected profit is ``sum(S_i * ev_i)``. A staking rule chooses the weights
``S_i`` and cannot change any ``ev_i``; selection chooses which ``ev_i`` enter the sum at
all. So before any staking rule is chosen there is a prior question worth more: does
moving the firing rule move the per-bet expectation, and by how much?

This answers it with the sizing lever deliberately switched off — flat one-unit stakes on
a bank large enough that the floor, the minimum and ruin can never bind. Whatever
difference appears between configurations is selection, uncontaminated by compounding.

The knobs swept: commission (2% Basic, 5% tennis base rate), probability source (model, or
the market's own de-vigged price as the control), fill-evidence requirement, minimum edge,
and odds band.

INTERVALS ARE DAY-CLUSTERED. Several matches settle on the same day and share a market
state; resampling individual bets would treat them as independent evidence and is the
easiest way to manufacture a confident wrong answer.

READ THIS AS A DIAGNOSTIC, NOT A CHOICE. Every configuration below is being evaluated on
the same realised path, so the best-looking cell is selected on noise as much as on
signal. Choosing a firing rule from this table without a multiplicity correction is
exactly the backtest-overfitting failure the study is supposed to avoid. It reports what
the levers do; it does not pick one.

Run from tennis-edge/:  python tools/sweep_selection.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.metrics import clustered_bootstrap  # noqa: E402
from tennis_edge.staking.engine import (  # noqa: E402
    Candidate,
    EngineConfig,
    LedgerRow,
    replay,
)
from tennis_edge.staking.selection import ProbabilitySource, SelectionRule  # noqa: E402
from tennis_edge.staking.sequence import load_sequence  # noqa: E402

DEFAULT_SEQUENCE = Path("/home/user/tennis_edge_data/"
                        "bet_sequence__exchange_prices_600s_v4.jsonl")

#: One unit = GBP 1.00 = 100p, the exchange minimum, on a bank of GBP 10,000,000. Large
#: enough that neither the floor, the minimum stake nor ruin can ever bind, which is the
#: point: this isolates selection from every sizing effect.
UNIT_PENCE = 100
HUGE_BANK_PENCE = 1_000_000_000

MIN_EDGES = ("0.00", "0.01", "0.02", "0.03", "0.04", "0.05", "0.075", "0.10")
ODDS_BANDS: tuple[tuple[str, str | None, str | None], ...] = (
    ("all", None, None),
    ("1.01-1.50", "1.01", "1.50"),
    ("1.50-2.00", "1.50", "2.00"),
    ("2.00-3.00", "2.00", "3.00"),
    ("3.00-6.00", "3.00", "6.00"),
    ("6.00+", "6.00", None),
)


def _flat(candidates: object, state: object) -> list[int]:  # noqa: ARG001
    return [UNIT_PENCE for _ in candidates]  # type: ignore[attr-defined]


def _roi(rows: object) -> float:
    staked = sum(r.stake_pence for r in rows if isinstance(r, LedgerRow))
    if not staked:
        return 0.0
    profit = sum(r.profit_pence for r in rows if isinstance(r, LedgerRow))
    return profit / staked


def _day(row: object) -> dt.date:
    assert isinstance(row, LedgerRow)
    return row.date


def measure(candidates: list[Candidate], rule: SelectionRule, commission: Decimal,
            draws: int) -> tuple[int, int, float, float, float]:
    fired = rule.fired(candidates, commission)
    if len(fired) < 100:
        return len(fired), 0, 0.0, 0.0, 0.0
    config = EngineConfig(start_bank_pence=HUGE_BANK_PENCE, floor_pence=0,
                          min_stake_pence=UNIT_PENCE, commission=commission)
    path = replay(fired, _flat, config)  # type: ignore[arg-type]
    placed = [r for r in path.rows if r.stake_pence > 0]
    roi = _roi(placed)
    lo, hi = clustered_bootstrap(placed, statistic=_roi, cluster_of=_day, draws=draws)
    days = len({r.date for r in placed})
    return len(placed), days, roi, lo, hi


def line(label: str, bets: int, days: int, roi: float, lo: float, hi: float) -> str:
    if bets < 100:
        return f"  {label:<26} {bets:>6,} bets — too few to score"
    verdict = "CLEARS ZERO" if lo > 0 else ("below zero" if hi < 0 else "spans zero")
    return (f"  {label:<26} {bets:>6,} bets  {days:>5,} days  "
            f"ROI {roi * 100:+6.2f}%  CI95 [{lo * 100:+6.2f}%,{hi * 100:+6.2f}%]  {verdict}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", type=Path, default=DEFAULT_SEQUENCE)
    parser.add_argument("--draws", type=int, default=2000)
    args = parser.parse_args()

    header, candidates = load_sequence(args.sequence)
    print(f"opportunity set: {len(candidates):,} side-prices "
          f"from {header.get('price_table')}")
    print(f"                 {len({c.date for c in candidates}):,} distinct days, "
          f"{min(c.date for c in candidates)} .. {max(c.date for c in candidates)}")
    print(f"                 flat {UNIT_PENCE}p unit, bank large enough that no floor, "
          f"minimum or ruin can bind\n")

    for commission in (Decimal("0.05"), Decimal("0.02")):
        for source in (ProbabilitySource.MODEL, ProbabilitySource.MARKET):
            for support in (None, ("SUPPORTED",)):
                tag = ("all fills" if support is None else "supported fills only")
                print(f"COMMISSION {commission * 100:.0f}%  |  SOURCE {source.value}  "
                      f"|  {tag}")

                print("  -- minimum edge, all prices --")
                for edge in MIN_EDGES:
                    rule = SelectionRule(min_edge=Decimal(edge), source=source,
                                         require_support=support)
                    print(line(f"min_edge {edge}",
                               *measure(candidates, rule, commission, args.draws)))

                print("  -- odds band, min_edge 0.02 --")
                for name, lo_odds, hi_odds in ODDS_BANDS:
                    rule = SelectionRule(
                        min_edge=Decimal("0.02"), source=source,
                        require_support=support,
                        min_odds=None if lo_odds is None else Decimal(lo_odds),
                        max_odds=None if hi_odds is None else Decimal(hi_odds))
                    print(line(f"odds {name}",
                               *measure(candidates, rule, commission, args.draws)))
                print()

    print("READING")
    print("  Every cell above is evaluated on the SAME realised path, so the best-looking")
    print("  one is selected on noise as much as on signal. This table reports what the")
    print("  levers do. It does not choose one, and a firing rule picked from it without a")
    print("  multiplicity correction is the backtest-overfitting failure in person.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
