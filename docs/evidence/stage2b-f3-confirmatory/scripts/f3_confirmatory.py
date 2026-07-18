"""F3-vs-F2 registered nested chronological confirmatory trial (Stage 2B §4).

Nested design (confirmatory-evaluation-integrity-audit.md, Design A): outer folds =
calendar years 2019..2026(May). For each outer year Y, F2's K and F3's K_surface are
selected by INNER prequential log loss on data strictly BEFORE Y (warm-up <=2018 selects
2019); ratings built through Y-1; both families predict every eligible match in Y from
pre-match ratings (same-day batch). Paired endpoint d = ln p_F3(winner) - ln p_F2(winner)
= ll_F2 - ll_F3 (positive => F3 better), RAW probabilities. Cluster-aware inference via
the adapter-owned l8_evidence.paired_inference block bootstrap (UTC-day clusters, SPEC-090).

Prequential Elo IS the leakage-safe expanding-window equivalent of the cross_fit
orchestrator for Elo (train-on-strictly-earlier-days == ratings-through-yesterday);
used directly here for O(n) tractability. No odds, no June, no names. Deterministic.
"""
from __future__ import annotations

import json
import math
import os
import sys
from bisect import bisect_left
from collections import defaultdict
from datetime import date
from decimal import Decimal

sys.path.insert(0, "/home/user/Moneymaker")
import f2_run as F  # load_tour/build_races/parse helpers (no odds read)
from l8_evidence.paired_inference import PairedRace, block_bootstrap_ci
from sport_core.clustering import ClusterId
from sport_tennis.elo_family import ELO_INITIAL_RATING as R0
from sport_tennis.elo_family import elo_win_probability
from sport_tennis.surface_elo_family import SURFACE_CODES

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = F.RAW
K_GRID = [16.0, 24.0, 32.0]
KS_GRID = [16.0, 24.0, 32.0]
DELTA = 0.0007
CONF = Decimal("0.95")          # two-sided 95% => .lower is the one-sided 97.5% bound
SEED = 20260718
N_RESAMPLES = 20000
LN2 = math.log(2.0)
BANDS = [(0, 0, "0"), (1, 4, "1-4"), (5, 9, "5-9"), (10, 19, "10-19"), (20, 10**9, "20+")]


def load(tour: str):
    matches, excl = F.load_tour(tour)  # (date, key_w, key_l), completed+identity+dedup
    # surface per (date, key_w, key_l): re-read raw for the Surface col (no odds)
    surf = {}
    for fn in sorted(os.listdir(RAW)):
        if not fn.startswith(tour.lower()):
            continue
        for hdr, row in F.iter_rows(os.path.join(RAW, fn)):
            cols = {h: (row[i] if i < len(row) else None) for i, h in enumerate(hdr)}
            d = F.parse_date(cols.get("Date"))
            if d is None:
                continue
            w, l = cols.get("Winner"), cols.get("Loser")
            if not w or not l:
                continue
            from sport_tennis.identity_bridge import _td_key, normalize_name
            kw, kl = _td_key(normalize_name(str(w))), _td_key(normalize_name(str(l)))
            if kw and kl:
                surf[(d, tuple(sorted((kw, kl))))] = SURFACE_CODES.get(str(cols.get("Surface") or "").strip(), 0)
    ids = {}
    def cid(k):
        if k not in ids:
            ids[k] = len(ids) + 1
        return ids[k]
    for k in sorted({x for _, kw, kl in matches for x in (kw, kl)}):
        cid(k)
    rows = []
    for d, kw, kl in sorted(matches, key=lambda m: (m[0], tuple(sorted((m[1], m[2]))))):
        a, b = cid(kw), cid(kl)
        lo, hi = min(a, b), max(a, b)
        rows.append({"date": d, "lo": lo, "hi": hi, "winner": cid(kw),
                     "code": surf.get((d, tuple(sorted((kw, kl)))), 0)})
    return rows, excl


