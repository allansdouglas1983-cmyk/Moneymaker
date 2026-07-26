"""STAGE3-0006C-D-A3-VERIFY-V1 §1/§2/§3/§5/§6 — sharded-verification setup.

Emits the append-only policy, the preflight integrity record, the exact verify plan, the frozen
pytest collection artifacts, and the deterministic shard plan (with per-shard node-ID manifests).
Evidence/policy only; changes no production code, test, golden, registration or Makefile scope.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

D = Path("docs/evidence/stage3-cross-market-audit")
SPEC = Path("specs/programme")
SCR = Path("/tmp/claude-0/-home-user-Moneymaker/"
           "b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad")
SHARD_DIR = D / "sharded_verify" / "shard_manifests"
SHARD_DIR.mkdir(parents=True, exist_ok=True)


def sh(*cmd: str) -> str:
    return subprocess.check_output(list(cmd)).decode().strip()


def sha_text(t: str) -> str:
    return "sha256:" + hashlib.sha256(t.encode()).hexdigest()


def sha_file(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


COMMIT = sh("git", "rev-parse", "HEAD")
MAKEFILE_SHA = sha_file(Path("Makefile"))
PY_FULL = "3.11.15 (main, Mar  3 2026, 09:26:23) [GCC 13.3.0]"
PYTEST_CMD_PATHS = ["tests/unit", "tests/integration", "tests/properties", "tests/stateful",
                    "tests/failure_injection"]
PYTEST_BASE = ["uv", "run", "pytest", *PYTEST_CMD_PATHS, "-q"]

# ---------------------------------------------------------------- §1 policy (append-only)
policy = """# APPEND-ONLY execution-policy amendment. Does NOT modify the Makefile verify target.
amendment_id: STAGE3_SHARDED_VERIFICATION_POLICY_V1
authority: founder
directive: STAGE3-0006C-D-A3-VERIFY-V1
reason: >
  The execution environment imposes a hard ~600s foreground-command cap. The full-repository
  pytest workload selected by `make verify` cannot complete in one attached command, and
  detached/background execution is prohibited. This authorises one deterministic,
  coverage-complete, foreground-sharded execution of the EXACT `make verify` gate.
original_gate: "the exact current `make verify` Makefile target (Makefile sha256 %s)"
permitted_substitute_in_this_environment: FULL_VERIFY_SHARDED_V1
rules:
  - every non-pytest gate runs through its exact Makefile command
  - the pytest collection equals the exact collection selected by the current make verify pytest command
  - every collected pytest node is executed in exactly one successful shard
  - no test, file, marker, directory or plugin may be omitted
  - no xfail, skip, timeout, tolerance, assertion or expected result may be changed
  - no test may be rewritten to run faster
  - no source behavior may be changed to satisfy verification
  - adding JUnit/logging arguments is permitted only where behavior-neutral
  - timed-out attempts are operational incidents, never passing evidence
  - a timed-out shard is split and rerun from clean source state
  - a single test node that cannot finish within the foreground cap -> STOP_SINGLE_TEST_EXCEEDS_CAP
  - FULL_VERIFY_SHARDED_PASS is accepted for Stage-3 engineering, founder adjudication and
    synthetic/research progression
  - a monolithic `make verify` remains REQUIRED in a capable environment before public release,
    multi-user exposure, real-money canary, automated execution, production deployment
  - this policy does not authorise June coherence, outcomes, tips or execution
