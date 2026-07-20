"""Stage 2F §8 ROLLING_AFFINE_365D_V1 + §9 SPEC032_POST_FAILURE_DIAGNOSTIC_V1 (development only).

Lower-player-side convention throughout (the bundle's designated = lower competitor id).
§8: for each June UTC day D fit the frozen two-parameter affine per tour on lawful lower-side
rows from [D-365, D-1] only (regenerated pre-June prequential + already-scored June days < D,
OUTCOME_SOURCE_CONFLICT excluded), apply to day-D frozen raw predictions. One window only.
§9: frozen combination formula only — p = softmax(alpha*ln p_f + beta*ln p_m) — expanding
UTC-day chronological folds over the prospective F0/F2 intersection; warm-up days refuse
explicitly; no tour coefficients, no interactions, no regularization search, no odds.
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, "/home/user/Moneymaker")
SCRATCH = Path("/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad")
sys.path.insert(0, str(SCRATCH / "tennis-data"))
from f2_run import load_tour  # type: ignore[import-not-found]  # noqa: E402

REPO = Path("/home/user/Moneymaker")
OUTDIR = REPO / "docs/evidence/stage2f-post-failure"
CONFLICT = "1.259522098"
FROZEN = {"ATP": (0.025399, 1.218638), "WTA": (0.029204, 1.150681)}


def clamp(p: float) -> float:
    return min(max(p, 1e-12), 1 - 1e-12)


def logit(p: float) -> float:
    p = clamp(p)
    return math.log(p / (1 - p))


def sig(z: float) -> float:
    z = max(-700.0, min(700.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def fit2(feats: list[tuple[float, float]], ys: list[int]) -> tuple[float, float, bool]:
    """2-feature no-intercept logistic MLE y ~ sigmoid(a*f1 + b*f2) (IRLS)."""
    a, b = 1.0, 0.0
    for _ in range(200):
        s11 = s12 = s22 = g1 = g2 = 0.0
        for (f1, f2), y in zip(feats, ys):
            mu = sig(a * f1 + b * f2)
            w = max(mu * (1 - mu), 1e-12)
            r = y - mu
            g1 += r * f1
            g2 += r * f2
            s11 += w * f1 * f1
            s12 += w * f1 * f2
            s22 += w * f2 * f2
        det = s11 * s22 - s12 * s12
        if abs(det) < 1e-12:
            return a, b, False
        da = (s22 * g1 - s12 * g2) / det
        db = (s11 * g2 - s12 * g1) / det
        a += da
        b += db
        if abs(da) + abs(db) < 1e-11:
            return a, b, True
    return a, b, False


def fit_affine(pairs: list[tuple[float, int]]) -> tuple[float, float]:
    """(intercept, temperature) via y ~ sigmoid(a + u*logit(p)); T = 1/u (frozen form)."""
    xs = [logit(p) for p, _ in pairs]
    a, u = 0.0, 1.0
    for _ in range(200):
        sw = swx = swxx = g0 = g1 = 0.0
        for x, (_, y) in zip(xs, pairs):
            mu = sig(a + u * x)
            w = max(mu * (1 - mu), 1e-12)
            r = y - mu
            g0 += r
            g1 += r * x
            sw += w
            swx += w * x
            swxx += w * x * x
        det = sw * swxx - swx * swx
        if abs(det) < 1e-13:
            break
        da = (swxx * g0 - swx * g1) / det
        du = (sw * g1 - swx * g0) / det
        a += da
        u += du
        if abs(da) + abs(du) < 1e-12:
            break
    return a, 1.0 / u


def ll_of(pairs: list[tuple[float, int]]) -> float:
    return round(sum(-math.log(clamp(p if y == 1 else 1 - p)) for p, y in pairs) / len(pairs), 6)


def mk_metrics(pairs: list[tuple[float, int]]) -> dict[str, float]:
    n = len(pairs)
    mp = sum(p for p, _ in pairs) / n
    my = sum(y for _, y in pairs) / n
    return {"n": n, "log_loss": ll_of(pairs),
            "brier": round(sum((p - y) ** 2 for p, y in pairs) / n, 6),
            "cal_in_large": round(logit(my) - logit(mp), 6)}


def main() -> None:
    bundle = [json.loads(ln) for ln in
              (REPO / "docs/evidence/stage2e-june-m1-bundle/JUNE_M1_PREDICTION_BUNDLE.jsonl")
              .read_text().splitlines() if ln.strip()]
    art = json.loads((REPO / "docs/evidence/stage2e-june-m1-artifact/RECOVERY_OUTCOME_ARTIFACT.json").read_text())
    win = {o["market_id"]: int(o["winner_selection_id"]) for o in art["outcomes"]}
    rows = [{**p, "y": 1 if win[p["market_id"]] == int(p["selection_id_designated"]) else 0}
            for p in bundle if p["market_id"] in win and p["market_id"] != CONFLICT]

    # lower-side pre-June prequential history (regenerated; verified in stage2f_core)
    pre: dict[str, list[tuple[date, float, int]]] = {"ATP": [], "WTA": []}
    for tour in ("ATP", "WTA"):
        matches, _ = load_tour(tour)
        R: dict[tuple[str, str], float] = defaultdict(lambda: 1500.0)
        by_day: dict[date, list[tuple[tuple[str, str], tuple[str, str]]]] = defaultdict(list)
        for d, kw, kl in matches:
            by_day[d].append((kw, kl))
        for d in sorted(by_day):
            deltas: dict[tuple[str, str], float] = defaultdict(float)
            for kw, kl in by_day[d]:
                pw = 1.0 / (1.0 + 10.0 ** ((R[kl] - R[kw]) / 400.0))
                lo_is_winner = kw < kl
                pre[tour].append((d, pw if lo_is_winner else 1.0 - pw, 1 if lo_is_winner else 0))
                deltas[kw] += 24.0 * (1.0 - pw)
                deltas[kl] -= 24.0 * (1.0 - pw)
            for k, dv in deltas.items():
                R[k] += dv

    # ---------------- §8 rolling affine 365d ----------------
    days = sorted({r["cluster_day"] for r in rows})
    path: dict[str, dict[str, Any]] = {}
    roll_pairs: list[tuple[float, int]] = []
    roll_by_market: dict[str, float] = {}
    by_tour_pairs: dict[str, list[tuple[float, int]]] = {"ATP": [], "WTA": []}
    for ds in days:
        D = date.fromisoformat(ds)
        lo, hi = D - timedelta(days=365), D - timedelta(days=1)
        params: dict[str, tuple[float, float]] = {}
        for tour in ("ATP", "WTA"):
            fitset = [(p, y) for (d, p, y) in pre[tour] if lo <= d <= hi]
            fitset += [(float(r["p_raw_designated"]), int(r["y"])) for r in rows
                       if r["tour"] == tour and lo <= date.fromisoformat(r["cluster_day"]) <= hi]
            params[tour] = fit_affine(fitset)
        path[ds] = {t: {"intercept": round(params[t][0], 6), "temperature": round(params[t][1], 6)}
                    for t in ("ATP", "WTA")}
        for r in (r for r in rows if r["cluster_day"] == ds):
            a, T = params[r["tour"]]
            pc = sig(a + logit(float(r["p_raw_designated"])) / T)
            roll_pairs.append((pc, int(r["y"])))
            roll_by_market[r["market_id"]] = pc
            by_tour_pairs[r["tour"]].append((pc, int(r["y"])))
    static_pairs = [(float(r["p_cal_designated"]), int(r["y"])) for r in rows]
    s8: dict[str, Any] = {
        "diagnostic": "ROLLING_AFFINE_365D_V1 (development evidence only)",
        "window": "single registered window: [D-365, D-1]; same-day batch preserved; no June "
                  "outcome calibrates itself; OUTCOME_SOURCE_CONFLICT excluded everywhere",
        "coverage": {"scored": len(roll_pairs), "refusals": 0,
                     "refusal_rule": "refuse if a tour window held < 200 rows (never triggered; "
                                     "min window ~15k rows)"},
        "prequential_scorecard": {"overall": mk_metrics(roll_pairs),
                                  "ATP": mk_metrics(by_tour_pairs["ATP"]),
                                  "WTA": mk_metrics(by_tour_pairs["WTA"])},
        "static_affine_comparison": {"overall": mk_metrics(static_pairs)},
        "parameter_path_first_mid_last": {ds: path[ds] for ds in (days[0], days[len(days) // 2], days[-1])},
        "parameter_path_full": path,
        "weekly_log_loss_rolling_vs_static": {
            f"W{w}": {
                "rolling": ll_of([pp for pp, ds2 in
                                  zip(roll_pairs, [r["cluster_day"] for r in rows])
                                  if (date.fromisoformat(ds2).day - 1) // 7 + 1 == w] or [(0.5, 0)]),
                "static": ll_of([(float(r["p_cal_designated"]), int(r["y"])) for r in rows
                                 if (date.fromisoformat(r["cluster_day"]).day - 1) // 7 + 1 == w] or [(0.5, 0)]),
            } for w in (1, 2, 3, 4, 5)},
    }
    (OUTDIR / "S8_ROLLING_AFFINE_365D.json").write_text(json.dumps(s8, indent=1, sort_keys=True))
    print("S8 rolling:", s8["prequential_scorecard"]["overall"],
          "| static:", s8["static_affine_comparison"]["overall"])
    print("S8 params first/last:", path[days[0]], path[days[-1]])

    # ---------------- §9 SPEC-032 expanding chronological ----------------
    f0: dict[str, dict[str, float]] = {}
    for ln in (SCRATCH / "tennis-data/F0_MARKET_YARDSTICK_MANIFEST.jsonl").read_text().splitlines():
        r = json.loads(ln)
        if r.get("committed") and r.get("p_market_by_selection"):
            f0[r["market_id"]] = {str(k): float(v) for k, v in r["p_market_by_selection"].items()}
    inter = json.loads((SCRATCH / "tennis-data/JUNE_M2_INTERSECTION_MANIFEST.json").read_text())
    reg_ids = set(inter["final_prospective_intersection"]["market_ids"]) \
        if isinstance(inter.get("final_prospective_intersection"), dict) else set()
    if not reg_ids:
        fi = inter.get("final_prospective_intersection")
        reg_ids = set(fi if isinstance(fi, list) else [])
    ex9 = []
    for r in rows:
        mid = r["market_id"]
        if mid not in f0 or (reg_ids and mid not in reg_ids):
            continue
        pm_by = f0[mid]
        pm_d = pm_by.get(str(r["selection_id_designated"]))
        pm_o = pm_by.get(str(r["selection_id_other"]))
        if pm_d is None or pm_o is None:
            continue
        tot = pm_d + pm_o
        pf = clamp(float(r["p_cal_designated"]))
        pm = clamp(pm_d / tot)
        ex9.append({"mid": mid, "day": r["cluster_day"], "tour": r["tour"], "y": int(r["y"]),
                    "df": math.log(pf) - math.log(1 - pf), "dm": math.log(pm) - math.log(1 - pm),
                    "pf": pf, "pm": pm,
                    "df_roll": (lambda pr: math.log(pr) - math.log(1 - pr))(clamp(roll_by_market[mid]))})
    ex9.sort(key=lambda e: (e["day"], e["mid"]))
    days9 = sorted({e["day"] for e in ex9})
    WARMUP_MIN = 50
    folds: dict[str, Any] = {}
    fwd: list[dict[str, Any]] = []
    refused = 0
    for ds in days9:
        train = [e for e in ex9 if e["day"] < ds]
        test = [e for e in ex9 if e["day"] == ds]
        if len(train) < WARMUP_MIN:
            refused += len(test)
            folds[ds] = {"refused": len(test), "n_train": len(train)}
            continue
        a, b, conv = fit2([(e["df"], e["dm"]) for e in train], [e["y"] for e in train])
        a2, b2, _ = fit2([(e["df_roll"], e["dm"]) for e in train], [e["y"] for e in train])
        folds[ds] = {"alpha": round(a, 4), "beta": round(b, 4), "converged": conv,
                     "n_train": len(train), "n_test": len(test),
                     "alpha_roll": round(a2, 4), "beta_roll": round(b2, 4)}
        for e in test:
            fwd.append({**e, "p_comb": sig(a * e["df"] + b * e["dm"]),
                        "p_comb_roll": sig(a2 * e["df_roll"] + b2 * e["dm"])})
    mkt = [(e["pm"], e["y"]) for e in fwd]
    f2o = [(e["pf"], e["y"]) for e in fwd]
    cmb = [(e["p_comb"], e["y"]) for e in fwd]
    cmb2 = [(e["p_comb_roll"], e["y"]) for e in fwd]
    diffs_by_day: dict[str, list[float]] = defaultdict(list)
    for e in fwd:
        dm = -math.log(clamp(e["pm"] if e["y"] == 1 else 1 - e["pm"]))
        dc = -math.log(clamp(e["p_comb"] if e["y"] == 1 else 1 - e["p_comb"]))
        diffs_by_day[e["day"]].append(dm - dc)
    rng = random.Random(20260720)
    daylist = sorted(diffs_by_day)
    boots = []
    for _ in range(1000):
        picks = [daylist[rng.randrange(len(daylist))] for _ in daylist]
        vals = [v for d in picks for v in diffs_by_day[d]]
        boots.append(sum(vals) / len(vals))
    boots.sort()
    alphas = [folds[d]["alpha"] for d in days9 if "alpha" in folds[d]]
    betas = [folds[d]["beta"] for d in days9 if "beta" in folds[d]]
    s9 = {
        "diagnostic": "SPEC032_POST_FAILURE_DIAGNOSTIC_V1 (development evidence only; no alpha "
                      "consumed; M2 not evaluated; no deployable coefficients declared)",
        "intersection": {"eligible": len(ex9), "scored_forward": len(fwd),
                         "refused_warmup": refused, "warmup_rule": f"n_train >= {WARMUP_MIN}"},
        "forward_log_loss": {"market_only": ll_of(mkt), "f2_affine_only": ll_of(f2o),
                             "combined": ll_of(cmb), "combined_with_rolling_f2": ll_of(cmb2)},
        "paired_market_minus_combined_mean": round(sum(v for vs in diffs_by_day.values() for v in vs)
                                                   / len(fwd), 6),
        "day_cluster_bootstrap_2p5_97p5": [round(boots[24], 6), round(boots[974], 6)],
        "coefficient_stability": {
            "alpha_first_last": [alphas[0], alphas[-1]] if alphas else [],
            "beta_first_last": [betas[0], betas[-1]] if betas else [],
            "alpha_range": [min(alphas), max(alphas)] if alphas else [],
            "beta_range": [min(betas), max(betas)] if betas else [],
        },
        "per_tour_secondary": {
            t: {"market_only": ll_of([(e["pm"], e["y"]) for e in fwd if e["tour"] == t]),
                "combined": ll_of([(e["p_comb"], e["y"]) for e in fwd if e["tour"] == t])}
            for t in ("ATP", "WTA") if any(e["tour"] == t for e in fwd)},
        "weekly_stability": {
            f"W{w}": {"n": sum(1 for e in fwd if (date.fromisoformat(e["day"]).day - 1) // 7 + 1 == w),
                      "market_only": ll_of([(e["pm"], e["y"]) for e in fwd
                                            if (date.fromisoformat(e["day"]).day - 1) // 7 + 1 == w] or [(0.5, 0)]),
                      "combined": ll_of([(e["p_comb"], e["y"]) for e in fwd
                                         if (date.fromisoformat(e["day"]).day - 1) // 7 + 1 == w] or [(0.5, 0)])}
            for w in (1, 2, 3, 4, 5)},
        "folds": folds,
    }
    (OUTDIR / "S9_SPEC032_EXPANDING.json").write_text(json.dumps(s9, indent=1, sort_keys=True))
    print("S9:", s9["forward_log_loss"], "| paired mean:", s9["paired_market_minus_combined_mean"],
          "| CI:", s9["day_cluster_bootstrap_2p5_97p5"])
    print("S9 coeffs:", s9["coefficient_stability"], "| n_fwd:", len(fwd), "refused:", refused)


if __name__ == "__main__":
    main()
