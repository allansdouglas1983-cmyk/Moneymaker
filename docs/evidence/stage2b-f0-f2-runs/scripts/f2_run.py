"""F2 global Elo — registered run (EXP-STAGE2-F2-GLOBAL-ELO-001, Design B).

Warm-up+OOF through the model-independent cross_fit orchestrator (per tour, per K in
the predeclared grid {16,24,32}); K selected on OOF-window mean log loss (dev only);
validation 2025-06-01..2026-05-31 evaluated PREQUENTIALLY with the selected K.
Label-policy-v1 completed-only; identities via td-norm-v1 keys; no odds columns are
ever read into this pipeline (Winner/Loser/Date/Comment/tour only). No row on/after
2026-06-01. Deterministic throughout.
"""
from __future__ import annotations

import json
import math
import os
import sys
from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, "/home/user/Moneymaker")
import openpyxl
import xlrd

from l4_pricing.crossfit import cross_fit
from sport_core.clustering import ChronologyKey
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow
from sport_tennis.elo_family import ELO_INITIAL_RATING, GlobalEloFamily, elo_win_probability
from sport_tennis.identity_bridge import _td_key, normalize_name  # governed normalizer
from sport_core.clustering import calendar_day_assignment

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "raw", "vintage-2026-07-18")
BOUNDARY = date(2026, 6, 1)
OOF_LO, OOF_HI = date(2019, 1, 1), date(2025, 5, 31)
VAL_LO, VAL_HI = date(2025, 6, 1), date(2026, 5, 31)
K_GRID = [16.0, 24.0, 32.0]
SCHEMA = FeatureSchema(names=("unit",))
H = HorizonLabel("T-5m")
_F = {"unit": Decimal(1)}
BANDS = [(0, 0, "0"), (1, 4, "1-4"), (5, 9, "5-9"), (10, 19, "10-19"), (20, 10**9, "20+")]


def iter_rows(path):
    if path.endswith(".xlsx"):
        wb = openpyxl.load_workbook(path, read_only=True)
        rows = wb.active.iter_rows(values_only=True)
        hdr = [str(c) for c in next(rows)]
        for r in rows:
            yield hdr, r
    else:
        wb = xlrd.open_workbook(path)
        ws = wb.sheet_by_index(0)
        hdr = [str(c.value) for c in ws.row(0)]
        for i in range(1, ws.nrows):
            vals = []
            for c in ws.row(i):
                if c.ctype == xlrd.XL_CELL_DATE:
                    vals.append(datetime(*xlrd.xldate_as_tuple(c.value, wb.datemode)))
                elif c.ctype == xlrd.XL_CELL_EMPTY:
                    vals.append(None)
                else:
                    vals.append(c.value)
            yield hdr, tuple(vals)


def parse_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        for f in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(v.strip(), f).date()
            except ValueError:
                pass
    return None


def load_tour(tour: str):
    """(matches, exclusions) — matches: (date, key_w, key_l); label-policy-v1."""
    excl = defaultdict(int)
    rows = []
    for fn in sorted(os.listdir(RAW)):
        if not fn.startswith(tour.lower()):
            continue
        for hdr, row in iter_rows(os.path.join(RAW, fn)):
            cols = {h: (row[i] if i < len(row) else None) for i, h in enumerate(hdr)}
            d = parse_date(cols.get("Date"))
            if d is None:
                excl["unparseable_date"] += 1
                continue
            if d >= BOUNDARY:
                excl["on_or_after_2026_06_01"] += 1
                continue
            cm = str(cols.get("Comment") or "Completed").strip().lower()
            if not cm.startswith("completed"):
                excl[f"label_excluded_{cm.split()[0] if cm else 'blank'}"] += 1
                continue
            w, l = cols.get("Winner"), cols.get("Loser")
            if not w or not l:
                excl["missing_winner_or_loser"] += 1
                continue
            kw = _td_key(normalize_name(str(w)))
            kl = _td_key(normalize_name(str(l)))
            if kw is None or kl is None:
                excl["malformed_identity"] += 1
                continue
            if kw == kl:
                excl["self_match_defect"] += 1
                continue
            rows.append((d, kw, kl))
    # duplicate/conflict policy (frozen): pair-day dedupe, conflicting winners excluded
    seen = {}
    dedup = []
    conflicts = set()
    for d, kw, kl in rows:
        key = (d, tuple(sorted((kw, kl))))
        if key in seen:
            if seen[key] != kw:
                conflicts.add(key)
            excl["duplicate_pair_day"] += 1
            continue
        seen[key] = kw
        dedup.append((d, kw, kl))
    if conflicts:
        dedup = [(d, kw, kl) for d, kw, kl in dedup if (d, tuple(sorted((kw, kl)))) not in conflicts]
        excl["conflicting_winner_excluded"] += len(conflicts)
    return dedup, dict(excl)


