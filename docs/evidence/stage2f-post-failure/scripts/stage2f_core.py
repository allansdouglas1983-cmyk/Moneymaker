"""Stage 2F §4-§7 diagnostics (POST_FAILURE_DIAGNOSTIC scope; development evidence only).

Cohort: the 1,153 diagnostic rows (1,154 scored minus the OUTCOME_SOURCE_CONFLICT market),
except §4 which reproduces the FROZEN 1,154-row Stage-A scorecard through a second independent
implementation (IRLS with a working response — no import of the l8 harness scoring helpers).
Pre-June per-match raw predictions are REGENERATED prequentially from the registered Elo family
(P = 1/(1+10^((Rb-Ra)/400)), init 1500, K=24, same-day batch) and VERIFIED against the frozen
June bundle p_raw before any diagnostic consumes them. No odds columns, no ROI/P&L/EV/CLV.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, "/home/user/Moneymaker")
SCRATCH = Path("/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad")
sys.path.insert(0, str(SCRATCH / "tennis-data"))
from f2_run import load_tour  # type: ignore[import-not-found]  # frozen governed loader  # noqa: E402

REPO = Path("/home/user/Moneymaker")
OUTDIR = REPO / "docs/evidence/stage2f-post-failure"
CONFLICT = "1.259522098"
FROZEN = {"ATP": (0.025399, 1.218638), "WTA": (0.029204, 1.150681)}
BANDS = [(0, 4, "1-4"), (5, 9, "5-9"), (10, 19, "10-19"), (20, 10**9, "20+")]


def clamp(p: float) -> float:
    return min(max(p, 1e-12), 1 - 1e-12)


def logit(p: float) -> float:
    p = clamp(p)
    return math.log(p / (1 - p))


def sig(z: float) -> float:
    z = max(-700.0, min(700.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def irls_slope(pairs: list[tuple[float, int]]) -> tuple[float, float, int, bool]:
    """INDEPENDENT 2-param logistic fit y ~ sigmoid(a + b*logit(p)) via IRLS with the
    weighted-least-squares working response (structurally different from the harness's
    gradient/Hessian Newton). Returns (a, b, iterations, converged)."""
    xs = [logit(p) for p, _ in pairs]
    ys = [float(y) for _, y in pairs]
    a, b = 0.0, 1.0
    for it in range(1, 201):
        sw = swx = swxx = swz = swxz = 0.0
        for x, y in zip(xs, ys):
            eta = a + b * x
            mu = sig(eta)
            w = max(mu * (1 - mu), 1e-12)
            z = eta + (y - mu) / w
            sw += w
            swx += w * x
            swxx += w * x * x
            swz += w * z
            swxz += w * x * z
        det = sw * swxx - swx * swx
        if abs(det) < 1e-13:
            return a, b, it, False
        na = (swxx * swz - swx * swxz) / det
        nb = (sw * swxz - swx * swz) / det
        if abs(na - a) + abs(nb - b) < 1e-12:
            return na, nb, it, True
        a, b = na, nb
    return a, b, 200, False


def blk_metrics(pairs: list[tuple[float, int]]) -> dict[str, Any]:
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    ll = sum(-math.log(clamp(p if y == 1 else 1 - p)) for p, y in pairs) / n
    br = sum((p - y) ** 2 for p, y in pairs) / n
    mp = sum(p for p, _ in pairs) / n
    my = sum(y for _, y in pairs) / n
    a, b, _, conv = irls_slope(pairs)
    return {"n": n, "log_loss": round(ll, 6), "brier": round(br, 6),
            "cal_in_large": round(logit(my) - logit(mp), 6),
            "cal_slope": round(b, 6), "cal_intercept": round(a, 6), "slope_converged": conv}


def reliability(pairs: list[tuple[float, int]], nbins: int = 10) -> list[dict[str, Any]]:
    srt = sorted(pairs)
    out = []
    for i in range(nbins):
        chunk = srt[i * len(srt) // nbins:(i + 1) * len(srt) // nbins]
        if chunk:
            out.append({"bin": i + 1, "n": len(chunk),
                        "mean_p": round(sum(p for p, _ in chunk) / len(chunk), 4),
                        "mean_y": round(sum(y for _, y in chunk) / len(chunk), 4)})
    return out


def fit_temperature(pairs: list[tuple[float, int]]) -> float:
    """1-param temperature-only fit y ~ sigmoid(logit(p)/T) by Newton on u=1/T."""
    xs = [logit(p) for p, _ in pairs]
    ys = [float(y) for _, y in pairs]
    u = 1.0
    for _ in range(100):
        g = h = 0.0
        for x, y in zip(xs, ys):
            m = sig(u * x)
            g += (y - m) * x
            h += m * (1 - m) * x * x
        if h < 1e-13:
            break
        du = g / h
        u += du
        if abs(du) < 1e-12:
            break
    return 1.0 / u


def week_of(d: str) -> str:
    dd = date.fromisoformat(d)
    return f"W{min((dd.day - 1) // 7 + 1, 5)}"


def main() -> None:
    bundle = [json.loads(ln) for ln in
              (REPO / "docs/evidence/stage2e-june-m1-bundle/JUNE_M1_PREDICTION_BUNDLE.jsonl")
              .read_text().splitlines() if ln.strip()]
    art = json.loads((REPO / "docs/evidence/stage2e-june-m1-artifact/RECOVERY_OUTCOME_ARTIFACT.json").read_text())
    win = {o["market_id"]: int(o["winner_selection_id"]) for o in art["outcomes"]}
    rows_all: list[dict[str, Any]] = []           # scored rows incl. conflict (for §4 only)
    for p in bundle:
        if p["market_id"] not in win:
            continue
        y = 1 if win[p["market_id"]] == int(p["selection_id_designated"]) else 0
        rows_all.append({**p, "y": y})
    rows = [r for r in rows_all if r["market_id"] != CONFLICT]
    assert len(rows_all) == 1154 and len(rows) == 1153

    # ---------------- §4 independent reproduction (frozen 1,154 membership) ----------------
    frozen = json.loads((REPO / "docs/evidence/stage2e-june-m1-artifact/STAGE_A_RESULT.json").read_text())["scorecard"]
    def cal_pairs(rs: list[dict[str, Any]]) -> list[tuple[float, int]]:
        return [(float(r["p_cal_designated"]), int(r["y"])) for r in rs]
    s4: dict[str, Any] = {"diagnostic": "INDEPENDENT_SCORECARD_REPRODUCTION_V1",
                          "tolerance": "abs diff <= 5e-6 per metric; counts exact",
                          "blocks": {}, "reliability_deciles": reliability(cal_pairs(rows_all)),
                          "coverage": {"scored": len(rows_all), "exclusions": len(art["exclusions"])}}
    ok = True
    checks = [("overall", rows_all, frozen["overall"]),
              ("ATP", [r for r in rows_all if r["tour"] == "ATP"], frozen["per_tour"]["ATP"]),
              ("WTA", [r for r in rows_all if r["tour"] == "WTA"], frozen["per_tour"]["WTA"])]
    for band_label, blockref in frozen["prior_history_cohorts"].items():
        checks.append((f"band:{band_label}",
                       [r for r in rows_all if r["prior_band"] == band_label], blockref))
    for name, rs, ref in checks:
        mine = blk_metrics(cal_pairs(rs))
        deltas = {k: round(abs(mine[k] - ref[k]), 8) for k in
                  ("log_loss", "brier", "cal_in_large", "cal_slope") if k in ref and mine["n"]}
        agree = mine["n"] == ref["n"] and all(v <= 5e-6 for v in deltas.values())
        ok &= agree
        s4["blocks"][name] = {"independent": mine, "frozen": ref, "abs_deltas": deltas,
                              "agree": agree}
    s4["scorecards_agree"] = ok
    (OUTDIR / "S4_INDEPENDENT_SCORECARD.json").write_text(json.dumps(s4, indent=1, sort_keys=True))
    print("S4 agree:", ok)
    if not ok:
        print("S4 MATERIAL DISAGREEMENT — INTEGRITY INCIDENT; STOPPING")
        return

    # ---------------- regenerate pre-June prequential raw predictions ----------------
    hist: list[dict[str, Any]] = []   # per completed pre-June match
    ratings_final: dict[str, dict[tuple[str, str], float]] = {}
    counts_final: dict[str, dict[tuple[str, str], int]] = {}
    last_seen: dict[str, dict[tuple[str, str], date]] = {}
    for tour in ("ATP", "WTA"):
        matches, _ = load_tour(tour)   # (date, key_w, key_l) completed, deduped, pre-June
        R: dict[tuple[str, str], float] = defaultdict(lambda: 1500.0)
        C: dict[tuple[str, str], int] = defaultdict(int)
        L: dict[tuple[str, str], date] = {}
        by_day: dict[date, list[tuple[tuple[str, str], tuple[str, str]]]] = defaultdict(list)
        for d, kw, kl in matches:
            by_day[d].append((kw, kl))
        for d in sorted(by_day):
            dv_map: dict[tuple[str, str], float] = defaultdict(float)
            for kw, kl in by_day[d]:
                pw = 1.0 / (1.0 + 10.0 ** ((R[kl] - R[kw]) / 400.0))
                hist.append({"tour": tour, "date": d.isoformat(), "p_w": pw,
                             "prior_min": min(C[kw], C[kl]),
                             "rest_min": min((d - L[kw]).days if kw in L else -1,
                                             (d - L[kl]).days if kl in L else -1)})
                dv_map[kw] += 24.0 * (1.0 - pw)
                dv_map[kl] -= 24.0 * (1.0 - pw)
            for k, dv in dv_map.items():
                R[k] += dv
            for kw, kl in by_day[d]:
                C[kw] += 1
                C[kl] += 1
                L[kw] = d
                L[kl] = d
        ratings_final[tour] = dict(R)
        counts_final[tour] = dict(C)
        last_seen[tour] = dict(L)

    # verify the regeneration against the FROZEN June bundle p_raw (STRICT cross-check)
    def key_of(cid: str) -> tuple[str, str]:
        body = cid.split(":", 1)[1]
        s, i = body.rsplit("|", 1)
        return (s, i)
    max_dev = 0.0
    n_checked = 0
    for p in bundle:
        t = p["tour"]
        kd, ko = key_of(p["competitor_designated"]), key_of(p["competitor_other"])
        rd = ratings_final[t].get(kd, 1500.0)
        ro = ratings_final[t].get(ko, 1500.0)
        mine = 1.0 / (1.0 + 10.0 ** ((ro - rd) / 400.0))
        max_dev = max(max_dev, abs(mine - float(p["p_raw_designated"])))
        n_checked += 1
    regen_ok = max_dev <= 5e-7
    print(f"regen check: n={n_checked} max|dp|={max_dev:.2e} ok={regen_ok}")
    if not regen_ok:
        print("REGENERATION MISMATCH — STOPPING BEFORE §5-§7")
        return

    # ---------------- §5 raw / temperature-only / affine (1,153 cohort) ----------------
    # temperature fit on mirrored pairs so both outcomes are represented
    t_only = {}
    for t in ("ATP", "WTA"):
        pairs = []
        for h in hist:
            if h["tour"] == t:
                pairs.append((h["p_w"], 1))
                pairs.append((1.0 - h["p_w"], 0))
        t_only[t] = round(fit_temperature(pairs), 6)
    variants: dict[str, Any] = {}
    for label in ("raw", "temp_only_reconstructed", "affine_frozen"):
        def pv(r: dict[str, Any]) -> float:
            praw = float(r["p_raw_designated"])
            if label == "raw":
                return praw
            if label == "temp_only_reconstructed":
                return sig(logit(praw) / t_only[r["tour"]])
            return float(r["p_cal_designated"])
        prs = [(pv(r), int(r["y"])) for r in rows]
        v: dict[str, Any] = {"overall": blk_metrics(prs), "reliability": reliability(prs)}
        for t in ("ATP", "WTA"):
            v[t] = blk_metrics([(pv(r), int(r["y"])) for r in rows if r["tour"] == t])
        v["weekly"] = {w: blk_metrics([(pv(r), int(r["y"])) for r in rows
                                       if week_of(r["cluster_day"]) == w])
                       for w in ("W1", "W2", "W3", "W4", "W5")}
        v["cohort_tier"] = {c: blk_metrics([(pv(r), int(r["y"])) for r in rows if r["cohort"] == c])
                            for c in sorted({r["cohort"] for r in rows})}
        v["prior_bands"] = {b: blk_metrics([(pv(r), int(r["y"])) for r in rows if r["prior_band"] == b])
                            for b in sorted({r["prior_band"] for r in rows})}
        variants[label] = v
    s5 = {"diagnostic": "RAW_TEMP_AFFINE_COMPARISON_V1",
          "temp_only_reconstruction": {"params_T": t_only,
                                       "fit_set": "regenerated pre-June prequential (mirrored pairs)",
                                       "label": "RECONSTRUCTED — no frozen temp-only vintage exists"},
          "variants": variants}
    (OUTDIR / "S5_RAW_TEMP_AFFINE.json").write_text(json.dumps(s5, indent=1, sort_keys=True))
    print("S5:", {k: v["overall"]["log_loss"] for k, v in variants.items()},
          {k: v["overall"]["cal_slope"] for k, v in variants.items()}, "T:", t_only)

    # ---------------- §7 oracle affine on June (1,153) — NON-DEPLOYABLE ----------------
    def fit_affine(pairs: list[tuple[float, int]]) -> tuple[float, float]:
        a, b, _, _ = irls_slope(pairs)          # y ~ sigmoid(a + b*logit(p)); T = 1/b
        return a, 1.0 / b
    oracle: dict[str, Any] = {"label": "JUNE_ORACLE_CALIBRATION — NON-DEPLOYABLE"}
    for t in ("ATP", "WTA"):
        prs = [(float(r["p_raw_designated"]), int(r["y"])) for r in rows if r["tour"] == t]
        a, T = fit_affine(prs)
        cal = [(sig(a + logit(p) / T), y) for p, y in prs]
        fa, fT = FROZEN[t]
        oracle[t] = {"oracle_intercept": round(a, 6), "oracle_temperature": round(T, 6),
                     "frozen_intercept": fa, "frozen_temperature": fT,
                     "delta_intercept": round(a - fa, 6), "delta_temperature": round(T - fT, 6),
                     "implied_logit_shrinkage_vs_frozen": round(fT / T, 6),
                     "in_sample_after_oracle": blk_metrics(cal)}
    slopes_fixed = {t: blk_metrics([(float(r["p_cal_designated"]), int(r["y"]))
                                    for r in rows if r["tour"] == t])["cal_slope"]
                    for t in ("ATP", "WTA")}
    oracle["frozen_affine_june_slopes"] = slopes_fixed
    oracle["recalibration_alone_note"] = (
        "compare in_sample_after_oracle (slope=1 by construction) log_loss/brier against the "
        "affine_frozen variant in S5 to judge how much of the failure recalibration would repair")
    (OUTDIR / "S7_JUNE_ORACLE_CALIBRATION.json").write_text(json.dumps(oracle, indent=1, sort_keys=True))
    print("S7 oracle:", {t: (oracle[t]["oracle_intercept"], oracle[t]["oracle_temperature"]) for t in ("ATP", "WTA")})

    # ---------------- §6 distribution-shift audit ----------------
    val_lo, val_hi = date(2025, 6, 1), date(2026, 5, 31)
    pre = [h for h in hist if val_lo <= date.fromisoformat(h["date"]) <= val_hi]
    def smd(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return float("nan")
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        va = sum((x - ma) ** 2 for x in a) / max(len(a) - 1, 1)
        vb = sum((x - mb) ** 2 for x in b) / max(len(b) - 1, 1)
        sp = math.sqrt((va + vb) / 2) or 1e-12
        return round((mb - ma) / sp, 4)
    june_prior = []
    june_rest = []
    for r in rows:
        t = r["tour"]
        kd, ko = key_of(r["competitor_designated"]), key_of(r["competitor_other"])
        june_prior.append(float(min(counts_final[t].get(kd, 0), counts_final[t].get(ko, 0))))
        d = date.fromisoformat(r["cluster_day"])
        rd = (d - last_seen[t][kd]).days if kd in last_seen[t] else -1
        ro = (d - last_seen[t][ko]).days if ko in last_seen[t] else -1
        june_rest.append(float(min(rd, ro)))
    def fav(p: float) -> float:
        return max(p, 1 - p)
    s6 = {
        "diagnostic": "DISTRIBUTION_SHIFT_AUDIT_V1",
        "pre_cohort": f"regenerated prequential validation window {val_lo}..{val_hi} (n={len(pre)})",
        "june_cohort": f"diagnostic cohort n={len(rows)}",
        "labels": "retrospective diagnostics; ranking fields unavailable in either cohort's lawful "
                  "feature set and are omitted; surface/tournament/round/level/best-of exist only "
                  "for the 379 TD-matched June markets and the pre-June TD rows",
        "smd": {
            "wta_share": smd([1.0 if h["tour"] == "WTA" else 0.0 for h in pre],
                             [1.0 if r["tour"] == "WTA" else 0.0 for r in rows]),
            "favourite_p_raw": smd([fav(h["p_w"]) for h in pre],
                                   [fav(float(r["p_raw_designated"])) for r in rows]),
            "abs_logit_rating_diff": smd([abs(logit(h["p_w"])) for h in pre],
                                         [abs(logit(float(r["p_raw_designated"]))) for r in rows]),
            "min_prior_matches": smd([float(h["prior_min"]) for h in pre], june_prior),
            "min_rest_days_capped60": smd([float(min(h["rest_min"], 60)) for h in pre if h["rest_min"] >= 0],
                                          [min(x, 60.0) for x in june_rest if x >= 0]),
        },
        "june_only_composition": {
            "cohort_tier": {c: sum(1 for r in rows if r["cohort"] == c)
                            for c in sorted({r["cohort"] for r in rows})},
            "prior_bands": {b: sum(1 for r in rows if r["prior_band"] == b)
                            for b in sorted({r["prior_band"] for r in rows})},
            "cold_start_share_prior0": round(sum(1 for x in june_prior if x == 0) / len(rows), 4),
        },
        "pre_only_composition": {
            "prior_min_median": sorted(h["prior_min"] for h in pre)[len(pre) // 2],
            "june_prior_min_median": sorted(june_prior)[len(june_prior) // 2],
        },
    }
    (OUTDIR / "S6_DISTRIBUTION_SHIFT.json").write_text(json.dumps(s6, indent=1, sort_keys=True))
    print("S6 smd:", s6["smd"])
    # cache regen history for §8/§9 (scratchpad; digest recorded)
    cache = SCRATCH / "stage2f_hist.jsonl"
    body = "\n".join(json.dumps(h, sort_keys=True) for h in hist)
    cache.write_text(body)
    print("hist cached:", len(hist), "sha256:" + hashlib.sha256(body.encode()).hexdigest()[:16])


if __name__ == "__main__":
    main()
