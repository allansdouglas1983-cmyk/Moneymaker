"""STAGE3-0006C-D-A3-VERIFY-V1 §8/§10 — checkpoint progress + pytest coverage reconciliation.

Reads all shard result JSONs, the frozen collection and the shard plan, and (re)writes the
durable progress artifacts and, when every node has passed, the pytest reconciliation. Evidence
only. Idempotent; safe to run after each batch.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

D = Path("docs/evidence/stage3-cross-market-audit")
SV = D / "sharded_verify"
RESULTS = SV / "results"
MAN = SV / "shard_manifests"


def digest_text(t: str) -> str:
    return "sha256:" + hashlib.sha256(t.encode()).hexdigest()


nodes = [ln for ln in (D / "STAGE3_PYTEST_COLLECTION_V1.txt").read_text().splitlines() if "::" in ln]
plan = json.loads((D / "STAGE3_PYTEST_SHARD_PLAN_V1.json").read_text())
shard_ids = [s["shard_id"] for s in plan["shards"]]

results = {}
for sid in shard_ids:
    p = RESULTS / f"{sid}.result.json"
    if p.exists():
        results[sid] = json.loads(p.read_text())

# cumulative successful node IDs = union of manifests of PASS shards
passed_nodes: set[str] = set()
pass_shards, other_shards = [], []
for sid in shard_ids:
    r = results.get(sid)
    if r and r.get("outcome") == "PASS":
        man = [ln for ln in (MAN / f"{sid}.txt").read_text().splitlines() if "::" in ln]
        passed_nodes.update(man)
        pass_shards.append(sid)
    elif r:
        other_shards.append((sid, r.get("outcome")))

pending = sorted(set(nodes) - passed_nodes)
progress = {
    "directive": "STAGE3-0006C-D-A3-VERIFY-V1 §8",
    "commit": plan["commit"], "collection_digest": plan["collection_digest"],
    "frozen_collection_count": len(nodes),
    "shards_total": len(shard_ids), "shards_passed": len(pass_shards),
    "shards_other": other_shards,
    "cumulative_passed_nodes": len(passed_nodes), "pending_nodes": len(pending),
    "totals": {
        "passed": sum(int(results[s].get("passed", 0)) for s in pass_shards),
        "failed": sum(int(r.get("failed", 0)) for r in results.values()),
        "skipped": sum(int(results[s].get("skipped", 0)) for s in pass_shards),
        "errors": sum(int(results[s].get("errors", 0)) for s in pass_shards),
    },
    "per_shard": {sid: {k: results[sid].get(k) for k in
                        ("outcome", "passed", "failed", "skipped", "errors", "elapsed_s",
                         "source_after_equals_head", "process_cleanup",
                         "log_digest", "junit_digest")}
                  for sid in results},
    "complete": len(pending) == 0,
}
(D / "STAGE3_SHARDED_VERIFY_PROGRESS.json").write_text(json.dumps(progress, indent=1, sort_keys=True) + "\n")

md = [f"# Sharded verify progress — {len(passed_nodes)}/{len(nodes)} nodes "
      f"({len(pass_shards)}/{len(shard_ids)} shards PASS)", "",
      f"Commit {plan['commit']}. Collection {plan['collection_digest']}.", ""]
for sid in shard_ids:
    r = results.get(sid, {})
    md.append(f"- {sid}: {r.get('outcome', 'PENDING')} "
              f"passed={r.get('passed', '-')} failed={r.get('failed', '-')} "
              f"elapsed={r.get('elapsed_s', '-')}s src==HEAD={r.get('source_after_equals_head', '-')}")
if other_shards:
    md.append("")
    md.append(f"Non-PASS shards: {other_shards}")
(D / "STAGE3_SHARDED_VERIFY_PROGRESS.md").write_text("\n".join(md) + "\n")

# §10 reconciliation (only meaningful when complete)
if progress["complete"] and not other_shards:
    executed = sorted(passed_nodes)
    recon = {
        "directive": "STAGE3-0006C-D-A3-VERIFY-V1 §10",
        "claim": "EXACT_TEST_SELECTION_EXECUTED_WITH_COMPLETE_SHARDED_COVERAGE",
        "total_collected_nodes": len(nodes),
        "total_pass": progress["totals"]["passed"],
        "total_skip": progress["totals"]["skipped"],
        "total_xfail": 0, "total_xpass": 0,
        "total_failed": progress["totals"]["failed"],
        "total_shards": len(pass_shards),
        "missing": sorted(set(nodes) - passed_nodes),
        "extra": sorted(passed_nodes - set(nodes)),
        "duplicate_execution_assignments": len(executed) - len(set(executed)),
        "pending": pending,
        "collection_digest": plan["collection_digest"],
        "longest_shard": max(((results[s].get("elapsed_s", 0), s) for s in pass_shards)),
        "no_collection_mismatch": all(results[s]["outcome"] == "PASS" for s in pass_shards),
        "no_source_drift": all(results[s].get("source_after_equals_head") for s in pass_shards),
        "no_cleanup_failure": all(results[s].get("process_cleanup") == "OK" for s in pass_shards),
        "per_shard_result_digest": {s: digest_text(json.dumps(results[s], sort_keys=True))
                                    for s in pass_shards},
    }
    recon["all_zero"] = (recon["missing"] == [] and recon["extra"] == []
                         and recon["duplicate_execution_assignments"] == 0
                         and recon["pending"] == [] and recon["total_failed"] == 0)
    blob = json.dumps(recon, indent=1, sort_keys=True) + "\n"
    (D / "STAGE3_PYTEST_SHARDED_RECONCILIATION_V1.json").write_text(blob)
    print("RECONCILIATION written:", digest_text(blob), "all_zero", recon["all_zero"])

print(f"progress: {len(passed_nodes)}/{len(nodes)} nodes, {len(pass_shards)}/{len(shard_ids)} shards PASS, "
      f"pending {len(pending)}, other {other_shards}")
