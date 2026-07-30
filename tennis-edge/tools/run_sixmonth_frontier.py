"""TE-0047 pre-declared SECONDARY analysis: the six-month frontier, with D7 included.

Reproduces the TE-0046 Addendum 2 frontier configuration exactly — GBP 200 bank,
~126 betting days (~445 bets) per history, 1,000 histories, 2% commission, arms
flat GBP2/5/10 + the withdrawn CONS_KELLY (measured object) + full Kelly (capped) —
now as a COMMITTED deterministic tool rather than an ad-hoc script, and with the
TE-0047 registered D7_LCB arm added. EXPLORATORY under the frozen registration:
labelled secondary, decides no gate, sized at the founder's declared horizon.

Scenario caveat, stated where the numbers are made: the §4.3 haircut zeroes the
EQUAL-WEIGHT per-unit mean. An edge-weighted allocator retains weighted drift under
that scenario, so a positive zero-scenario median for D7/Kelly arms is a property of
the scenario definition's declared scope — the admissibility claim is the floor/bust
behaviour, never zero-scenario profit.
"""
from __future__ import annotations

import datetime as dt
import random
import statistics
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.staking.engine import Candidate  # noqa: E402
from tennis_edge.staking.harness import (  # noqa: E402
    HarnessConfig,
    Ruin,
    haircut_factor,
    replay_run,
)
from tennis_edge.staking.rules import (  # noqa: E402
    conservative_kelly,
    d7_conservative_bound,
    flat,
    hb_cap,
)
from tennis_edge.staking.selection import ProbabilitySource, SelectionRule  # noqa: E402
from tennis_edge.staking.sequence import load_sequence  # noqa: E402

SEQUENCE = Path("/home/user/tennis_edge_data/bet_sequence__exchange_prices_600s_v4.jsonl")
OUT = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "staking" / "stk-harness-v1" / "six-month-frontier-v2.txt"

START_BANK = 20_000        # GBP 200
DAYS_PER_HISTORY = 126     # ~six months of betting days at the measured cadence
DRAWS = 1_000
SEED = 20260730
BLOCK = 10
COMMISSION = Decimal("0.02")
D7_DELTA_E = Decimal("0.0249")     # TE-0047 frozen
D7_MAX_DRAWDOWN = Decimal("0.30")  # TE-0047 frozen
CONS_KELLY_SHRINK = Decimal("1.37") / Decimal("3.86")  # withdrawn arm, measured object


def short_draws(days: list[dt.date], *, length: int, draws: int, seed: int,
                expected_block_length: int) -> list[list[dt.date]]:
    """Stationary-bootstrap day sequences of a FIXED length (the six-month horizon),
    same mechanics as harness.day_sequence_draws but not full-length."""
    rng = random.Random(seed)
    continue_probability = 1.0 - 1.0 / expected_block_length
    out: list[list[dt.date]] = []
    for _ in range(draws):
        sequence: list[dt.date] = []
        index = rng.randrange(len(days))
        while len(sequence) < length:
            sequence.append(days[index])
            if rng.random() < continue_probability:
                index = (index + 1) % len(days)
            else:
                index = rng.randrange(len(days))
        out.append(sequence)
    return out


def main() -> None:
    header, pool = load_sequence(SEQUENCE)
    rule = SelectionRule(min_edge=Decimal("0.02"), source=ProbabilitySource.MODEL,
                         require_support=("SUPPORTED",))
    fired = rule.fired(pool, COMMISSION)
    by_day: dict[dt.date, list[Candidate]] = {}
    for candidate in fired:
        by_day.setdefault(candidate.date, []).append(candidate)
    days = sorted(by_day)
    draws = short_draws(days, length=DAYS_PER_HISTORY, draws=DRAWS, seed=SEED,
                        expected_block_length=BLOCK)

    arms = {
        "FLAT_GBP2": flat(200),
        "FLAT_GBP5": flat(500),
        "FLAT_GBP10": flat(1_000),
        "CONS_KELLY_0355_WITHDRAWN": hb_cap(
            conservative_kelly(shrink=CONS_KELLY_SHRINK, commission=COMMISSION),
            Decimal("0.50")),
        "KELLY_FULL_CAP": hb_cap(
            conservative_kelly(shrink=Decimal(1), commission=COMMISSION),
            Decimal("0.50")),
        "D7_LCB": d7_conservative_bound(delta_e=D7_DELTA_E, commission=COMMISSION,
                                        max_drawdown=D7_MAX_DRAWDOWN),
    }
    config = HarnessConfig(start_bank_pence=START_BANK, founder_floor_pence=0,
                           min_stake_pence=100, commission=COMMISSION,
                           silent_death_days=30)

    # The equal-weight mean over the fired ledger, for the zero-scenario haircut.
    def unit_return(c: Candidate) -> Decimal:
        if not c.won:
            return Decimal(-1)
        return (c.odds - 1) * (Decimal(1) - COMMISSION)

    mu = sum((unit_return(c) for c in fired), Decimal(0)) / len(fired)
    scenarios = {"MEASURED": Decimal(0),
                 "ZERO": haircut_factor(fired, -mu, commission=COMMISSION)}

    lines = [f"SIX MONTHS v2 ({DAYS_PER_HISTORY} betting days), GBP{START_BANK // 100} "
             f"bank, {DRAWS} histories, ledger {header.get('price_table')} "
             f"({len(fired):,} fired bets) — TE-0047 secondary, EXPLORATORY"]
    for name, staking_rule in arms.items():
        row = {}
        for label, haircut in scenarios.items():
            finals, dips, busts = [], [], 0
            for sequence_days in draws:
                resampled: list[Candidate] = []
                for order, day in enumerate(sequence_days):
                    base = dt.date(2000, 1, 1) + dt.timedelta(days=order)
                    for c in by_day[day]:
                        resampled.append(Candidate(
                            date=base, market_id=c.market_id, side=c.side, odds=c.odds,
                            p_model=c.p_model, p_market=c.p_market, won=c.won,
                            support=c.support, stratum=c.stratum))
                path = replay_run(resampled, staking_rule, config, haircut=haircut)
                finals.append(path.final_bank_pence)
                low = min((r.closing_bank_pence for r in path.rows),
                          default=START_BANK)
                dips.append(START_BANK - min(low, START_BANK))
                busts += path.ruin is Ruin.DEAD_HARD
            finals.sort()
            dips.sort()
            n = len(finals)
            row[label] = {
                "med": statistics.median(finals), "q05": finals[int(0.05 * n)],
                "q95": finals[int(0.95 * n)], "dip95": dips[int(0.95 * n)],
                "bust": busts / n,
            }
        m, z = row["MEASURED"], row["ZERO"]
        lines.append(
            f"  {name:<26} MEASURED: med GBP{m['med'] / 100:>6.0f} "
            f"q05 GBP{m['q05'] / 100:>5.0f} q95 GBP{m['q95'] / 100:>6.0f} | "
            f"ZERO: med GBP{z['med'] / 100:>5.0f} q05 GBP{z['q05'] / 100:>5.0f} "
            f"dip95 GBP{z['dip95'] / 100:>4.0f} bust {z['bust']:.1%}")
        print(lines[-1], flush=True)

    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