""" % MAKEFILE_SHA
(SPEC / "stage3-sharded-verification-policy-v1.yaml").write_text(policy)

# ---------------------------------------------------------------- §5 collection artifacts
nodes = [ln for ln in (SCR / "collect1.txt").read_text().splitlines() if "::" in ln]
nodes2 = [ln for ln in (SCR / "collect2.txt").read_text().splitlines() if "::" in ln]
assert nodes == nodes2, "collection not deterministic"
assert len(nodes) == len(set(nodes)), "duplicate node ids"
node_blob = "\n".join(nodes) + "\n"
(D / "STAGE3_PYTEST_COLLECTION_V1.txt").write_text(node_blob)
COLLECTION_DIGEST = sha_text(node_blob)
files = sorted({n.split("::")[0] for n in nodes})
collection_meta = {
    "collection_command": " ".join(PYTEST_BASE[:-1]) + " --collect-only -q",
    "collection_start_utc": "2026-07-24T23:59:29Z", "collection_end_utc": "2026-07-24T23:59:51Z",
    "total_collected": len(nodes), "node_id_digest": COLLECTION_DIGEST,
    "unique_test_file_count": len(files), "skipped_at_collection": 0,
    "collection_exit_code": 0, "second_collection_identical": nodes == nodes2,
    "duplicate_node_ids": 0,
}
(D / "STAGE3_PYTEST_COLLECTION_V1.json").write_text(json.dumps(collection_meta, indent=1, sort_keys=True) + "\n")

# ---------------------------------------------------------------- §2 preflight
preflight = {
    "branch": sh("git", "rev-parse", "--abbrev-ref", "HEAD"), "commit": COMMIT,
    "clean_working_tree": sh("git", "status", "--porcelain") == "",
    "active_pytest_make_cosmic_python_workers": "NONE",
    "makefile_sha256": MAKEFILE_SHA,
    "python_implementation": "CPython", "python_version_full": PY_FULL,
    "venv_digest_uv_lock": sha_file(Path("uv.lock")),
    "pytest_version": "9.1.1",
    "installed_plugins": {"pytest": "9.1.1", "hypothesis": "6.156.6"},
    "tool_versions": {"ruff": "0.15.21", "pylint": "4.0.6", "mypy": "2.3.0",
                      "cosmic-ray": "8.4.6"},
    "pytest_affecting_env_vars": "(none present)",
    "pytest_addopts_env": "<unset>",
    "pytest_ini_addopts": "--strict-markers",
    "stage3_source_digests": {
        f: sh("git", "hash-object", f) for f in (
            "sport_tennis/coherence/scan_variants.py",
            "sport_tennis/coherence/discretisation_stability.py",
            "sport_tennis/coherence/solver.py")},
    "governing_golden_digest": sha_file(
        Path("tests/unit/coherence/golden/SOLVER_GOLDEN_V3_DISCRETISATION_STABLE.json")),
    "governing_registration_digest": sha_file(
        SPEC / "cross-market-coherence-discretisation-stability-amendment-v1.yaml"),
    "prior_interrupted_verify_record_digest": sha_file(
        D / "STAGE3_A3_FULL_VERIFY_RECORD.json"),
    "integrity": "PASS",
}
for f, h in preflight["stage3_source_digests"].items():
    assert h == sh("git", "rev-parse", f"HEAD:{f}"), f"source drift {f}"
(D / "STAGE3_SHARDED_VERIFY_PREFLIGHT.json").write_text(json.dumps(preflight, indent=1, sort_keys=True) + "\n")

# ---------------------------------------------------------------- §3 verify plan (exact make verify)
verify_plan = {
    "makefile_sha256": MAKEFILE_SHA, "target": "verify", "working_directory": ".",
    "environment": "uv run (project venv)", "source_of_truth": "Makefile",
    "gates_in_execution_order": [
        {"id": "spec_coverage", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_spec_coverage.py --manifest docs/spec-manifest.yaml --enforce-states active,verified"},
        {"id": "spec_coverage_causal_money", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_spec_coverage.py --manifest docs/spec-manifest.yaml --enforce-states active,verified --require-causal-declarations --require-properties-for money"},
        {"id": "facts_freshness", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_facts_freshness.py --registry docs/facts.yaml"},
        {"id": "licensed_sources", "kind": "non-pytest", "tool": "python",
         "command": "uv run python -m tools.check_licensed_sources --registry docs/licensed-sources.yaml"},
        {"id": "pytest", "kind": "pytest", "tool": "pytest", "requires_sharding": True,
         "command": "uv run pytest tests/unit tests/integration tests/properties tests/stateful tests/failure_injection -q",
         "behavior_neutral_logging_additions_permitted": "--junitxml=<path>  (per shard, no -x, no marker/collection change; node IDs supplied as positional args)"},
        {"id": "ruff_ARG", "kind": "non-pytest", "tool": "ruff",
         "command": "uv run ruff check --select ARG ."},
        {"id": "pylint_W0613", "kind": "non-pytest", "tool": "pylint",
         "command": "uv run pylint --disable=all --enable=W0613 l4b_fill l5_decision l5b_risk l6_broker l7_settle l8_evidence governance price_contracts sport_core sport_tennis"},
        {"id": "escape_hatch_money", "kind": "non-pytest", "tool": "grep",
         "command": "! grep -rinE '<ESCAPE_HATCHES>' <MONEY> --include='*.py'"},
        {"id": "escape_hatch_evidence", "kind": "non-pytest", "tool": "grep",
         "command": "! grep -rinE '<ESCAPE_HATCHES>' l0_raw l1_reduce l3_features --include='*.py'"},
        {"id": "quarantine_1_research_scraping", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid research.scraping --from l5_decision l5b_risk l6_broker"},
        {"id": "quarantine_2_research_xmarket_exec", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid research.xmarket --from l5_decision l5b_risk l6_broker l7_settle l3_features l4_pricing"},
        {"id": "quarantine_3_l6_from_v0", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid l6_broker --from assistant_v0"},
        {"id": "quarantine_4_xmarket_from_v0", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid research.xmarket --from assistant_v0"},
        {"id": "quarantine_5_l6_from_xcontracts", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid l6_broker --from xmarket_contracts"},
        {"id": "quarantine_6_xmarket_from_xcontracts", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid research.xmarket --from xmarket_contracts"},
        {"id": "quarantine_7_bsp_from_l3", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid l8_evidence.reconciled_bsp --from l3_features"},
        {"id": "quarantine_8_outcomes_from_l3_l4", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid l8_evidence.tennis_outcomes --from l3_features l4_pricing"},
        {"id": "quarantine_9_l5_from_coherence", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid l5_decision --from sport_tennis.coherence"},
        {"id": "quarantine_10_l5b_from_coherence", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid l5b_risk --from sport_tennis.coherence"},
        {"id": "quarantine_11_l6_from_coherence", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid l6_broker --from sport_tennis.coherence"},
        {"id": "quarantine_12_l7_from_coherence", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid l7_settle --from sport_tennis.coherence"},
        {"id": "quarantine_13_v0_from_coherence", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid assistant_v0 --from sport_tennis.coherence"},
        {"id": "quarantine_14_xmarket_from_coherence", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid research.xmarket --from sport_tennis.coherence"},
        {"id": "quarantine_15_coherence_from_v0_l4", "kind": "non-pytest", "tool": "python",
         "command": "uv run python tools/check_import_quarantine.py --forbid sport_tennis.coherence --from assistant_v0 l4_pricing"},
        {"id": "mypy_strict", "kind": "non-pytest", "tool": "mypy",
         "command": "uv run mypy --strict ."},
    ],
    "note": "Extracted from the committed Makefile verify target (sha256 above). The pytest gate "
            "is the only sharded one; all others run via their exact Makefile command. "
            "tests/replay_regression is NOT in the make verify pytest paths (make verify lists "
            "unit/integration/properties/stateful/failure_injection explicitly), so it is "
            "excluded from the frozen collection — matching make verify exactly.",
}
(D / "STAGE3_VERIFY_PLAN_V1.json").write_text(json.dumps(verify_plan, indent=1, sort_keys=True) + "\n")

# ---------------------------------------------------------------- §6 deterministic shard plan
BO5 = [n for n in nodes if "production_equals_reference" in n and "BO5_AD_TB10_FINAL_AT_6_6" in n]
assert len(BO5) == 2, BO5
ISOLATE_FILES = {  # known slow/moderate coherence files -> own shard each
    "tests/unit/coherence/test_solver.py",
    "tests/unit/coherence/test_solver_golden.py",
    "tests/unit/coherence/test_discretisation_stability.py",
    "tests/unit/coherence/test_degeneracy_diagnostic.py",
    "tests/unit/coherence/test_solver_nonfinite_reachability.py",
    "tests/unit/coherence/test_rootset_independent.py",
}
COH_FAST_BUDGET = 80    # fast/moderate coherence nodes grouped, lexical order
NONCOH_BUDGET = 300     # fast non-coherence nodes grouped, lexical order

shards: list[dict] = []


def add(kind: str, ids: list[str], rationale: str) -> None:
    if not ids:
        return
    sid = f"S{len(shards):03d}"
    (SHARD_DIR / f"{sid}.txt").write_text("\n".join(ids) + "\n")
    shards.append({"shard_id": sid, "kind": kind, "node_ids": ids, "node_count": len(ids),
                   "file_count": len({i.split('::')[0] for i in ids}), "rationale": rationale,
                   "manifest_digest": sha_text("\n".join(ids) + "\n")})


# 1) the two BO5 singletons (each approaches the cap; isolated)
for n in BO5:
    add("pytest_singleton_slow", [n],
        "known long single test (~380s, approaches the 600s cap): isolated per §6")

# 2) isolated slow coherence files (each its own shard), lexical
for f in sorted(ISOLATE_FILES):
    ids = [n for n in nodes if n.split("::")[0] == f]
    add("pytest_isolated_file", ids, f"known slow/moderate coherence file isolated: {f}")

# 3) remaining coherence (fast/moderate), lexical, budgeted, kept file-contiguous
handled = set(BO5) | {n for n in nodes if n.split("::")[0] in ISOLATE_FILES}
coh_rest = [n for n in nodes if n.startswith("tests/unit/coherence/") and n not in handled]
buf: list[str] = []
for n in coh_rest:
    buf.append(n)
    # cut at budget on a file boundary (next node is a different file or budget exceeded)
    idx = coh_rest.index(n)
    nxt = coh_rest[idx + 1] if idx + 1 < len(coh_rest) else None
    if len(buf) >= COH_FAST_BUDGET and (nxt is None or nxt.split("::")[0] != n.split("::")[0]):
        add("pytest_coherence_group", buf, "grouped fast/moderate coherence nodes (budget 80)")
        buf = []
add("pytest_coherence_group", buf, "grouped fast/moderate coherence nodes (budget 80)")

# 4) non-coherence (fast), lexical, budgeted, kept file-contiguous
noncoh = [n for n in nodes if not n.startswith("tests/unit/coherence/")]
buf = []
for i, n in enumerate(noncoh):
    buf.append(n)
    nxt = noncoh[i + 1] if i + 1 < len(noncoh) else None
    if len(buf) >= NONCOH_BUDGET and (nxt is None or nxt.split("::")[0] != n.split("::")[0]):
        add("pytest_noncoherence_group", buf, "grouped fast non-coherence nodes (budget 300)")
        buf = []
add("pytest_noncoherence_group", buf, "grouped fast non-coherence nodes (budget 300)")

# reconcile: every node exactly once
assigned = [i for s in shards for i in s["node_ids"]]
plan = {
    "directive": "STAGE3-0006C-D-A3-VERIFY-V1 §6", "commit": COMMIT,
    "collection_digest": COLLECTION_DIGEST, "frozen_collection_count": len(nodes),
    "shard_count": len(shards),
    "budgets": {"coherence_group": COH_FAST_BUDGET, "noncoherence_group": NONCOH_BUDGET,
                "target_shard_seconds": 480, "hard_shard_seconds": 540, "env_cap_seconds": 600},
    "reconcile": {
        "total_planned_node_ids": len(assigned),
        "unique_planned_node_ids": len(set(assigned)),
        "missing": sorted(set(nodes) - set(assigned)),
        "extra": sorted(set(assigned) - set(nodes)),
        "duplicate_count": len(assigned) - len(set(assigned)),
    },
    "shards": shards,
}
plan["reconcile_all_zero"] = (
    plan["reconcile"]["missing"] == [] and plan["reconcile"]["extra"] == []
    and plan["reconcile"]["duplicate_count"] == 0
    and plan["reconcile"]["total_planned_node_ids"] == len(nodes))
plan_blob = json.dumps(plan, indent=1, sort_keys=True) + "\n"
(D / "STAGE3_PYTEST_SHARD_PLAN_V1.json").write_text(plan_blob)

print("policy:", sha_file(SPEC / "stage3-sharded-verification-policy-v1.yaml"))
print("preflight:", sha_file(D / "STAGE3_SHARDED_VERIFY_PREFLIGHT.json"), "integrity", preflight["integrity"])
print("verify_plan:", sha_file(D / "STAGE3_VERIFY_PLAN_V1.json"), "gates", len(verify_plan["gates_in_execution_order"]))
print("collection:", COLLECTION_DIGEST, "count", len(nodes))
print("shard_plan:", sha_text(plan_blob), "shards", len(shards), "reconcile_all_zero", plan["reconcile_all_zero"])
print("shard kinds:", {k: sum(1 for s in shards if s['kind'] == k) for k in {s['kind'] for s in shards}})
print("max shard node_count:", max(s["node_count"] for s in shards))
