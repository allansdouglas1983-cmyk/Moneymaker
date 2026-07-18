"""Stage 2D §3 — PROSPECTIVE June M1 transfer manifest (OUTCOME-BLIND).

Distinct from the M2 intersection: M1 does NOT require a valid F0 market snapshot, only a
calibrated-F2-valid prediction. Tour (ATP/WTA) is derived from GOVERNED IDENTITY PROVENANCE
(the namespace each player resolves into via the td-norm-v1 bridge — m.source.tour), NEVER
inferred from name strings, tournaments, prices, or outcomes. Mixed/contradictory/absent tour
provenance -> a typed refusal. Reuses the exact governed bridge resolution of
eligibility_and_designs.py. No June outcome, no odds, no returns.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime

sys.path.insert(0, "/home/user/Moneymaker")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eligibility_and_designs import BANDS, band, iter_rows, parse_date  # governed helpers
from sport_tennis.identity_bridge import build_bridge

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "raw", "vintage-2026-07-18")
SP = "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad"
META = os.path.join(SP, "pilot-data", "audit", "full_corpus_metadata.jsonl")
UNI = "/home/user/Moneymaker/docs/evidence/pilot-2026-06-tennis/PRIMARY_JUNE_ANALYSIS_UNIVERSE_MANIFEST.csv"
BOUNDARY = date(2026, 6, 1)
MIN_SUPPORT = 500

# frozen final affine calibration (calibration-policy-v2; scorecard digest 6001657753…)
CALIB = {
    "policy": "calibration-policy-v2",
    "scorecard_digest": "sha256:6001657753c8a26ea2ba53e3d323c0a132b1034161b6708d65c2c45e30284470",
    "ATP": {"intercept": 0.025399, "temperature": 1.218638},
    "WTA": {"intercept": 0.029204, "temperature": 1.150681},
}
MODEL = "EXP-STAGE2-F2-GLOBAL-ELO-001"


def main() -> None:
    # ---- TD pre-June completed rows: per-player appearances + tour name sets ----
    appearances: dict[tuple[str, str], int] = defaultdict(int)
    names_by_tour: dict[str, set] = {"ATP": set(), "WTA": set()}
    for fn in sorted(os.listdir(RAW)):
        tour = "ATP" if fn.startswith("atp") else "WTA"
        for hdr, row in iter_rows(os.path.join(RAW, fn)):
            cols = {h: (row[i] if i < len(row) else None) for i, h in enumerate(hdr)}
            d = parse_date(cols.get("Date"))
            if d is None or d >= BOUNDARY:
                continue
            if not str(cols.get("Comment") or "Completed").strip().lower().startswith("completed"):
                continue
            w, l = cols.get("Winner"), cols.get("Loser")
            if not w or not l:
                continue
            for name in (str(w).strip(), str(l).strip()):
                names_by_tour[tour].add(name)
                appearances[(tour, name)] += 1

    # ---- June singles universe (2876) + strict flag + names + scheduled day ----
    uni_rows = list(csv.DictReader(open(UNI)))
    uni = {r["market_id"]: ("STRICT" in r["cohort_tags"])
           for r in uni_rows if r["universe_membership"] == "PRIMARY_JUNE_SINGLES_UNIVERSE"}
    market_names: dict[str, list[str]] = {}
    market_day: dict[str, str] = {}
    for line in open(META):
        r = json.loads(line)
        mid = r["market_id"]
        if mid in uni and r.get("runner_names"):
            market_names[mid] = [n.strip() for n in r["runner_names"]]
            od = r.get("open_date")
            market_day[mid] = datetime.strptime(od, "%Y-%m-%dT%H:%M:%S.%f%z").date().isoformat() if od else "UNKNOWN"

    all_bf = sorted({n for ns in market_names.values() for n in ns})
    res = build_bridge(
        td_names_by_tour={"ATP": sorted(names_by_tour["ATP"]), "WTA": sorted(names_by_tour["WTA"])},
        betfair_full_names=all_bf, source_vintage="vintage-2026-07-18",
    )
    mapped = {m.betfair_alias.display_name: m for m in res.mappings}
    unresolved_reason = {u.name: u.reason.value for u in res.unresolved if u.name in set(all_bf)}

    manifest = []
    excl_funnel: Counter = Counter()
    tour_counts: Counter = Counter()
    band_by_tour: dict[str, Counter] = {"ATP": Counter(), "WTA": Counter()}
    day_by_tour: dict[str, Counter] = {"ATP": Counter(), "WTA": Counter()}
    f2 = f2_strict = 0
    for mid in sorted(market_names):
        names = market_names[mid]
        strict = uni[mid]
        flags = [n in mapped for n in names]
        both = all(flags)
        rec = {"market_id": mid, "both_mapped": both,
               "cohort": "STRICT" if strict else "PRIMARY_ONLY_TIER",
               "calendar_day_cluster": market_day.get(mid, "UNKNOWN"),
               "outcome_eligibility_policy": "label-policy-v1-completed-only",
               "identity_policy": "td-norm-v1", "eligibility_policy": "eligibility-policy-v1",
               "selected_model": MODEL, "calibration_policy": CALIB["policy"],
               "source_vintage": "vintage-2026-07-18"}
        if not both:
            missing = [unresolved_reason.get(n, "NO_SOURCE_MATCH") for n, ok in zip(names, flags) if not ok]
            reason = "EXCLUDED_IDENTITY:" + "|".join(sorted(set(missing)))
            rec.update({"f2_can_emit": False, "calibrated_f2_valid": False, "tour": None,
                        "prior_match_band_min_player": None, "reason": reason})
            excl_funnel[reason.split(":")[0]] += 1
            manifest.append(rec)
            continue
        # governed tour provenance from identity namespaces
        tours = {mapped[n].source.tour for n in names}
        counts = [appearances[(mapped[n].source.tour, mapped[n].source.raw_name)] for n in names]
        prior_band = band(min(counts))
        if len(tours) == 1:
            tour = next(iter(tours))
            reason = "ELIGIBLE_F2"
            f2 += 1
            f2_strict += strict
            tour_counts[tour] += 1
            band_by_tour[tour][prior_band] += 1
            day_by_tour[tour][market_day.get(mid, "UNKNOWN")] += 1
        else:
            tour = "MIXED_TOUR"
            reason = "REFUSED_TOUR_PROVENANCE:MIXED_TOUR"  # contradictory namespaces
            excl_funnel["REFUSED_TOUR_PROVENANCE"] += 1
        rec.update({"f2_can_emit": True, "calibrated_f2_valid": len(tours) == 1,
                    "tour": tour, "prior_match_band_min_player": prior_band, "reason": reason})
        if reason == "ELIGIBLE_F2":
            excl_funnel["ELIGIBLE_F2"] += 1
        manifest.append(rec)

    body = "\n".join(json.dumps(m, sort_keys=True) for m in manifest) + "\n"
    digest = "sha256:" + hashlib.sha256(body.encode()).hexdigest()
    with open(os.path.join(ROOT, "JUNE_M1_TRANSFER_MANIFEST.jsonl"), "w") as fh:
        fh.write(body)

    atp, wta = tour_counts["ATP"], tour_counts["WTA"]
    def clus(counter_map):
        sizes = sorted(counter_map.values())
        return ({"n_clusters": len(sizes), "min": sizes[0], "max": sizes[-1],
                 "p50": sizes[len(sizes)//2], "mean": round(sum(sizes)/len(sizes), 2)}
                if sizes else {})
    summary = {
        "artefact": "PROSPECTIVE June M1 transfer manifest (outcome-blind)",
        "purpose": "Stage 2D §3 — calibrated-F2-valid June singles for the M1 external "
                   "transfer check; does NOT require an F0 market snapshot.",
        "min_supported_predictions": MIN_SUPPORT,
        "total_june_primary_singles": len(manifest),
        "f2_valid_total": f2,
        "atp_count": atp,
        "wta_count": wta,
        "mixed_or_unknown_tour_refusals": tour_counts["MIXED_TOUR"] + excl_funnel.get("REFUSED_TOUR_PROVENANCE", 0),
        "f2_valid_strict": f2_strict,
        "f2_valid_primary_only_tier": f2 - f2_strict,
        "prior_history_cohorts_by_tour": {t: dict(sorted(band_by_tour[t].items())) for t in ("ATP", "WTA")},
        "calendar_day_clusters": {"overall_atp_plus_wta": clus(Counter(
            {d: day_by_tour["ATP"][d] + day_by_tour["WTA"][d]
             for d in set(day_by_tour["ATP"]) | set(day_by_tour["WTA"])})),
            "ATP": clus(day_by_tour["ATP"]), "WTA": clus(day_by_tour["WTA"])},
        "exclusion_funnel": dict(excl_funnel),
        "support_verdict": {
            "atp_supported": atp >= MIN_SUPPORT, "wta_supported": wta >= MIN_SUPPORT,
            "overall_supported": f2 >= MIN_SUPPORT,
            "note": ("A tour with < 500 supported predictions CANNOT pass its tour-specific "
                     "M1 requirements on June; Stage A returns CONTINUE for that tour unless the "
                     "frozen amendment permits an overall-only PASS. Threshold fixed BEFORE these "
                     "counts were computed; not to be altered after."),
        },
        "tour_derivation": "governed identity-namespace provenance (m.source.tour); "
            "mixed/contradictory/absent -> typed refusal; NEVER inferred from names/tournaments/"
            "prices/outcomes.",
        "calibration_provenance": CALIB,
        "manifest_digest": digest,
        "note": "June SEALED (SPEC-092); derived only from SAFE_BEFORE_LOCKBOX fields "
                "(schedule, runner names, pre-June TD history).",
    }
    blob = json.dumps(summary, indent=1, sort_keys=True, default=str)
    with open(os.path.join(ROOT, "JUNE_M1_TRANSFER_SUMMARY.json"), "w") as fh:
        fh.write(blob)
    print(blob)


if __name__ == "__main__":
    main()
