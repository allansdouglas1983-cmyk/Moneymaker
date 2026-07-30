"""Emit golden vectors for the SERVED staking policy from the REGISTERED code path.

The site must display the exact policy the study measured and ADR 0020 Amendment 2
adopted: ``hb_cap(conservative_kelly(shrink=1.37/3.86, commission=0.02), 0.50)`` sized
off the live bank, then STK-HARNESS-V1 §1.6 sequential day reservation with the £1
exchange-minimum skip. Nothing here re-derives that policy — every expected stake is
computed by calling the registered rule composition and :func:`reserve_day` themselves,
so the vectors pin the JavaScript port to the study's arithmetic, not to a description
of it.

Probabilities are quantised to integer nanoprobability (round(p * 1e9)) because the
port receives IEEE doubles over JSON; the quantisation makes every downstream operation
exact integer arithmetic in both languages. Each vector is double-checked against an
exact-rational reference; a disagreement with the Decimal path (which computes at 28
significant digits) would mean a penny-floor boundary case and aborts the emit rather
than shipping an ambiguous vector.

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
from tennis_edge.staking.rules import conservative_kelly, hb_cap  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "supabase" / "functions" / "tips" / "staking_golden.json"

# The adopted policy's frozen parameters — identical to tools/run_staking_study.py.
SHRINK = Decimal("1.37") / Decimal("3.86")           # TE-0043 measured ratio, never chosen
COMMISSION = Decimal("0.02")                          # TE-0044: Basic package, founder-attested
HB_MAX_DRAWDOWN = Decimal("0.50")
MIN_STAKE_PENCE = 100
NANO = 1_000_000_000
SEED = 20260730
VECTOR_COUNT = 300


def exact_requested(bank: int, peak: int, p_nano: int, odds_c: int) -> int:
    """Exact-rational reference for one bet's post-cap request. Cross-check only."""
    if odds_c <= 100:
        want = 0
    else:
        num1 = p_nano * (odds_c - 100) * 98 - (NANO - p_nano) * 10_000
        if num1 <= 0:
            want = 0
        else:
            want = bank * num1 * 137 // (NANO * (odds_c - 100) * 98 * 386)
    cap = max((2 * bank - peak) // 2, 0)
    return min(want, cap)


def main() -> None:
    rng = random.Random(SEED)
    rule = hb_cap(conservative_kelly(shrink=SHRINK, commission=COMMISSION),
                  HB_MAX_DRAWDOWN)
    day = dt.date(2026, 7, 30)

    vectors = []
    for index in range(VECTOR_COUNT):
        # Banks from £1 to £20,000; always include the founder's discussed £200 first.
        # Two dedicated strata force the reservation branches the uniform draw almost
        # never reaches: tiny banks (sub-£1 requests -> SKIP_MIN) and big-edge cards
        # that exhaust the bank (CLAMP_RESERVE, then SKIP_RESERVE behind the clamp).
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
        # Peak is the high-water mark, so peak >= bank; occasionally deep drawdown
        # states where the HB cap bites hard or reaches exactly zero.
        style = rng.random()
        if style < 0.55:
            peak = bank
        elif style < 0.85:
            peak = rng.randint(bank, 2 * bank)
        else:
            peak = rng.randint(2 * bank, 3 * bank)   # cap is zero at or beyond 2x

        card = []
        for _ in range(rng.randint(4, 8) if stratum == "exhaust"
                       else rng.randint(1, 8)):
            odds_c = rng.choice([
                rng.randint(101, 200), rng.randint(201, 500),
                rng.randint(501, 2000), 100,          # 1.00: no net return, always zero
            ] if rng.random() < 0.1 else [
                rng.randint(101, 200), rng.randint(201, 500), rng.randint(501, 2000),
            ])
            implied = NANO * 100 // max(odds_c, 101)
            if stratum == "exhaust":
                shift = rng.choice([250_000_000, 400_000_000, 550_000_000])
            else:
                shift = rng.choice([-80_000_000, -20_000_000, 0, 10_000_000,
                                    40_000_000, 120_000_000, 300_000_000])
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
        for want, (p_nano, odds_c) in zip(requested, card, strict=True):
            reference = exact_requested(bank, peak, p_nano, odds_c)
            if want != reference:
                raise AssertionError(
                    f"Decimal path {want} != exact-rational path {reference} for "
                    f"bank={bank} peak={peak} p_nano={p_nano} odds_c={odds_c} — "
                    "penny-floor boundary; refusing to emit an ambiguous vector")

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
            "policy": "hb_cap(conservative_kelly(shrink=1.37/3.86, commission=0.02), 0.50) "
                      "+ STK-HARNESS-V1 §1.6 sequential reservation + £1 minimum skip",
            "source": "tools/emit_staking_vectors.py — emitted from the registered "
                      "Python rules, tennis_edge.staking.{rules,harness}",
            "adr": "ADR 0020 Amendment 2",
            "shrink": "137/386 (TE-0043 measured conservative-bound/point ratio)",
            "commission_hundredths": 2,
            "hb_max_drawdown": "1/2",
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
