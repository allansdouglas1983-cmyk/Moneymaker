"""Stage 2C §10 — PROSPECTIVE June M2 intersection manifest (OUTCOME-BLIND).

Joins the two frozen per-market June manifests by market_id — NEITHER reads a sporting
outcome:
  * F0_MARKET_YARDSTICK_MANIFEST.jsonl  (pre-off Betfair prices; committed p_market_info)
  * JUNE_F2F3_ELIGIBILITY_MANIFEST.jsonl (identity governance + pre-June history existence)

A market enters the prospective M2 intersection only when ALL outcome-blind gates hold:
  (a) in the frozen 2,876 primary June singles universe (every manifest row is),
  (b) F0 produced a valid COMMITTED p_market_info snapshot (committed == true),
  (c) both competitor identities are governed (f2_can_emit implies both_mapped),
  (d) F2 can emit a valid probability from pre-June history (f2_can_emit == true),
  (e) the final affine calibration is available (global: calibration-policy-v2 final
      params are frozen pre-June; applies to any F2 probability) — always satisfied here.
The selected-outcome-policy scoring gate (completed singles, label-policy-v1) can ONLY be
evaluated once June is opened; it can only REDUCE this count. So the intersection below is
the PROSPECTIVE MAXIMUM eligible, subject to June completion status. UTC calendar day (the
tennis correlation-cluster key) is derived from the scheduled market_time — a
SAFE_BEFORE_LOCKBOX field — never from any result.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
EV = "/home/user/Moneymaker/docs/evidence"
F0 = os.path.join(EV, "stage2b-f0-f2-runs/F0_MARKET_YARDSTICK_MANIFEST.jsonl")
ELIG = os.path.join(EV, "tennis-data-2026-07-18/JUNE_F2F3_ELIGIBILITY_MANIFEST.jsonl")


def load(path):
    return {json.loads(l)["market_id"]: json.loads(l) for l in open(path)}


def main() -> None:
    f0 = load(F0)
    el = load(ELIG)
    assert set(f0) == set(el), "manifest market-id sets differ"
    markets = sorted(f0)

    total = len(markets)
    f0_committed = [m for m in markets if f0[m]["committed"]]
    f2_valid = [m for m in markets if el[m]["f2_can_emit"]]
    inter = [m for m in markets if f0[m]["committed"] and el[m]["f2_can_emit"]]
    inter_strict = [m for m in inter if f0[m]["cohort"] == "STRICT" and el[m]["cohort"] == "STRICT"]
    inter_primary_only = [m for m in inter if m not in set(inter_strict)]

    # prior-history cohorts within the intersection
    bands = defaultdict(int)
    for m in inter:
        bands[el[m]["prior_match_band_min_player"] or "unknown"] += 1

    # UTC-calendar-day clusters within the intersection (scheduled market time)
    day_counts = defaultdict(int)
    for m in inter:
        ms = f0[m]["market_time_ms_at_commit"]
        day = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()
        day_counts[day] += 1
    sizes = sorted(day_counts.values())
    cluster_dist = {
        "n_clusters": len(sizes), "min": sizes[0], "max": sizes[-1],
        "p50": sizes[len(sizes) // 2], "p90": sizes[int(0.9 * len(sizes))],
        "mean": round(sum(sizes) / len(sizes), 2),
    } if sizes else {}

    # exclusion funnel (outcome-blind)
    f0_refusals = defaultdict(int)
    for m in markets:
        if not f0[m]["committed"]:
            f0_refusals[f0[m]["refusal_reason"] or "UNCOMMITTED"] += 1
    elig_reasons = defaultdict(int)
    for m in markets:
        if not el[m]["f2_can_emit"]:
            elig_reasons[el[m]["reason"]] += 1
    # why intersection < min(F0-valid, F2-valid): F2-valid markets whose F0 did not commit
    f2valid_no_f0 = [m for m in f2_valid if not f0[m]["committed"]]
    f0valid_no_f2 = [m for m in f0_committed if not el[m]["f2_can_emit"]]

    rep = {
        "artefact": "PROSPECTIVE June M2 intersection manifest (outcome-blind)",
        "purpose": "Stage 2C §10 — the outcome-blind maximum-eligible June set for M2 "
                   "(market-only vs pre-fitted combined). No sporting outcome is read.",
        "universe_total_june_primary_singles": total,           # 2876
        "f0_committed_p_market_info": len(f0_committed),
        "f2_valid_from_pre_june_history": len(f2_valid),
        "final_prospective_intersection": len(inter),
        "intersection_strict_cohort": len(inter_strict),
        "intersection_primary_only_tier": len(inter_primary_only),
        "prior_history_cohorts_in_intersection": dict(sorted(bands.items())),
        "utc_day_cluster_distribution_in_intersection": cluster_dist,
        "atp_wta_counts": "NOT DERIVABLE from the two frozen per-market manifests (neither "
            "carries a tour tag). Deriving it requires a governed join of the June market "
            "catalogue competition/tour tag (SAFE_BEFORE_LOCKBOX) added at manifest "
            "finalization BEFORE opening. Reported as a gap, never fabricated (Stage 2C §10).",
        "exclusion_funnel": {
            "f0_uncommitted_reasons": dict(sorted(f0_refusals.items())),
            "f2_ineligible_reasons": dict(sorted(elig_reasons.items())),
            "f2_valid_but_f0_uncommitted": len(f2valid_no_f0),
            "f0_committed_but_f2_ineligible": len(f0valid_no_f2),
        },
        "gates_applied_outcome_blind": [
            "in frozen 2876 universe", "F0 committed p_market_info",
            "both identities governed", "F2 emits from pre-June history",
            "final affine calibration available (global)",
        ],
        "gate_deferred_to_june": "selected outcome policy scoring (completed singles, "
            "label-policy-v1) — evaluable only on opening; can only REDUCE the count.",
        "source_manifests": {
            "f0": "docs/evidence/stage2b-f0-f2-runs/F0_MARKET_YARDSTICK_MANIFEST.jsonl "
                  "(sha256 90b80100…)",
            "eligibility": "docs/evidence/tennis-data-2026-07-18/"
                           "JUNE_F2F3_ELIGIBILITY_MANIFEST.jsonl (sha256 96bd1f12…)",
        },
        "note": "June remains SEALED (SPEC-092). This manifest is prospective planning "
                "metadata derived from SAFE_BEFORE_LOCKBOX fields only.",
    }
    blob = json.dumps(rep, indent=1, sort_keys=True, default=str)
    path = os.path.join(ROOT, "JUNE_M2_INTERSECTION_MANIFEST.json")
    with open(path, "w") as fh:
        fh.write(blob)
    digest = "sha256:" + hashlib.sha256(blob.encode()).hexdigest()
    print(json.dumps({k: rep[k] for k in (
        "universe_total_june_primary_singles", "f0_committed_p_market_info",
        "f2_valid_from_pre_june_history", "final_prospective_intersection",
        "intersection_strict_cohort", "intersection_primary_only_tier",
        "prior_history_cohorts_in_intersection",
        "utc_day_cluster_distribution_in_intersection")}, indent=1))
    print("exclusion_funnel:", json.dumps(rep["exclusion_funnel"]))
    print("digest:", digest)


if __name__ == "__main__":
    main()
