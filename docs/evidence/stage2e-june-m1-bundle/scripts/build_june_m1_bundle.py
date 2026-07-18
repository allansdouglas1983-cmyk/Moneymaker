"""OUTCOME-BLIND frozen June M1 prediction bundle (Stage 2E).

For each of the 1,213 governed calibrated-F2-valid June singles markets (reason==ELIGIBLE_F2
in the frozen June M1 transfer manifest), freeze everything needed to score M1 LATER, with
NO outcome.

CONTAMINATION DISCIPLINE (binding, .claude/rules/stage2-evidence-discipline.md):
  * June sporting OUTCOMES are NEVER read. From June Betfair streams this script reads ONLY
    runner `id` + `name` and takes them ONLY from the FIRST pre-off marketDefinition whose
    status=="OPEN". It never reads/parses/branches-on/records runner status WINNER/LOSER,
    status=="CLOSED" market definitions, settledTime, or any settlement/result field.
  * Ratings use ONLY Tennis-Data pre-June completed rows (Date < 2026-06-01): Winner/Loser/
    Date/Comment columns; NO odds columns; the winner IDENTITY drives the Elo update, never a
    June result.

Rating model: F2 per-tour global Elo (sport_tennis.elo_family), same-day BATCH update at the
frozen 2026-fold selected k_global per tour (F3_CONFIRMATORY_REPORT.json). Cold start at
ELO_INITIAL_RATING for a competitor with no pre-June matches.

Calibration: calibration-policy-v2 affine map  z=logit(p_raw); z_cal=intercept+z/temperature;
p_cal=sigmoid(z_cal); per-tour params frozen below.

Identity: the ONE governed bridge (sport_tennis.identity_bridge.build_bridge), built with the
SAME universe-filtered resolution as docs/evidence/tennis-data-2026-07-18/scripts/
eligibility_and_designs.py so the manifest's tour tags are reproduced.
"""
from __future__ import annotations

import bz2
import csv
import hashlib
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, "/home/user/Moneymaker")

SCRATCH = "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad"
TENNIS_DATA = os.path.join(SCRATCH, "tennis-data")
PILOT = os.path.join(SCRATCH, "pilot-data")
sys.path.insert(0, TENNIS_DATA)

import f2_run as F  # noqa: E402  iter_rows/parse_date/load_tour/RAW (no odds read)
from sport_tennis.elo_family import ELO_INITIAL_RATING, elo_win_probability  # noqa: E402
from sport_tennis.identity_bridge import (  # noqa: E402
    _td_key,
    build_bridge,
    normalize_name,
)

BOUNDARY = date(2026, 6, 1)
TRANSFER_MANIFEST = (
    "/home/user/Moneymaker/docs/evidence/stage2d-june-m1-transfer/JUNE_M1_TRANSFER_MANIFEST.jsonl"
)
UNIVERSE_CSV = (
    "/home/user/Moneymaker/docs/evidence/pilot-2026-06-tennis/"
    "PRIMARY_JUNE_ANALYSIS_UNIVERSE_MANIFEST.csv"
)
CORPUS_META = os.path.join(PILOT, "audit", "full_corpus_metadata.jsonl")
F3_REPORT = os.path.join(TENNIS_DATA, "F3_CONFIRMATORY_REPORT.json")
OUT_DIR = "/home/user/Moneymaker/docs/evidence/stage2e-june-m1-bundle"

# calibration-policy-v2 (frozen affine, per tour)
CALIBRATION = {
    "ATP": {"intercept": 0.025399, "temperature": 1.218638},
    "WTA": {"intercept": 0.029204, "temperature": 1.150681},
}
CALIBRATION_PROVENANCE = "calibration-policy-v2"

# forbidden substrings: no output key or read value may expose an outcome
_FORBIDDEN_KEY_SUBSTR = ("winner", "loser", "status", "settled", "result", "score")


def affine_calibrate(p_raw: float, tour: str) -> float:
    params = CALIBRATION[tour]
    z = math.log(p_raw / (1.0 - p_raw))
    z_cal = params["intercept"] + z / params["temperature"]
    return 1.0 / (1.0 + math.exp(-z_cal))


def build_ratings(tour: str, k_global: float) -> dict[tuple[str, str], float]:
    """Final per-tour global Elo ratings as of 2026-05-31, keyed by td competitor key
    (_td_key(normalize_name(name))). Same-day BATCH update at k_global over ALL pre-June
    completed matches in date order. Cold start at ELO_INITIAL_RATING."""
    matches, _excl = F.load_tour(tour)  # (date, key_w, key_l); completed+identity+dedup, date<BOUNDARY
    by_day: dict[date, list[tuple[tuple[str, str], tuple[str, str]]]] = defaultdict(list)
    for d, kw, kl in matches:
        assert d < BOUNDARY, f"pre-June invariant violated: {d}"
        by_day[d].append((kw, kl))
    ratings: dict[tuple[str, str], float] = {}
    for d in sorted(by_day):
        deltas: dict[tuple[str, str], float] = defaultdict(float)
        # deterministic within-day order; batch => order-invariant anyway
        for kw, kl in sorted(by_day[d], key=lambda m: tuple(sorted((m[0], m[1])))):
            lo, hi = sorted((kw, kl))
            r_lo = ratings.get(lo, ELO_INITIAL_RATING)
            r_hi = ratings.get(hi, ELO_INITIAL_RATING)
            p_lo = elo_win_probability(r_lo, r_hi)
            score_lo = 1.0 if kw == lo else 0.0
            deltas[lo] += k_global * (score_lo - p_lo)
            deltas[hi] += k_global * ((1.0 - score_lo) - (1.0 - p_lo))
        for k, dv in deltas.items():
            ratings[k] = ratings.get(k, ELO_INITIAL_RATING) + dv
    return ratings