def prequential(rows, k_global, k_surface, collect_lo, collect_hi):
    """One forward pass. Returns predictions for matches with collect_lo<=date<collect_hi:
    list of (date, cluster_date, p_f2_winner, p_f3_winner, cold_band)."""
    g = {}
    s = {}
    appear = defaultdict(int)
    out = []
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["date"]].append(r)
    for d in sorted(by_day):
        day = sorted(by_day[d], key=lambda r: (r["lo"], r["hi"]))
        dg = defaultdict(float)
        ds = defaultdict(float)
        seed = {}
        for r in day:
            lo, hi, code = r["lo"], r["hi"], r["code"]
            rgl, rgh = g.get(lo, R0), g.get(hi, R0)
            p_f2_lo = elo_win_probability(rgl, rgh)
            # surface (F3): seeded from current global at first appearance; unknown->global
            if code != 0:
                for cid_ in (lo, hi):
                    if (cid_, code) not in s and (cid_, code) not in seed:
                        seed[(cid_, code)] = g.get(cid_, R0)
                rsl = s[(lo, code)] if (lo, code) in s else seed[(lo, code)]
                rsh = s[(hi, code)] if (hi, code) in s else seed[(hi, code)]
                p_f3_lo = elo_win_probability(rsl, rsh)
            else:
                p_f3_lo = p_f2_lo
            if collect_lo <= d < collect_hi:
                pw2 = p_f2_lo if r["winner"] == lo else 1 - p_f2_lo
                pw3 = p_f3_lo if r["winner"] == lo else 1 - p_f3_lo
                m = min(appear[lo], appear[hi])
                band = next(lb for a0, b0, lb in BANDS if a0 <= m <= b0)
                out.append((d, pw2, pw3, band))
            # updates
            sa = 1.0 if r["winner"] == lo else 0.0
            dg[lo] += k_global * (sa - p_f2_lo)
            dg[hi] += k_global * ((1 - sa) - (1 - p_f2_lo))
            if code != 0:
                ds[(lo, code)] += k_surface * (sa - p_f3_lo)
                ds[(hi, code)] += k_surface * ((1 - sa) - (1 - p_f3_lo))
        for cid_, dv in dg.items():
            g[cid_] = g.get(cid_, R0) + dv
        for key, base in seed.items():
            s.setdefault(key, base)
        for key, dv in ds.items():
            s[key] = s.get(key, R0) + dv
        for r in day:
            appear[r["lo"]] += 1
            appear[r["hi"]] += 1
    return out


def inner_logloss(rows, k_global, k_surface, y, model):
    """prequential inner loss on [y-3y, y) with data < y."""
    lo_cut = date(y - 3, 1, 1)
    pred = prequential([r for r in rows if r["date"] < date(y, 1, 1)], k_global, k_surface, lo_cut, date(y, 1, 1))
    idx = 2 if model == "f2" else 3  # tuple: (date,p_f2,p_f3,band) -> p at 1 or 2
    j = 1 if model == "f2" else 2
    if not pred:
        return float("inf")
    return sum(-math.log(p[j]) for p in pred) / len(pred)


