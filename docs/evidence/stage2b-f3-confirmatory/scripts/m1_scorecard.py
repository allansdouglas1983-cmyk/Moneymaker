"""M1 calibrated scorecard for the SELECTED model (Stage 2B §5 + §2 bands).

F3 FAILED (FAIL_HARM) => F2 global Elo is the selected family. Applies the registered
one-parameter temperature scaling per outer fold (fitted strictly on data < Y), producing
honest calibrated outer-fold predictions, and evaluates every frozen M1 band.

Predictions framed on the LOWER-id runner (p_lo, y_lo) so calibration sees BOTH classes.
Uses f3_confirmatory.load + the same per-fold selected K. No June, no odds, no returns.
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, "/home/user/Moneymaker")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f3_confirmatory as C
from sport_tennis.elo_family import ELO_INITIAL_RATING as R0
from sport_tennis.elo_family import elo_win_probability

LN2 = math.log(2.0)
VAL_LO = date(2025, 6, 1)
BANDS = C.BANDS
MODEL = sys.argv[1] if len(sys.argv) > 1 else "f2"


def prequential_lo(rows, kg, ks, clo, chi):
    """Like C.prequential but yields (date, p_lo_f2, p_lo_f3, y_lo, band) for lower-id runner."""
    g, s, appear = {}, {}, defaultdict(int)
    out = []
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["date"]].append(r)
    for d in sorted(by_day):
        dg, ds, seed = defaultdict(float), defaultdict(float), {}
        day = sorted(by_day[d], key=lambda r: (r["lo"], r["hi"]))
        for r in day:
            lo, hi, code = r["lo"], r["hi"], r["code"]
            p2 = elo_win_probability(g.get(lo, R0), g.get(hi, R0))
            if code != 0:
                for c_ in (lo, hi):
                    if (c_, code) not in s and (c_, code) not in seed:
                        seed[(c_, code)] = g.get(c_, R0)
                rl = s.get((lo, code), seed.get((lo, code)))
                rh = s.get((hi, code), seed.get((hi, code)))
                p3 = elo_win_probability(rl, rh)
            else:
                p3 = p2
            if clo <= d < chi:
                ylo = 1.0 if r["winner"] == lo else 0.0
                m = min(appear[lo], appear[hi])
                band = next(lb for a0, b0, lb in BANDS if a0 <= m <= b0)
                out.append((d, p2, p3, ylo, band))
            sa = 1.0 if r["winner"] == lo else 0.0
            dg[lo] += kg * (sa - p2); dg[hi] += kg * ((1 - sa) - (1 - p2))
            if code != 0:
                ds[(lo, code)] += ks * (sa - p3); ds[(hi, code)] += ks * ((1 - sa) - (1 - p3))
        for c_, dv in dg.items():
            g[c_] = g.get(c_, R0) + dv
        for key, base in seed.items():
            s.setdefault(key, base)
        for key, dv in ds.items():
            s[key] = s.get(key, R0) + dv
        for r in day:
            appear[r["lo"]] += 1; appear[r["hi"]] += 1
    return out


def clamp(p):
    return min(max(p, 1e-12), 1 - 1e-12)


def fit_temperature(pairs):
    """T>0 minimising log loss of sigma(logit(p)/T) vs y. Newton on u=1/T."""
    xs = [(math.log(clamp(p) / (1 - clamp(p))), y) for p, y in pairs]
    u = 1.0
    for _ in range(80):
        g = h = 0.0
        for lg, y in xs:
            pp = 1 / (1 + math.exp(-lg * u))
            g += (pp - y) * lg
            h += pp * (1 - pp) * lg * lg
        if h < 1e-12:
            break
        step = g / h
        u = max(1e-6, u - step)
        if abs(step) < 1e-12:
            break
    return 1.0 / u


def apply_T(p, T):
    lg = math.log(clamp(p) / (1 - clamp(p)))
    return 1 / (1 + math.exp(-lg / T))


def metrics(pairs):  # (p_lo_cal, y_lo)
    n = len(pairs)
    ll = sum(-math.log(clamp(p if y == 1 else 1 - p)) for p, y in pairs) / n
    brier = sum((p - y) ** 2 for p, y in pairs) / n
    mp = sum(p for p, _ in pairs) / n
    my = sum(y for _, y in pairs) / n
    lg = lambda x: math.log(clamp(x) / (1 - clamp(x)))  # noqa
    cil = lg(my) - lg(mp)
    # slope
    a, b = 0.0, 1.0
    xs = [lg(p) for p, _ in pairs]
    ys = [y for _, y in pairs]
    for _ in range(60):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in zip(xs, ys):
            mm = 1 / (1 + math.exp(-(a + b * x)))
            ga += y - mm; gb += (y - mm) * x; w = mm * (1 - mm)
            haa += w; hab += w * x; hbb += w * x * x
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        da = (hbb * ga - hab * gb) / det; db = (haa * gb - hab * ga) / det
        a += da; b += db
        if abs(da) + abs(db) < 1e-11:
            break
    return {"n": n, "log_loss": round(ll, 5), "brier": round(brier, 5),
            "cal_in_large": round(cil, 5), "cal_slope": round(b, 4)}


def main():
    fold_K = json.load(open("F3_CONFIRMATORY_REPORT.json"))["selected_k_by_fold"]
    cal = []   # (tour, year, p_lo_cal, y_lo, band, is_val)
    temps = defaultdict(dict)
    for tour in ("ATP", "WTA"):
        rows, _ = C.load(tour)
        for y in range(2019, 2027):
            if str(y) not in fold_K[tour]:
                continue
            kg = fold_K[tour][str(y)]["k_global"]; ks = fold_K[tour][str(y)]["k_surface"]
            inr = prequential_lo([r for r in rows if r["date"] < date(y, 1, 1)], kg, ks,
                                 date(max(2000, y - 2), 1, 1), date(y, 1, 1))
            jj = 1 if MODEL == "f2" else 2
            T = fit_temperature([(p[jj], p[3]) for p in inr]) if inr else 1.0
            temps[tour][str(y)] = round(T, 4)
            preds = prequential_lo(rows, kg, ks, date(y, 1, 1), min(date(y + 1, 1, 1), date(2026, 6, 1)))
            for d, p2, p3, ylo, band in preds:
                pc = apply_T(p2 if MODEL == "f2" else p3, T)
                cal.append((tour, y, pc, ylo, band, d >= VAL_LO))
        print(f"[{tour}] temperatures {temps[tour]}", flush=True)

    rep = {"selected_model": MODEL, "temperatures_by_fold": {t: dict(v) for t, v in temps.items()},
           "coverage": {"scored": len(cal), "eligible_confirmatory": 34038,
                        "coverage_rate": round(len(cal) / 34038, 4)}}
    rep["overall"] = metrics([(p, y) for _t, _y, p, y, _b, _v in cal])
    rep["per_tour"] = {t: metrics([(p, y) for tt, _y, p, y, _b, _v in cal if tt == t]) for t in ("ATP", "WTA")}
    rep["temporal"] = {
        "oof": metrics([(p, y) for _t, _y, p, y, _b, v in cal if not v]),
        "validation": metrics([(p, y) for _t, _y, p, y, _b, v in cal if v])}
    rep["temporal"]["val_minus_oof_logloss"] = round(
        rep["temporal"]["validation"]["log_loss"] - rep["temporal"]["oof"]["log_loss"], 5)
    yr = defaultdict(list)
    for _t, y, p, ylo, _b, _v in cal:
        yr[y].append((p, ylo))
    rep["yearly"] = {str(y): {"n": len(v), "log_loss": metrics(v)["log_loss"]} for y, v in sorted(yr.items())}
    cb = defaultdict(list)
    for _t, _y, p, ylo, b, _v in cal:
        cb[b].append((p, ylo))
    rep["cold_start"] = {b: {"n": len(v), "log_loss": metrics(v)["log_loss"]} for b, v in sorted(cb.items())}
    # reliability: adaptive deciles by p_lo_cal
    srt = sorted(cal, key=lambda x: x[2])
    rel = []
    q = len(srt) // 10
    for i in range(10):
        chunk = srt[i * q:(i + 1) * q] if i < 9 else srt[i * q:]
        if not chunk:
            continue
        mp = sum(x[2] for x in chunk) / len(chunk)
        my = sum(x[3] for x in chunk) / len(chunk)
        rel.append({"n": len(chunk), "mean_p": round(mp, 4), "obs": round(my, 4), "abs_gap": round(abs(my - mp), 4)})
    rep["reliability_deciles"] = rel
    json.dump(rep, open("M1_SCORECARD.json", "w"), indent=1, sort_keys=True, default=str)
    print(json.dumps({"overall": rep["overall"], "temporal": rep["temporal"],
                      "max_reliability_gap": max(r["abs_gap"] for r in rel)}, indent=1))


if __name__ == "__main__":
    main()