def build_races(matches, tour: str):
    ids = {}
    def cid(key):
        if key not in ids:
            ids[key] = len(ids) + 1
        return ids[key]
    # deterministic: assign ids over sorted keys first
    for key in sorted({k for _, kw, kl in matches for k in (kw, kl)}):
        cid(key)
    races = []
    occ = defaultdict(int)
    for d, kw, kl in sorted(matches, key=lambda m: (m[0], tuple(sorted((m[1], m[2]))))):
        a, b = cid(kw), cid(kl)
        okey = (d, min(a, b), max(a, b))
        occ[okey] += 1
        rid = f"td:{tour}:{d.isoformat()}:{min(a,b)}v{max(a,b)}:{occ[okey]}"
        races.append(
            (d, Race(
                race_id=rid,
                cluster=calendar_day_assignment("tennis", d),
                runners=(RunnerRow(runner_id=a, features=_F), RunnerRow(runner_id=b, features=_F)),
                winner_id=cid(kw),
            ))
        )
    return races, ids


def metrics(pairs):
    """pairs: list of (p_winner, p_first, y_first, date, cold_band). Returns metric dict."""
    n = len(pairs)
    ll = sum(-math.log(p) for p, *_ in pairs) / n
    brier = sum((pf - y) ** 2 for _, pf, y, *_ in pairs) / n
    cal_large = sum(pf for _, pf, *_ in pairs) / n - sum(y for _, _, y, *_ in pairs) / n
    # calibration slope: 1-D logistic y ~ a + b*logit(p), Newton
    a, b = 0.0, 1.0
    xs = [math.log(pf / (1 - pf)) for _, pf, _, *_ in pairs]
    ys = [y for _, _, y, *_ in pairs]
    for _ in range(25):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in zip(xs, ys):
            m = 1 / (1 + math.exp(-(a + b * x)))
            ga += y - m
            gb += (y - m) * x
            w = m * (1 - m)
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
        if abs(da) + abs(db) < 1e-10:
            break
    bands = defaultdict(lambda: [0, 0.0, 0])
    for _, pf, y, *_ in pairs:
        i = min(9, int(pf * 10))
        bands[i][0] += 1
        bands[i][1] += pf
        bands[i][2] += y
    reliability = {
        f"[{i/10:.1f},{(i+1)/10:.1f})": {"n": c, "mean_p": round(sp / c, 4), "obs_rate": round(sy / c, 4)}
        for i, (c, sp, sy) in sorted(bands.items()) if c
    }
    return {"n": n, "log_loss": round(ll, 5), "brier": round(brier, 5),
            "cal_in_large": round(cal_large, 5), "cal_slope": round(b, 4), "reliability": reliability}


