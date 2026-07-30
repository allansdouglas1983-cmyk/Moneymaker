"""Emit golden vectors for the SERVED staking policy from the REGISTERED code path.

Policy: TE-0047's D7 conservative-bound allocator, exactly as registered — Kelly at the
conservative bound (delta_e = 0.0249, the TE-0043 day-clustered interval displacement at
the operative threshold), divide-by-k correlation charge over the full selected card,
multi-bet B5 HB-CAP day budget at d_max = 0.30, then reserve_day feasibility and the £1
skip. Every expected stake is computed by calling the registered rule and reserve_day
themselves — nothing here re-derives the policy.

Probabilities are quantised to integer nanoprobability (round(p * 1e9)) because the port
receives IEEE doubles over JSON; from there every operation is exact integer arithmetic
in both languages. Each vector is cross-checked against an exact-rational reference; a
disagreement with the Decimal path would mean a penny-floor boundary case and aborts the
emit rather than shipping an ambiguous vector.

Deterministic: fixed seed, no timestamps. Output: supabase/functions/tips/staking_golden.json
"""
from __future__ import annotations

import datetime as dt
import json
import random
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.staking.engine import Candidate, DayState  # noqa: E402
from tennis_edge.staking.harness import reserve_day  # noqa: E402
from tennis_edge.staking.rules import d7_conservative_bound  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "supabase" / "functions" / "tips" / "staking_golden.json"

# TE-0047 frozen constants — identical to tools/run_staking_study.py.
DELTA_E = Decimal("0.0249")        # TE-0043 raw sweep: 3.86 - 1.37, min_edge 0.02, 2% supported
COMMISSION = Decimal("0.02")       # TE-0044 founder-attested Basic rate
MAX_DRAWDOWN = Decimal("0.30")     # founder tolerance
MIN_STAKE_PENCE = 100
NANO = 1_000_000_000
SEED = 20260731
VECTOR_COUNT = 300


def exact_plan(bank: int, peak: int, card: list[tuple[int, int]]) -> list[int]:
    """Exact-rational reference for the post-cap requests. Cross-check only."""
    k = len(card)
    cap = max((10 * bank - 7 * peak) // 10, 0)
    remaining = cap
    out = []
    for p_nano, odds_c in card:
        if odds_c <= 100:
            out.append(0)
            continue
        b1 = (odds_c - 100) * 98 + 10_000
        num = p_nano * b1 - 10_249 * 10**9
        if num <= 0:
            out.append(0)
            continue
        want = bank * num // (10**9 * (odds_c - 100) * 98 * k)
        grant = min(want, remaining)
        remaining -= grant
        out.append(grant)
    return out


def main() -> None:
    rng = random.Random(SEED)
    rule = d7_conservative_bound(delta_e=DELTA_E, commission=COMMISSION,
                                 max_drawdown=MAX_DRAWDOWN)
    day = dt.date(2026, 7, 30)

    vectors = []
    for index in range(VECTOR_COUNT):
        # Strata: the founder's discussed £200 first; tiny banks force SKIP_MIN; big-edge
        # cards force the HB day budget and reservation branches; drawdown states where
        # the cushion is thin or exactly spent; then the broad uniform sweep.
        stratum = "uniform"
        if index == 0:
            bank = 20_000
        elif index < 50:
            stratum = "tiny_bank"
            bank = rng.randint(100, 5_000)
        elif index < 100:
            stratum = "exhaust"
            bank = rng.randint(2_000, 50_000)
        else:
            bank = rng.randint(100, 2_000_000)

        style = rng.random()
        if style < 0.50:
            peak = bank
        elif style < 0.80:
            peak = rng.randint(bank, (13 * bank) // 10)   # cushion thinning
        else:
            peak = rng.randint((10 * bank) // 7, 2 * bank)  # cushion spent or near it

        card = []
        for _ in range(rng.randint(3, 8) if stratum == "exhaust"
                       else rng.randint(1, 8)):
            odds_c = rng.choice([
                rng.randint(101, 200), rng.randint(201, 500),
                rng.randint(501, 2000), 100,           # 1.00: no net return, always zero
            ] if rng.random() < 0.1 else [
                rng.randint(101, 200), rng.randint(201, 500), rng.randint(501, 2000),
            ])
            implied = NANO * 100 // max(odds_c, 101)
            if stratum == "exhaust":
                shift = rng.choice([250_000_000, 400_000_000, 550_000_000])
            else:
                # Around the conservative break-even: refusals, LEANs and big edges.
                shift = rng.choice([-80_000_000, -20_000_000, 0, 15_000_000,
                                    30_000_000, 60_000_000, 150_000_000])
            p_nano = min(max(implied + shift, 1_000), NANO - 1_000)
            card.append((p_nano, odds_c))

        candidates = [Candidate(date=day, market_id=f"m{index}.{j}", side="A",
                                odds=Decimal(odds_c) / 100,
                                p_model=Decimal(p_nano) / NANO,
                                p_market=Decimal(p_nano) / NANO, won=False,
                                support="SUPPORTED", stratum="vector")
                      for j, (p_nano, odds_c) in enumerate(card)]
        state = DayState(opening_bank_pence=bank, peak_bank_pence=peak,
                         floor_pence=0, min_stake_pence=MIN_STAKE_PENCE,
                         commission=COMMISSION, day_index=0, bets_settled=0)

        requested = list(rule(candidates, state))
        reference = exact_plan(bank, peak, card)
        if requested != reference:
            raise AssertionError(
                f"Decimal path {requested} != exact-rational path {reference} for "
                f"bank={bank} peak={peak} card={card} — penny-floor boundary; refusing "
                "to emit an ambiguous vector")

        granted = reserve_day(requested, bank_pence=bank,
                              min_stake_pence=MIN_STAKE_PENCE)
        vectors.append({
            "bank_pence": bank,
            "peak_pence": peak,
            "candidates": [{"p_nano": p, "odds_c": o} for p, o in card],
            "expected": [{"requested_pence": want, "stake_pence": size,
                          "reason": reason}
                         for want, (size, reason) in zip(requested, granted,
                                                         strict=True)],
        })

    payload = {
        "meta": {
            "policy": "TE-0047 D7 conservative-bound allocator: Kelly at the "
                      "conservative bound (delta_e), /k correlation charge, multi-bet "
                      "HB-CAP day budget (d_max 0.30), reserve_day + GBP 1 skip",
            "source": "tools/emit_staking_vectors.py — emitted from the registered "
                      "Python rules, tennis_edge.staking.{rules,harness}",
            "registration": "docs/TE-0047-d7-registration.md",
            "delta_e": "0.0249 (TE-0043 CI displacement, min_edge 0.02, 2% supported)",
            "commission_hundredths": 2,
            "max_drawdown": "0.30",
            "min_stake_pence": MIN_STAKE_PENCE,
            "p_quantisation": "p_nano = round(p * 1e9)",
            "seed": SEED,
            "count": VECTOR_COUNT,
        },
        "vectors": vectors,
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    total = sum(len(v["candidates"]) for v in vectors)
    reasons: dict[str, int] = {}
    for vector in vectors:
        for row in vector["expected"]:
            reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
    print(f"wrote {VECTOR_COUNT} vectors, {total} bets -> {OUT}")
    print(f"reason mix: {reasons}")


if __name__ == "__main__":
    main()