def load_open_runners(stream_path: str) -> dict[int, str] | None:
    """Return {selection_id -> runner name} from the FIRST pre-off marketDefinition whose
    status=='OPEN'. Reads ONLY runner id + name. Never reads runner WINNER/LOSER status,
    CLOSED market definitions, settledTime, or any settlement field. Returns None if no OPEN
    marketDefinition is present."""
    with bz2.open(stream_path, "rt") as fh:
        for line in fh:
            obj = json.loads(line)
            for mc in obj.get("mc", []):
                md = mc.get("marketDefinition")
                if not md:
                    continue
                if md.get("status") != "OPEN":
                    # skip any non-OPEN (SUSPENDED/CLOSED/...) definition entirely
                    continue
                out: dict[int, str] = {}
                for r in md.get("runners", []):
                    # take ONLY id + name; runner-level status is not read/recorded
                    rid = r.get("id")
                    name = r.get("name")
                    if rid is not None and name is not None:
                        out[int(rid)] = str(name).strip()
                return out
    return None


def main() -> None:
    # ---- frozen 2026-fold k_global per tour ----
    f3 = json.load(open(F3_REPORT))
    k_by_tour = {
        "ATP": float(f3["selected_k_by_fold"]["ATP"]["2026"]["k_global"]),
        "WTA": float(f3["selected_k_by_fold"]["WTA"]["2026"]["k_global"]),
    }

    # ---- reproduce the governed identity bridge exactly as eligibility_and_designs.py ----
    names_by_tour: dict[str, set] = {"ATP": set(), "WTA": set()}
    for fn in sorted(os.listdir(F.RAW)):
        tour = "ATP" if fn.startswith("atp") else "WTA"
        for hdr, row in F.iter_rows(os.path.join(F.RAW, fn)):
            cols = {h: (row[i] if i < len(row) else None) for i, h in enumerate(hdr)}
            d = F.parse_date(cols.get("Date"))
            if d is None or d >= BOUNDARY:
                continue
            cm = str(cols.get("Comment") or "Completed").strip().lower()
            if not cm.startswith("completed"):
                continue
            w, l = cols.get("Winner"), cols.get("Loser")
            if not w or not l:
                continue
            names_by_tour[tour].add(str(w).strip())
            names_by_tour[tour].add(str(l).strip())

    uni_rows = list(csv.DictReader(open(UNIVERSE_CSV)))
    uni = {
        r["market_id"]
        for r in uni_rows
        if r["universe_membership"] == "PRIMARY_JUNE_SINGLES_UNIVERSE"
    }
    market_names: dict[str, list[str]] = {}
    stream_rel: dict[str, str] = {}
    with open(CORPUS_META) as fh:
        for line in fh:
            r = json.loads(line)
            if r["market_id"] in uni:
                if r.get("runner_names"):
                    market_names[r["market_id"]] = [n.strip() for n in r["runner_names"]]
                stream_rel[r["market_id"]] = r["path"]
    all_bf = sorted({n for ns in market_names.values() for n in ns})
    res = build_bridge(
        td_names_by_tour={
            "ATP": sorted(names_by_tour["ATP"]),
            "WTA": sorted(names_by_tour["WTA"]),
        },
        betfair_full_names=all_bf,
        source_vintage="vintage-2026-07-18",
    )
    mapped = {m.betfair_alias.display_name: m for m in res.mappings}

    # ---- final per-tour ratings as of 2026-05-31 ----
    ratings = {tour: build_ratings(tour, k_by_tour[tour]) for tour in ("ATP", "WTA")}

    # ---- transfer manifest: ELIGIBLE_F2 rows only ----
    manifest_rows = []
    for line in open(TRANSFER_MANIFEST):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["reason"] == "ELIGIBLE_F2":
            manifest_rows.append(r)
    assert len(manifest_rows) == 1213, f"expected 1213 ELIGIBLE_F2, got {len(manifest_rows)}"

    bundle: list[dict] = []
    exclusions: list[dict] = []
    n_missing_stream = 0
    n_missing_selection_join = 0
    tour_mismatch: list[dict] = []

    for r in manifest_rows:
        mid = r["market_id"]
        rel = stream_rel.get(mid)
        stream_path = os.path.join(PILOT, rel) if rel else None
        if not stream_path or not os.path.exists(stream_path):
            n_missing_stream += 1
            exclusions.append({"market_id": mid, "reason": "NO_STREAM_FILE"})
            continue
        runners = load_open_runners(stream_path)
        if not runners:
            n_missing_stream += 1
            exclusions.append({"market_id": mid, "reason": "NO_OPEN_MARKETDEF"})
            continue
        if len(runners) != 2:
            exclusions.append(
                {"market_id": mid, "reason": f"NON_BINARY_MARKET:{len(runners)}_runners"}
            )
            continue

        # identity join: each pre-off runner name -> governed CompetitorId + tour
        resolved = []  # (selection_id, competitor_id_str, tour, td_key)
        unresolved_names = []
        for sel_id, name in runners.items():
            m = mapped.get(name)
            if m is None:
                unresolved_names.append(name)
                continue
            cid = m.competitor_id.value
            tkey = _td_key(normalize_name(m.source.raw_name))
            resolved.append((sel_id, cid, m.source.tour, tkey))
        if len(resolved) != 2:
            n_missing_selection_join += 1
            exclusions.append(
                {
                    "market_id": mid,
                    "reason": "SELECTION_NAME_UNRESOLVED:" + "|".join(sorted(unresolved_names)),
                }
            )
            continue

        tours = {c[2] for c in resolved}
        if len(tours) != 1:
            exclusions.append({"market_id": mid, "reason": "MIXED_TOUR_UNEXPECTED"})
            continue
        tour = resolved[0][2]
        if r.get("tour") is not None and r["tour"] != tour:
            tour_mismatch.append({"market_id": mid, "manifest": r["tour"], "bridge": tour})

        # designated = LOWER CompetitorId string value
        resolved.sort(key=lambda c: c[1])
        (sel_des, cid_des, _t, key_des), (sel_oth, cid_oth, _t2, key_oth) = resolved

        rating_des = ratings[tour].get(key_des, ELO_INITIAL_RATING)
        rating_oth = ratings[tour].get(key_oth, ELO_INITIAL_RATING)
        p_raw = elo_win_probability(rating_des, rating_oth)
        p_cal = affine_calibrate(p_raw, tour)

        bundle.append(
            {
                "market_id": mid,
                "tour": tour,
                "cohort": r.get("cohort"),
                "prior_band": r.get("prior_match_band_min_player"),
                "cluster_day": r.get("calendar_day_cluster"),
                "competitor_designated": cid_des,
                "competitor_other": cid_oth,
                "selection_id_designated": int(sel_des),
                "selection_id_other": int(sel_oth),
                "p_raw_designated": p_raw,
                "p_cal_designated": p_cal,
            }
        )

    # ---- deterministic sort by market_id, serialise ----
    bundle.sort(key=lambda b: b["market_id"])
    body = "".join(json.dumps(b, sort_keys=True) + "\n" for b in bundle).encode()
    bundle_sha256 = hashlib.sha256(body).hexdigest()

    # ---- verification (a): NO output key exposes an outcome ----
    for b in bundle:
        for k in b:
            kl = k.lower()
            assert not any(
                s in kl for s in _FORBIDDEN_KEY_SUBSTR
            ), f"forbidden outcome-like key in bundle: {k}"

    atp_count = sum(1 for b in bundle if b["tour"] == "ATP")
    wta_count = sum(1 for b in bundle if b["tour"] == "WTA")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "JUNE_M1_PREDICTION_BUNDLE.jsonl"), "wb") as fh:
        fh.write(body)

    summary = {
        "n_markets": len(bundle),
        "atp_count": atp_count,
        "wta_count": wta_count,
        "n_missing_stream": n_missing_stream,
        "n_missing_selection_join": n_missing_selection_join,
        "exclusions": sorted(exclusions, key=lambda e: e["market_id"]),
        "bundle_sha256": bundle_sha256,
        "calibration_provenance": CALIBRATION_PROVENANCE,
        "calibration_params": CALIBRATION,
        "k_global_by_tour": k_by_tour,
        "generated_from": {
            "transfer_manifest": TRANSFER_MANIFEST,
            "eligible_f2_rows": len(manifest_rows),
            "tennis_data_vintage": "vintage-2026-07-18",
            "f3_report": F3_REPORT,
            "identity_policy": "td-norm-v1",
            "rating_model": "F2-global-elo-v1 (same-day batch, cold-start=1500.0)",
            "june_streams_root": os.path.join(
                PILOT, "extracted", "ADVANCED", "2026", "Jun"
            ),
        },
        "tour_mismatch_vs_manifest": tour_mismatch,
        "manifest_tour_match": len(tour_mismatch) == 0,
    }
    with open(os.path.join(OUT_DIR, "BUNDLE_SUMMARY.json"), "w") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)

    print(json.dumps(summary, indent=1, sort_keys=True))
    print(f"\nn_markets={len(bundle)} of 1213  ATP={atp_count} WTA={wta_count} "
          f"exclusions={len(exclusions)}  sha256={bundle_sha256}")


if __name__ == "__main__":
    main()
