"""Packets A (candidate delta) and B (planning sigma_d) — OUTCOME-BLIND planning evidence.

Founder direction 2026-07-18. Uses ONLY: frozen June market probabilities (first-instance
T-5m two-sided books from the deterministic Stage-1 reconstruction), measured displayed
prices, and declared commission scenarios. NO real outcome, settlement, or winner is read
anywhere. Synthetic winners in Packet B are drawn from the MARKET probability with fixed
literal seeds. Floats are acceptable here: this is planning evidence, not money code.

PREDECLARED design (before any computation was run):
- market probability: normalized implied midpoint of best back/lay (info-price-v1 concept)
  at the FIRST T-5m horizon instance, primary singles cohort, complete two-sided books;
- residual-information scenarios: affected fraction f in {1%,5%,10%,20%};
  probability-shift magnitude dp in {0.01, 0.02, 0.05} (absolute, on the favourite);
  shapes: SYMMETRIC (random +/- per affected match), FAVOURITE (toward favourite),
  UNDERDOG (toward underdog); q clamped to [0.02, 0.98];
- log scores in NATS; mean per-match improvement over ALL matches = f-weighted mean
  KL(q||p) (exact, no simulation needed for the mean);
- best-case actionable rate: EV = q*(O-1)*(1-c) - (1-q) > 0 at the best displayed back
  price of the shifted-up selection, commission c in {2%, 5%};
- probability bands on the favourite: [0.5,0.6), [0.6,0.75), [0.75,0.9), [0.9,1.0);
- Packet B: winners ~ Bernoulli(p_market) (the market-correct world), R=100 seeded
  replications; d_m = ln q(w) - ln p(w); sigma_d = std over ALL matches (zeros included);
  conservative planning value = the PREDECLARED 90th percentile of sigma_d across all
  scenario x replication combinations, paired in the N table with each scenario's own
  delta; N derived by l8_evidence.sample_size.derive_sample_size (two_sided=True,
  conservative) at power=0.80 with per-trial alpha in {0.05/1, 0.05/6} from the
  family-wise alpha_total=0.05.
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
from decimal import Decimal

sys.path.insert(0, ".")
from l8_evidence.sample_size import PowerAssumptions, derive_sample_size  # noqa: E402
from price_contracts.ladder import price_of  # noqa: E402

RECON = "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/audit/recon_full.jsonl"
SEED_BASE = "stage2b-packets:20260718"
FRACTIONS = [0.01, 0.05, 0.10, 0.20]
SHIFTS = [0.01, 0.02, 0.05]
SHAPES = ["SYMMETRIC", "FAVOURITE", "UNDERDOG"]
COMMISSIONS = [0.02, 0.05]
BANDS = [(0.5, 0.6), (0.6, 0.75), (0.75, 0.9), (0.9, 1.0)]
CLAMP_LO, CLAMP_HI = 0.02, 0.98
REPS = 100
ALPHA_TOTAL = 0.05
PLANNED_FAMILY_COUNTS = [1, 6]
POWER = "0.80"


def load_matches() -> list[dict]:
    out = []
    n_no_instance = 0
    n_not_two_sided = 0
    with open(RECON) as f:
        for line in f:
            r = json.loads(line)
            if r.get("error") or r.get("cohort") != "PRIMARY_JUNE_SINGLES_UNIVERSE":
                continue
            insts = r["horizons"]["300"]["instances"]
            if not insts:
                n_no_instance += 1
                continue
            inst = insts[0]
            sels = inst["selections"]
            if len(sels) != 2 or not all(s["back"] and s["lay"] for s in sels.values()):
                n_not_two_sided += 1
                continue
            mids = {}
            backs = {}
            for sid, s in sels.items():
                bb, bl = s["back"][0][0], s["lay"][0][0]
                mids[sid] = (1 / float(price_of(bb)) + 1 / float(price_of(bl))) / 2
                backs[sid] = float(price_of(bb))
            tot = sum(mids.values())
            sids = sorted(sels, key=lambda k: -mids[k])  # favourite first
            p_fav = mids[sids[0]] / tot
            out.append(
                {
                    "market_id": r["market_id"],
                    "strict": bool(r.get("strict_sensitivity")),
                    "p_fav": p_fav,
                    "back_fav": backs[sids[0]],
                    "back_dog": backs[sids[1]],
                }
            )
    print(f"loaded {len(out)} matches (no_instance={n_no_instance}, not_two_sided={n_not_two_sided})")
    return out


def kl_binary(q: float, p: float) -> float:
    return q * math.log(q / p) + (1 - q) * math.log((1 - q) / (1 - p))


def clamp(x: float) -> float:
    return min(CLAMP_HI, max(CLAMP_LO, x))


def scenario_assignment(matches: list[dict], shape: str, f: float, dp: float) -> list[dict]:
    """Deterministically choose affected matches and their true probability q_fav."""
    rng = random.Random(f"{SEED_BASE}:assign:{shape}:{f}:{dp}")
    n_aff = round(f * len(matches))
    idx = rng.sample(range(len(matches)), n_aff)
    rows = []
    for i in idx:
        m = matches[i]
        if shape == "FAVOURITE":
            q = clamp(m["p_fav"] + dp)
        elif shape == "UNDERDOG":
            q = clamp(m["p_fav"] - dp)
        else:
            q = clamp(m["p_fav"] + (dp if rng.random() < 0.5 else -dp))
        rows.append({**m, "q_fav": q})
    return rows


def packet_a(matches: list[dict]) -> dict:
    n = len(matches)
    scenarios = []
    for shape in SHAPES:
        for f in FRACTIONS:
            for dp in SHIFTS:
                aff = scenario_assignment(matches, shape, f, dp)
                kls = [kl_binary(a["q_fav"], a["p_fav"]) for a in aff]
                mean_all = sum(kls) / n if n else 0.0
                mean_aff = sum(kls) / len(kls) if kls else 0.0
                shifts = [abs(a["q_fav"] - a["p_fav"]) for a in aff]
                clearing = {}
                for c in COMMISSIONS:
                    n_clear = 0
                    for a in aff:
                        up_is_fav = a["q_fav"] > a["p_fav"]
                        q = a["q_fav"] if up_is_fav else 1 - a["q_fav"]
                        odds = a["back_fav"] if up_is_fav else a["back_dog"]
                        if q * (odds - 1) * (1 - c) - (1 - q) > 0:
                            n_clear += 1
                    clearing[f"c={c:.0%}"] = {
                        "pct_of_affected": round(100 * n_clear / len(aff), 1) if aff else None,
                        "pct_of_all_matches": round(100 * n_clear / n, 2) if n else None,
                    }
                by_band = {}
                for lo, hi in BANDS:
                    baff = [a for a in aff if lo <= a["p_fav"] < hi]
                    if baff:
                        by_band[f"[{lo},{hi})"] = {
                            "n_affected": len(baff),
                            "mean_kl_nats": round(sum(kl_binary(a["q_fav"], a["p_fav"]) for a in baff) / len(baff), 6),
                            "pct_clear_c2": round(
                                100
                                * sum(
                                    1
                                    for a in baff
                                    if (
                                        (a["q_fav"] if a["q_fav"] > a["p_fav"] else 1 - a["q_fav"])
                                        * ((a["back_fav"] if a["q_fav"] > a["p_fav"] else a["back_dog"]) - 1)
                                        * 0.98
                                        - (1 - (a["q_fav"] if a["q_fav"] > a["p_fav"] else 1 - a["q_fav"]))
                                    )
                                    > 0
                                )
                                / len(baff),
                                1,
                            ),
                        }
                scenarios.append(
                    {
                        "shape": shape,
                        "affected_fraction": f,
                        "dp": dp,
                        "n_affected": len(aff),
                        "mean_logscore_improvement_all_nats": round(mean_all, 7),
                        "mean_logscore_improvement_affected_nats": round(mean_aff, 6),
                        "mean_abs_prob_shift_post_clamp": round(sum(shifts) / len(shifts), 5) if shifts else None,
                        "best_case_ev_clearing": clearing,
                        "by_favourite_band": by_band,
                    }
                )
    return {"n_matches": n, "scenarios": scenarios}


def packet_b(matches: list[dict], a: dict) -> dict:
    n = len(matches)
    rows = []
    all_sigmas = []
    for shape in SHAPES:
        for f in FRACTIONS:
            for dp in SHIFTS:
                aff = scenario_assignment(matches, shape, f, dp)
                aff_by_id = {m["market_id"]: m for m in aff}
                sigmas = []
                for rep in range(REPS):
                    rng = random.Random(f"{SEED_BASE}:winners:{shape}:{f}:{dp}:{rep}")
                    ds = []
                    for m in matches:
                        qa = aff_by_id.get(m["market_id"])
                        if qa is None:
                            ds.append(0.0)
                            continue
                        p, q = m["p_fav"], qa["q_fav"]
                        fav_wins = rng.random() < p  # winners from the MARKET probability
                        d = (math.log(q) - math.log(p)) if fav_wins else (math.log(1 - q) - math.log(1 - p))
                        ds.append(d)
                    sigmas.append(statistics.pstdev(ds))
                all_sigmas.extend(sigmas)
                rows.append(
                    {
                        "shape": shape,
                        "affected_fraction": f,
                        "dp": dp,
                        "sigma_d_mean": round(statistics.mean(sigmas), 6),
                        "sigma_d_p90": round(sorted(sigmas)[int(0.9 * (len(sigmas) - 1))], 6),
                    }
                )
    conservative = sorted(all_sigmas)[int(0.9 * (len(all_sigmas) - 1))]
    # N table: each scenario's own delta (Packet A mean improvement, alternative world)
    delta_by_key = {
        (s["shape"], s["affected_fraction"], s["dp"]): s["mean_logscore_improvement_all_nats"]
        for s in a["scenarios"]
    }
    n_table = []
    for r in rows:
        delta = delta_by_key[(r["shape"], r["affected_fraction"], r["dp"])]
        if delta <= 0:
            continue
        entry = {**{k: r[k] for k in ("shape", "affected_fraction", "dp")}, "delta_nats": delta}
        for k in PLANNED_FAMILY_COUNTS:
            pa = PowerAssumptions(
                alpha=Decimal(str(ALPHA_TOTAL)) / k,
                power=Decimal(POWER),
                sigma_d=Decimal(str(round(r["sigma_d_p90"], 6))),
                delta=Decimal(str(delta)),
                two_sided=True,
            )
            entry[f"N_required_alpha_{ALPHA_TOTAL}/{k}"] = derive_sample_size(pa).n_required
        n_table.append(entry)
    return {
        "winners_source": "synthetic Bernoulli(p_market) — NO real outcome used",
        "replications": REPS,
        "sigma_d_by_scenario": rows,
        "conservative_planning_sigma_d_p90_all": round(conservative, 6),
        "note": "sigma_d is a PLANNING ASSUMPTION, not a measured fact",
        "sample_size_table_power_0.80_two_sided": n_table,
    }


def main() -> None:
    matches = load_matches()
    a = packet_a(matches)
    b = packet_b(matches, a)
    with open("docs/evidence/stage2b-planning-packets/packet_a.json", "w") as fh:
        json.dump(a, fh, indent=1, sort_keys=True)
    with open("docs/evidence/stage2b-planning-packets/packet_b.json", "w") as fh:
        json.dump(b, fh, indent=1, sort_keys=True)
    print("packet A scenarios:", len(a["scenarios"]))
    print("packet B conservative sigma_d (p90):", b["conservative_planning_sigma_d_p90_all"])


if __name__ == "__main__":
    main()