def main():
    all_pairs = []          # (tour, year, cluster_date, p_f2_win, p_f3_win, band)
    per_fold = {}
    for tour in ("ATP", "WTA"):
        rows, excl = load(tour)
        years = list(range(2019, 2027))
        per_fold[tour] = {}
        for y in years:
            hist = [r for r in rows if r["date"] < date(y, 1, 1)]
            if not any(r for r in rows if date(y, 1, 1) <= r["date"] < date(y + 1, 1, 1) and r["date"] < date(2026, 6, 1)):
                continue
            # inner selection (data < y only)
            kf2 = min(K_GRID, key=lambda k: (inner_logloss(rows, k, k, y, "f2"), k))
            kfs = min(KS_GRID, key=lambda ks: (inner_logloss(rows, kf2, ks, y, "f3"), ks))
            per_fold[tour][y] = {"k_global": kf2, "k_surface": kfs}
            # outer prediction for year y (cap at 2026-05-31)
            preds = prequential(rows, kf2, kfs, date(y, 1, 1), min(date(y + 1, 1, 1), date(2026, 6, 1)))
            for d, pw2, pw3, band in preds:
                all_pairs.append((tour, y, d, pw2, pw3, band))
        print(f"[{tour}] folds={sorted(per_fold[tour])} preds so far={len([1 for p in all_pairs if p[0]==tour])}", flush=True)

    # --- overall confirmatory inference (UTC-day clusters, both tours pooled per day) ---
    def to_paired(pairs):
        out = []
        for i, (tour, y, d, pw2, pw3, band) in enumerate(pairs):
            p2 = min(max(pw2, 1e-9), 1 - 1e-9)
            p3 = min(max(pw3, 1e-9), 1 - 1e-9)
            out.append(PairedRace(race_id=f"{tour}:{y}:{i}", cluster_id=ClusterId(f"tennis:day:{d.isoformat()}"),
                                  p_market_winner=Decimal(str(p2)), p_combined_winner=Decimal(str(p3))))
        return out

    result = {}
    for label, subset in (("overall", all_pairs), ("ATP", [p for p in all_pairs if p[0] == "ATP"]),
                          ("WTA", [p for p in all_pairs if p[0] == "WTA"])):
        pr = to_paired(subset)
        ci = block_bootstrap_ci(pr, seed=SEED, confidence_level=CONF, n_resamples=N_RESAMPLES)
        ll_f2 = sum(-math.log(float(x.p_market_winner)) for x in pr) / len(pr)
        ll_f3 = sum(-math.log(float(x.p_combined_winner)) for x in pr) / len(pr)
        result[label] = {"n_races": ci.n_races, "n_clusters": ci.n_clusters,
                         "ll_F2": round(ll_f2, 6), "ll_F3": round(ll_f3, 6),
                         "mean_d": round(ci.mean_d, 6), "lower_975": round(ci.lower, 6),
                         "upper": round(ci.upper, 6), "ci_digest": ci.content_digest()}
    # cluster-size distribution (overall)
    cl = defaultdict(int)
    for (_t, _y, d, *_r) in all_pairs:
        cl[d.isoformat()] += 1
    sizes = sorted(cl.values())
    dist = {"n_clusters": len(sizes), "min": sizes[0], "p50": sizes[len(sizes)//2],
            "p90": sizes[int(0.9*len(sizes))], "max": sizes[-1],
            "mean": round(sum(sizes)/len(sizes), 2)}
    # yearly
    yearly = {}
    for (tour, y, d, pw2, pw3, band) in all_pairs:
        yr = yearly.setdefault(y, {"n": 0, "ll_F2": 0.0, "ll_F3": 0.0})
        yr["n"] += 1; yr["ll_F2"] += -math.log(min(max(pw2,1e-9),1-1e-9)); yr["ll_F3"] += -math.log(min(max(pw3,1e-9),1-1e-9))
    for y in yearly:
        yearly[y] = {"n": yearly[y]["n"], "ll_F2": round(yearly[y]["ll_F2"]/yearly[y]["n"],5),
                     "ll_F3": round(yearly[y]["ll_F3"]/yearly[y]["n"],5)}
    o = result["overall"]
    if o["upper"] < 0:
        verdict = "FAIL_HARM"
    elif o["mean_d"] >= DELTA and o["lower_975"] > 0:
        verdict = "PASS"
    elif o["upper"] < DELTA:
        verdict = "FAIL_FUTILITY"
    else:
        verdict = "CONTINUE"
    report = {"delta": DELTA, "confidence": "0.975 one-sided lower (=.lower of 95% two-sided)",
              "seed": SEED, "n_resamples": N_RESAMPLES, "results": result,
              "cluster_size_distribution": dist, "yearly": {str(k): v for k, v in sorted(yearly.items())},
              "selected_k_by_fold": per_fold, "verdict": verdict}
    json.dump(report, open(os.path.join(ROOT, "F3_CONFIRMATORY_REPORT.json"), "w"), indent=1, sort_keys=True, default=str)
    print(json.dumps({"verdict": verdict, **{k: result[k] for k in result}}, indent=1))


if __name__ == "__main__":
    main()
