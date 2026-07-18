"""Stage 2C §3/§4 — AFFINE_LOGIT_CALIBRATION_V2 nested fold-safe remediation scorecard.

REMEDIATION / DEVELOPMENT EVIDENCE (registered AFTER observing the temperature-only
calibration-in-the-large shortfall of +0.02328). Does NOT close M1. Does NOT touch June.
Does NOT overwrite the temperature-only diagnostic vintage (stage2b-f3-confirmatory/
M1_SCORECARD.json remains as recorded).

Calibration map (one intercept + one temperature; temperature > 0):
    z        = logit(p_raw)
    z_cal    = intercept + z / temperature
    p_cal    = sigmoid(z_cal)

Fold-safe procedure, per outer fold Y (per tour — ATP and WTA fitted separately because
the frozen F2 policy runs the two tours as fully independent models,
f2-global-elo-registration-v1.yaml `atp_wta_separation`):
  1. inner OOF F2 predictions from outer-training only (data strictly < Y),
  2. fit (intercept, temperature) on those inner OOF preds + outcomes,
  3. refit F2 on the full outer-training (prequential ratings through Y-1),
  4. apply the fitted calibration to the outer-eval matches (year Y),
  5. stamp per-fold provenance (intercept, temperature, trained_through).

Final pre-June parameters: fit ONE (intercept, temperature) per tour on ALL governed
pre-June OOF (2019-01-01..2026-05-31 outer-eval preds), reported for June freezing.
Raw and calibrated predictions kept strictly separate. No odds, no June, no returns.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, "/home/user/Moneymaker")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f3_confirmatory as C
from m1_scorecard import prequential_lo  # identical fold-safe forward pass (lower-id frame)

LN2 = math.log(2.0)
VAL_LO = date(2025, 6, 1)
BANDS = C.BANDS
ROOT = os.path.dirname(os.path.abspath(__file__))


def clamp(p: float) -> float:
    return min(max(p, 1e-12), 1 - 1e-12)


def logit(p: float) -> float:
    p = clamp(p)
    return math.log(p / (1 - p))


def fit_affine(pairs):
    """MLE (intercept a, slope u=1/T) of y ~ sigmoid(a + u*logit(p)); returns (a, T).

    2-D Newton on the logistic log-likelihood. temperature = 1/u (u constrained > 0 so
    temperature stays finite and positive; a degenerate non-positive slope is refused)."""
    xs = [logit(p) for p, _ in pairs]
    ys = [y for _, y in pairs]
    a, u = 0.0, 1.0
    for _ in range(100):
        ga = gu = haa = hau = huu = 0.0
        for x, y in zip(xs, ys):
            m = 1 / (1 + math.exp(-(a + u * x)))
            ga += y - m
            gu += (y - m) * x
            w = m * (1 - m)
            haa += w
            hau += w * x
            huu += w * x * x
        det = haa * huu - hau * hau
        if abs(det) < 1e-14:
            break
        da = (huu * ga - hau * gu) / det
        du = (haa * gu - hau * ga) / det
        a += da
        u += du
        if abs(da) + abs(du) < 1e-12:
            break
    if u <= 1e-9:
        raise ValueError(f"affine calibration produced non-positive slope u={u}; refused")
    return a, 1.0 / u


def apply_affine(p: float, a: float, T: float) -> float:
    z = logit(p)
    zc = a + z / T
    return 1 / (1 + math.exp(-zc))


def metrics(pairs):  # (p_cal, y)
    n = len(pairs)
    ll = sum(-math.log(clamp(p if y == 1 else 1 - p)) for p, y in pairs) / n
    brier = sum((p - y) ** 2 for p, y in pairs) / n
    mp = sum(p for p, _ in pairs) / n
    my = sum(y for _, y in pairs) / n
    cil = logit(my) - logit(mp)
    a, b = 0.0, 1.0
    xs = [logit(p) for p, _ in pairs]
    ys = [y for _, y in pairs]
    for _ in range(60):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in zip(xs, ys):
            mm = 1 / (1 + math.exp(-(a + b * x)))
            ga += y - mm
            gb += (y - mm) * x
            w = mm * (1 - mm)
            haa += w
            hab += w * x
            hbb += w * x * x
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a += da
        b += db
        if abs(da) + abs(db) < 1e-11:
            break
    return {"n": n, "log_loss": round(ll, 5), "brier": round(brier, 5),
            "cal_in_large": round(cil, 5), "cal_slope": round(b, 4)}


def main() -> None:
    fold_K = json.load(open(os.path.join(ROOT, "F3_CONFIRMATORY_REPORT.json")))["selected_k_by_fold"]
    cal = []                         # (tour, year, p_cal, y, band, is_val)
    raw_rows = []                    # (tour, p_raw, y) pooled pre-June OOF for final fit
    params = defaultdict(dict)       # per-fold {intercept, temperature}
    for tour in ("ATP", "WTA"):
        rows, _ = C.load(tour)
        for y in range(2019, 2027):
            if str(y) not in fold_K[tour]:
                continue
            kg = fold_K[tour][str(y)]["k_global"]
            ks = fold_K[tour][str(y)]["k_surface"]
            # (1) inner OOF preds from outer-training only (data < Y)
            inr = prequential_lo([r for r in rows if r["date"] < date(y, 1, 1)], kg, ks,
                                 date(max(2000, y - 2), 1, 1), date(y, 1, 1))
            # (2) fit (intercept, temperature) on inner OOF
            a, T = fit_affine([(p[1], p[3]) for p in inr]) if inr else (0.0, 1.0)
            params[tour][str(y)] = {"intercept": round(a, 5), "temperature": round(T, 5)}
            # (3)+(4) refit F2 on full outer-training, apply calib to outer-eval year Y
            preds = prequential_lo(rows, kg, ks, date(y, 1, 1),
                                   min(date(y + 1, 1, 1), date(2026, 6, 1)))
            for d, p2, _p3, ylo, band in preds:
                cal.append((tour, y, apply_affine(p2, a, T), ylo, band, d >= VAL_LO))
                raw_rows.append((tour, p2, ylo))
        print(f"[{tour}] per-fold affine params {dict(params[tour])}", flush=True)

    # Final pre-June parameters: ONE (intercept, temperature) per tour on ALL pre-June OOF.
    final_params = {}
    for tour in ("ATP", "WTA"):
        a, T = fit_affine([(p, y) for t, p, y in raw_rows if t == tour])
        final_params[tour] = {"intercept": round(a, 6), "temperature": round(T, 6),
                              "n_oof_fit": sum(1 for t, _p, _y in raw_rows if t == tour)}

    rep = {
        "artefact": "AFFINE_LOGIT_CALIBRATION_V2 pre-June remediation scorecard",
        "evidence_label": "REMEDIATION / DEVELOPMENT EVIDENCE — does NOT close M1; "
                          "June is the external transfer check (Stage 2C §4).",
        "calibration_policy": "calibration-policy-v2 (affine logit: z_cal = intercept + z/temperature)",
        "selected_model": "F2 global Elo (EXP-STAGE2-F2-GLOBAL-ELO-001)",
        "atp_wta_params_separate_because": "frozen F2 policy runs ATP and WTA as fully "
            "independent models (f2-global-elo-registration-v1.yaml atp_wta_separation)",
        "per_fold_params": {t: dict(v) for t, v in params.items()},
        "final_pre_june_params_for_june_freeze": final_params,
        "coverage": {"scored": len(cal), "eligible_confirmatory": 34038,
                     "coverage_rate": round(len(cal) / 34038, 4)},
    }
    rep["overall"] = metrics([(p, y) for _t, _y, p, y, _b, _v in cal])
    rep["per_tour"] = {t: metrics([(p, y) for tt, _y, p, y, _b, _v in cal if tt == t])
                       for t in ("ATP", "WTA")}
    rep["temporal"] = {
        "oof": metrics([(p, y) for _t, _y, p, y, _b, v in cal if not v]),
        "validation": metrics([(p, y) for _t, _y, p, y, _b, v in cal if v])}
    rep["temporal"]["val_minus_oof_logloss"] = round(
        rep["temporal"]["validation"]["log_loss"] - rep["temporal"]["oof"]["log_loss"], 5)
    yr = defaultdict(list)
    for _t, y, p, ylo, _b, _v in cal:
        yr[y].append((p, ylo))
    rep["yearly"] = {str(y): {"n": len(v), "log_loss": metrics(v)["log_loss"]}
                     for y, v in sorted(yr.items())}
    cb = defaultdict(list)
    for _t, _y, p, ylo, b, _v in cal:
        cb[b].append((p, ylo))
    rep["cold_start"] = {b: {"n": len(v), "log_loss": metrics(v)["log_loss"]}
                         for b, v in sorted(cb.items())}
    srt = sorted(cal, key=lambda x: x[2])
    rel = []
    q = len(srt) // 10
    for i in range(10):
        chunk = srt[i * q:(i + 1) * q] if i < 9 else srt[i * q:]
        if not chunk:
            continue
        mp = sum(x[2] for x in chunk) / len(chunk)
        my = sum(x[3] for x in chunk) / len(chunk)
        rel.append({"n": len(chunk), "mean_p": round(mp, 4), "obs": round(my, 4),
                    "abs_gap": round(abs(my - mp), 4)})
    rep["reliability_deciles"] = rel
    blob = json.dumps(rep, indent=1, sort_keys=True, default=str)
    path = os.path.join(ROOT, "AFFINE_REMEDIATION_SCORECARD.json")
    with open(path, "w") as fh:
        fh.write(blob)
    digest = "sha256:" + hashlib.sha256(blob.encode()).hexdigest()  # over the file bytes
    print(json.dumps({"overall": rep["overall"], "temporal": rep["temporal"],
                      "final_pre_june_params": final_params,
                      "max_reliability_gap": max(r["abs_gap"] for r in rel),
                      "digest": digest}, indent=1))


if __name__ == "__main__":
    main()
