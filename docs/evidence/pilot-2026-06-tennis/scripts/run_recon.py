"""Batch driver: reconstruct every date-included MATCH_ODDS market (singles + doubles)
from its canonical standalone file. Deterministic pure function per market; output order
sorted by market_id so the whole run is reproducible and hashable.
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

AUDIT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(AUDIT)
sys.path.insert(0, AUDIT)
from recon import reconstruct  # noqa: E402


def load_targets(limit: int | None = None) -> list[dict]:
    # cohort membership from the frozen universe manifest
    man = {}
    with open(os.path.join(AUDIT, "PRIMARY_JUNE_ANALYSIS_UNIVERSE_MANIFEST.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            man[r["market_id"]] = r
    # canonical source path from the canonical replay manifest
    canon = {}
    with open(os.path.join(AUDIT, "CANONICAL_REPLAY_MANIFEST.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            canon[r["market_id"]] = r
    targets = []
    for mid, m in man.items():
        if m["universe_membership"] not in ("PRIMARY_JUNE_SINGLES_UNIVERSE", "DOUBLES_DESCRIPTIVE_COHORT"):
            continue  # excluded (out-of-window / unknown) not reconstructed
        c = canon[mid]
        assert c["canonical_provenance"] == "STANDALONE_FILE"
        targets.append(
            {
                "market_id": mid,
                "path": os.path.join(ROOT, c["canonical_source"]),
                "cohort": m["universe_membership"],
                "match_format": m["match_format"],
                "classification_evidence": m["classification_evidence"],
                "strict_sensitivity": "STRICT_SIBLING_CORROBORATED_SENSITIVITY_COHORT" in m["cohort_tags"],
            }
        )
    targets.sort(key=lambda x: x["market_id"])
    if limit:
        targets = targets[:limit]
    return targets


def _work(t: dict) -> dict:
    try:
        rec = reconstruct(t["path"], t["market_id"])
        rec["cohort"] = t["cohort"]
        rec["match_format"] = t["match_format"]
        rec["classification_evidence"] = t["classification_evidence"]
        rec["strict_sensitivity"] = t["strict_sensitivity"]
        rec["error"] = None
        return rec
    except Exception as e:  # noqa: BLE001
        import traceback

        return {"market_id": t["market_id"], "path": t["path"], "error": f"{e}", "traceback": traceback.format_exc()}


def main() -> None:
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    out_path = sys.argv[1]
    targets = load_targets(limit)
    n = 0
    errors = 0
    with ProcessPoolExecutor(max_workers=4) as pool, open(out_path, "w") as out:
        for rec in pool.map(_work, targets, chunksize=16):
            n += 1
            if rec.get("error"):
                errors += 1
            out.write(json.dumps(rec, default=str) + "\n")
    print(f"reconstructed {n} markets, errors={errors} -> {out_path}")


if __name__ == "__main__":
    main()