def main() -> None:
    out = {}
    for tour in ("ATP", "WTA"):
        matches, excl = load_tour(tour)
        races_dated, _ids = build_races(matches, tour)
        date_by_rid = {r.race_id: d for d, r in races_dated}
        dev_races = [r for d, r in races_dated if d <= OOF_HI]
        # prior-count index per competitor (completed matches before date)
        appear = defaultdict(list)
        for d, r in races_dated:
            for rr in r.runners:
                appear[rr.runner_id].append(d)
        for v in appear.values():
            v.sort()
        def cold_band(r, d):
            m = min(bisect_left(appear[rr.runner_id], d) for rr in r.runners)
            for lo, hi, lab in BANDS:
                if lo <= m <= hi:
                    return lab
            return "20+"
        races_by_id = {r.race_id: r for _, r in races_dated}
        k_results = {}
        for k in K_GRID:
            res = cross_fit(dev_races, SCHEMA, horizon=H, family=GlobalEloFamily(k_factor=k),
                            score_only_after=ChronologyKey.from_date(date(2018, 12, 31)))
            pairs = []
            by_year = defaultdict(list)
            for row in res.oof:
                d = date_by_rid[row.race_id]
                if not (OOF_LO <= d <= OOF_HI):
                    continue
                race = races_by_id[row.race_id]
                if row.runner_id != race.winner_id:
                    continue
                first_id = min(rr.runner_id for rr in race.runners)
                p_first = row.p_fundamental if race.winner_id == first_id else 1 - row.p_fundamental
                y_first = 1.0 if race.winner_id == first_id else 0.0
                pairs.append((row.p_fundamental, p_first, y_first, d, cold_band(race, d)))
                by_year[d.year].append(-math.log(row.p_fundamental))
            k_results[k] = {
                "oof": metrics(pairs),
                "by_year_logloss": {y: round(sum(v) / len(v), 5) for y, v in sorted(by_year.items())},
                "pairs": pairs,
                "excluded_by_orchestrator": len(res.excluded),
                "deployment_ratings": res.deployment_model.ratings,  # type: ignore[attr-defined]
            }
        best_k = min(K_GRID, key=lambda k: (k_results[k]["oof"]["log_loss"], k))
        # validation: prequential from deployment ratings at best K
        ratings = dict(k_results[best_k]["deployment_ratings"])
        val = [(d, r) for d, r in races_dated if VAL_LO <= d <= VAL_HI]
        by_day = defaultdict(list)
        for d, r in val:
            by_day[d].append(r)
        vpairs = []
        for d in sorted(by_day):
            deltas = defaultdict(float)
            for r in sorted(by_day[d], key=lambda x: x.race_id):
                a, b_ = sorted(rr.runner_id for rr in r.runners)
                pa = elo_win_probability(ratings.get(a, ELO_INITIAL_RATING), ratings.get(b_, ELO_INITIAL_RATING))
                p_first = pa
                y_first = 1.0 if r.winner_id == a else 0.0
                p_win = pa if r.winner_id == a else 1 - pa
                vpairs.append((p_win, p_first, y_first, d, cold_band(r, d)))
                sa = 1.0 if r.winner_id == a else 0.0
                deltas[a] += best_k * (sa - pa)
                deltas[b_] += best_k * ((1 - sa) - (1 - pa))
            for rid_, dv in deltas.items():
                ratings[rid_] = ratings.get(rid_, ELO_INITIAL_RATING) + dv
        # cohorts
        def cohort(pairs, keyfn):
            groups = defaultdict(list)
            for t in pairs:
                groups[keyfn(t)].append(t)
            return {k: metrics(v) for k, v in sorted(groups.items()) if len(v) >= 25}
        sel = k_results[best_k]
        out[tour] = {
            "exclusion_funnel_rows": excl,
            "universe": {"races_dev": len(dev_races), "oof_scored": sel["oof"]["n"],
                         "orchestrator_exclusions": sel["excluded_by_orchestrator"],
                         "validation_scored": len(vpairs)},
            "k_selection": {str(k): {"oof_logloss": k_results[k]["oof"]["log_loss"],
                                     "by_year": k_results[k]["by_year_logloss"]} for k in K_GRID},
            "selected_k": best_k,
            "oof_metrics": sel["oof"],
            "oof_cold_start_cohorts": cohort(sel["pairs"], lambda t: t[4]),
            "oof_period_cohorts": cohort(sel["pairs"], lambda t: str(t[3].year)),
            "validation_metrics": metrics(vpairs),
            "validation_cold_start_cohorts": cohort(vpairs, lambda t: t[4]),
        }
        print(f"[{tour}] dev={len(dev_races)} oof_scored={sel['oof']['n']} val={len(vpairs)} "
              f"K*={best_k} oof_ll={sel['oof']['log_loss']} val_ll={out[tour]['validation_metrics']['log_loss']}",
              flush=True)
    for tour in out:
        for k in list(out[tour].get("k_selection", {})):
            pass
    # strip non-serializable
    json.dump(out, open(os.path.join(ROOT, "F2_EVALUATION_REPORT.json"), "w"), indent=1, sort_keys=True, default=str)
    print("wrote F2_EVALUATION_REPORT.json")


if __name__ == "__main__":
    main()
