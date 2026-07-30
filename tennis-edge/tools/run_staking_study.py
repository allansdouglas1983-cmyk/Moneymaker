"""STK-HARNESS-V1: the head-to-head. Config frozen IN THIS FILE, committed before any run.

Protocol: docs/research/findings/DR-TENNIS-STAKING-006-PROTOCOL.md. This runner freezes
every choice the protocol left as an input, prints the config hash first, and computes
nothing until the freeze is committed. Deviations from the protocol text, declared here
rather than discovered later:

- COMMISSION PRIMARY = 0.02. The protocol draft named 0.05 "the account's current
  state"; the account moved to the Basic package (TE-0044) before this config froze, so
  the primary column is the account's actual rate. 0.05 is the secondary column.
- DRAWS = 1,000 (protocol §3.3 said 10,000). Pure-Python exact-Decimal replay costs make
  10k draws ~a day of compute; 1,000 gives percentile CIs with Monte-Carlo error well
  inside the effect sizes at stake, and the seed is frozen so the run is extendable
  WITHOUT re-picking anything. Recorded as a deviation, not hidden.
- LEDGER: the fired set of the CURRENT policy (model source, min_edge 0.02) over the
  v4 opportunity export, SUPPORTED fills only — the honest reading every published
  money number uses. The ledger hash is printed and recorded.
- ARMS: the eight edge-free catalogue rules in eleven parameterisations plus one
  designed control. N = 12 is the trial count for every Bonferroni correction. Group D
  (edge-consuming) is absent by construction, per the matrix ranking.

Founder floor: GBP 70 on the GBP 100 bank (LOSS_BUDGET GBP 30, the protocol's default
proposal — an input, not a finding).

Run from tennis-edge/:  python tools/run_staking_study.py [--out DIR]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import statistics
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.staking.engine import Candidate  # noqa: E402
from tennis_edge.staking.harness import (  # noqa: E402
    HarnessConfig,
    Ruin,
    RunPath,
    day_sequence_draws,
    haircut_factor,
    replay_run,
)
from tennis_edge.staking.rules import (  # noqa: E402
    StakingRule,
    cppi,
    fixed_profit_net,
    flat,
    hb_cap,
    proportional,
    sqrt_profit,
    tipp,
    variance_ladder,
)
from tennis_edge.staking.selection import ProbabilitySource, SelectionRule  # noqa: E402
from tennis_edge.staking.sequence import load_sequence  # noqa: E402

SEQUENCE = Path("/home/user/tennis_edge_data/bet_sequence__exchange_prices_600s_v4.jsonl")

CONFIG = {
    "kind": "stk-harness-v1-config",
    "start_bank_pence": 10_000,
    "founder_floor_pence": 7_000,
    "min_stake_pence": 100,
    "silent_death_days": 30,
    "commission_primary": "0.02",
    "commission_secondary": "0.05",
    "selection": {"source": "MODEL", "min_edge": "0.02", "require_support": ["SUPPORTED"]},
    "scenarios": ["as_measured", "half", "zero", "negative"],
    "draws": 1_000,
    "seed": 20260730,
    "expected_block_length": 10,
    "N_trials": 12,
    "alpha": 0.05,
    "gates": {
        "G1_dead_floor_at_zero": 0.05,
        "G2_dead_floor_at_negative": 0.10,
        "G3_silent_death": 0.10,
        "G3_participation": 0.70,
        "G4_clamp_rate": 0.05,
    },
    "incumbent": "FLAT_100",
    "deviations": [
        "commission primary 0.02 not 0.05: account moved to Basic (TE-0044) pre-freeze",
        "draws 1000 not 10000: exact-Decimal compute cost; seed frozen, extendable",
    ],
}

#: The arms. Parameters are the matrix's canonical descriptions on a GBP 100 bank.
#: N = len(ARMS) is the Bonferroni trial count. FLAT_100 is the incumbent.
ARMS: dict[str, StakingRule] = {
    "FLAT_100": flat(100),                                       # A1, incumbent, GBP 1
    "FLAT_200": flat(200),                                       # A1 at GBP 2
    "PROP_2PC": proportional(Decimal("0.02")),                   # B1
    "PROP_5PC": proportional(Decimal("0.05")),                   # B1 aggressive
    "FPNET_100": fixed_profit_net(100),                          # A2, win GBP 1 net
    "VELADDER_100": variance_ladder(100),                        # A6
    "SQRT_100": sqrt_profit(100, 10_000),                        # A7
    "CPPI_M05": cppi(Decimal("0.05"), 7_000),                    # B2, m=0.05 of cushion
    "CPPI_M1": cppi(Decimal("1"), 7_000),                        # B2, m=1 (gap-safe bound)
    "TIPP_08": tipp(Decimal("0.05"), 7_000, Decimal("0.8")),     # B4, ratchet 80% of HWM
    "HBCAP_PROP5": hb_cap(proportional(Decimal("0.05")), Decimal("0.30")),  # B5 over B1
    "CONTROL_ALLIN": proportional(Decimal("1")),                 # designed pathology control
}

SCENARIO_FACTORS = {"as_measured": Decimal(0), "half": Decimal("0.5"),
                    "zero": Decimal(1), "negative": Decimal(2)}


def ledger_hash(candidates: list[Candidate]) -> str:
    payload = json.dumps([[c.date.isoformat(), c.market_id, c.side, str(c.odds), c.won]
                          for c in candidates], sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def measured_mean(candidates: list[Candidate], commission: Decimal) -> Decimal:
    total = Decimal(0)
    for c in candidates:
        b = (c.odds - 1) * (Decimal(1) - commission)
        total += b if c.won else Decimal(-1)
    return total / len(candidates)


def path_metrics(path: RunPath, config: HarnessConfig) -> dict[str, object]:
    series: list[int] = []
    bank_by_day: dict[dt.date, int] = {}
    for row in path.rows:
        bank_by_day[row.date] = row.closing_bank_pence
    running = config.start_bank_pence
    for day in sorted(bank_by_day):
        running = bank_by_day[day]
        series.append(running)
    peak = config.start_bank_pence
    max_dd = 0.0
    drawdowns: list[float] = []
    for value in series:
        peak = max(peak, value)
        dd = (peak - value) / peak
        drawdowns.append(dd)
        max_dd = max(max_dd, dd)
    placed = sum(1 for r in path.rows if r.stake_pence > 0)
    eligible = len(path.rows)
    stakes = [r.stake_pence for r in path.rows if r.stake_pence > 0]
    n_eff = (sum(stakes) ** 2 / sum(s * s for s in stakes)) if stakes else 0.0
    min_bank = min(series) if series else config.start_bank_pence
    worst = sorted(drawdowns, reverse=True)
    top5 = worst[:max(1, len(worst) // 20)]
    return {
        "final": path.final_bank_pence,
        "min_bank": min_bank,
        "max_drawdown": max_dd,
        "cdar_95": sum(top5) / len(top5) if top5 else 0.0,
        "ulcer": math.sqrt(sum(d * d for d in drawdowns) / len(drawdowns)) * 100
                 if drawdowns else 0.0,
        "dead_floor": path.ruin is Ruin.DEAD_FLOOR,
        "dead_hard": path.ruin is Ruin.DEAD_HARD,
        "silent_death": path.silent_death_onset is not None,
        "participation": placed / eligible if eligible else 0.0,
        "clamp_rate": sum(1 for r in path.rows if r.reason == "CLAMP_RESERVE")
                      / placed if placed else 0.0,
        "n_eff": n_eff,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=Path("docs/evidence/staking/stk-harness-v1"))
    args = parser.parse_args()

    config_digest = hashlib.sha256(
        json.dumps(CONFIG, sort_keys=True).encode()).hexdigest()
    print(f"config sha256: {config_digest}", flush=True)

    header, pool = load_sequence(SEQUENCE)
    commission = Decimal(CONFIG["commission_primary"])  # type: ignore[arg-type]
    rule = SelectionRule(min_edge=Decimal("0.02"), source=ProbabilitySource.MODEL,
                         require_support=("SUPPORTED",))
    fired = rule.fired(pool, commission)
    print(f"ledger: {len(fired):,} bets from {header.get('price_table')} "
          f"sha256 {ledger_hash(fired)[:16]}…", flush=True)

    mu = measured_mean(fired, commission)
    print(f"measured per-unit mean at c={commission}: {mu:+.6f}", flush=True)

    config = HarnessConfig(
        start_bank_pence=CONFIG["start_bank_pence"],  # type: ignore[arg-type]
        founder_floor_pence=CONFIG["founder_floor_pence"],  # type: ignore[arg-type]
        min_stake_pence=CONFIG["min_stake_pence"],  # type: ignore[arg-type]
        commission=commission,
        silent_death_days=CONFIG["silent_death_days"],  # type: ignore[arg-type]
    )

    by_day: dict[dt.date, list[Candidate]] = {}
    for candidate in fired:
        by_day.setdefault(candidate.date, []).append(candidate)
    days = sorted(by_day)
    draws = day_sequence_draws(
        days, draws=CONFIG["draws"],  # type: ignore[arg-type]
        seed=CONFIG["seed"],  # type: ignore[arg-type]
        expected_block_length=CONFIG["expected_block_length"])  # type: ignore[arg-type]
    print(f"{len(days):,} days; {len(draws)} paired draws generated", flush=True)

    results: dict[str, dict[str, object]] = {}
    for scenario, factor in SCENARIO_FACTORS.items():
        delta = -mu * factor
        h = haircut_factor(fired, delta, commission=commission) if factor else Decimal(0)
        print(f"\nSCENARIO {scenario}: delta={delta:+.6f} haircut={h:.6f}", flush=True)
        for name, staking_rule in ARMS.items():
            realised = replay_run(fired, staking_rule, config, haircut=h)
            realised_metrics = path_metrics(realised, config)
            finals, floors, silents = [], 0, 0
            for sequence_days in draws:
                resampled: list[Candidate] = []
                for order, day in enumerate(sequence_days):
                    base = dt.date(2000, 1, 1) + dt.timedelta(days=order)
                    for c in by_day[day]:
                        resampled.append(Candidate(
                            date=base, market_id=c.market_id, side=c.side, odds=c.odds,
                            p_model=c.p_model, p_market=c.p_market, won=c.won,
                            support=c.support, stratum=c.stratum))
                draw_path = replay_run(resampled, staking_rule, config, haircut=h)
                finals.append(draw_path.final_bank_pence)
                floors += draw_path.ruin is Ruin.DEAD_FLOOR
                silents += draw_path.silent_death_onset is not None
            finals.sort()
            n = len(finals)
            results[f"{scenario}|{name}"] = {
                "realised": realised_metrics,
                "median_final": statistics.median(finals),
                "q05_final": finals[int(0.05 * n)],
                "q25_final": finals[int(0.25 * n)],
                "p_dead_floor": floors / n,
                "p_silent_death": silents / n,
                "draw_finals": finals,
            }
            print(f"  {name:<14} realised {realised_metrics['final']:>7} "
                  f"med {statistics.median(finals):>9} q05 {finals[int(0.05*n)]:>7} "
                  f"P(floor) {floors/n:.3f} P(silent) {silents/n:.3f}", flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    payload = {
        "config": CONFIG, "config_sha256": config_digest,
        "ledger_bets": len(fired), "ledger_sha256": ledger_hash(fired),
        "measured_mean": str(mu),
        "results": {k: {m: v for m, v in row.items() if m != "draw_finals"}
                    for k, row in results.items()},
    }
    out_file = args.out / "results.json"
    out_file.write_text(json.dumps(payload, indent=1, default=str))
    # Draw-level finals for the paired selection analysis, kept separately (large).
    (args.out / "draw_finals.json").write_text(json.dumps(
        {k: row["draw_finals"] for k, row in results.items()}))
    print(f"\nwrote {out_file}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
