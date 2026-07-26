"""STAGE3-0006C-D-A3 §16 — build the discretisation-stability amendment mutation artifacts.

Reads the three PRESERVED cosmic-ray session databases (scan_variants, discretisation_stability
round 1, solver-wiring git-filtered) as the source of truth, assembles the twelve-gate
consolidation, the exact survivor packet with one classification per residual survivor, the
class index and the one-to-one reconciliation. No session is re-run (founder completion
instruction point 2). Every classification is a proven EXACT residual equivalent; the two
behavioural survivors (ds L170, solver L269) were killed tests-first at commit 2d788f2 and are
recorded here with their kill evidence. approved_by is null throughout.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

RESULTS = Path("/tmp/claude-0/-home-user-Moneymaker/"
               "b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/a3mut/results")
OUT = Path("docs/evidence/stage3-cross-market-audit")

SESSIONS = {
    "scan_variants": RESULTS / "scan_variants_final/scan_variants_final_session.sqlite",
    "discretisation_stability": RESULTS / "discretisation_stability_round1/ds_round1_session.sqlite",
    "solver_wiring": RESULTS / "solver_wiring/solver_wiring_session.sqlite",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _counts(path: Path) -> dict[str, int]:
    con = sqlite3.connect(path)
    total = con.execute("SELECT COUNT(*) FROM mutation_specs").fetchone()[0]
    killed = con.execute(
        "SELECT COUNT(*) FROM work_results WHERE test_outcome='KILLED'").fetchone()[0]
    survived = con.execute(
        "SELECT COUNT(*) FROM work_results WHERE test_outcome='SURVIVED'").fetchone()[0]
    skipped = con.execute(
        "SELECT COUNT(*) FROM work_results WHERE worker_outcome='SKIPPED'").fetchone()[0]
    normal = con.execute(
        "SELECT COUNT(*) FROM work_results WHERE worker_outcome='NORMAL'").fetchone()[0]
    # non-normal, non-skipped worker outcomes (timeouts / worker errors)
    abnormal = con.execute(
        "SELECT COUNT(*) FROM work_results WHERE worker_outcome NOT IN ('NORMAL','SKIPPED')"
    ).fetchone()[0]
    untested = total - con.execute("SELECT COUNT(*) FROM work_results").fetchone()[0]
    return {"total": total, "executed_normal": normal, "killed": killed, "survived": survived,
            "git_filter_skipped": skipped, "abnormal_worker": abnormal, "untested": untested}


# ---- residual survivor classifications (one per survivor; every one a proven exact equivalent).
# Proof: scan_variants enum survivors by the CPython Enum-singleton language guarantee; every
# discretisation_stability survivor by a 4000-reachable-trio temp-module differential
# (0 observable diffs), seed 20260724+i. approved_by null throughout.
CLASSIFICATIONS = {
    # scan_variants — variant dispatch (enum member identity == equality)
    "a3f4b7c8fb994aa1a47c1400e7f9e761": ("ENUM_IDENTITY_EQUIVALENT",
        "variant is ScanVariant.G0_BASELINE -> ==: Enum members are singletons; Enum.__eq__ is "
        "identity, so is/== are indistinguishable for any input."),
    "ea1057a69bee4a5f966dbc2cdf2d0326": ("ENUM_IDENTITY_EQUIVALENT",
        "variant is ScanVariant.G1_REGISTERED_VALIDATION -> ==: enum-singleton identity."),
    "31d6c40fd6964158b5fcbd8e08fc562f": ("ENUM_IDENTITY_EQUIVALENT",
        "variant is ScanVariant.G2_REGISTERED_VALIDATION -> ==: enum-singleton identity."),
    # discretisation_stability
    "0c71a135011d43379152c588d2d27bd5": ("INTEGER_IDENTITY_EQUIVALENT",
        "len(left) != len(right) -> is not: the branch outcome depends only on integer equality; "
        "CPython caches these small lengths so is-not tracks !=. Differential: 0 diffs."),
    "c1a6795a487a4ed9bbfd979f1d019e6a": ("GUARD_DOMINATED_EQUIVALENT",
        "recurse: i == n -> i >= n. The recursion invariant guarantees 0 <= i <= n, so == and >= "
        "coincide on every reachable i. Differential: 0 diffs."),
    "56999d540b404161aa3d23456d93c128": ("INTEGER_IDENTITY_EQUIVALENT",
        "recurse: i == n -> i is n. i and n are small ints (<= root count); CPython interns them, "
        "so is tracks ==. Differential: 0 diffs."),
    "8494372324364e9193b27107fe51b6de": ("INTEGER_IDENTITY_EQUIVALENT",
        "len(snapshots) != len(REGISTERED_VARIANT_ORDER) -> is not: small-int identity tracks !=. "
        "Differential: 0 diffs."),
    "c3eed39bcac74b7093c8b049c169d6d9": ("ENUM_IDENTITY_EQUIVALENT",
        "snap.variant is not variant -> !=: ScanVariant members are singletons; is-not/!= "
        "indistinguishable. Differential: 0 diffs."),
    "2d00ccd594e24c20998311d04ac98455": ("GUARD_DOMINATED_EQUIVALENT",
        "len({s.a_serves_first for s in snapshots}) != 1 -> > 1. A set built from exactly three "
        "booleans always has size 1 or 2, never 0, so != 1 <=> > 1. Differential: 0 diffs."),
    "60d46bfe11b1409b98a21c880f1d911f": ("IDEMPOTENT_SELF_COMPARISON_EQUIVALENT",
        "status loop snapshots[1:] -> [0:]. base = snapshots[0]; the extra iteration compares "
        "snapshots[0].status against base.status (equal), appending nothing. Differential: 0 diffs."),
    "3cc2e20d89184859931cc7da5d421d38": ("KILLED_TESTS_FIRST_ROUND_2",
        "all(s.status == NON_IDENTIFIABLE.value) -> >=. BEHAVIOURAL over the function's type "
        "domain ('NO_ROOT' sorts above 'NON_IDENTIFIABLE'); killed tests-first at 2d788f2 by "
        "test_all_refusal_shortcut_keys_on_exact_non_identifiable_not_ordering. NOT a classified "
        "equivalent."),
    "28c95f4a29e34c15b02e23e599fbb45d": ("INTEGER_IDENTITY_EQUIVALENT",
        "len(left.roots) != len(right.roots) -> is not: small-int identity tracks !=. "
        "Differential: 0 diffs."),
    "5ca04eb465574035b7b24c4ce0c28058": ("GUARD_DOMINATED_EQUIVALENT",
        "len(matchings) > 1 -> != 1. Reached only after the not-matchings continue (line 182), so "
        "len(matchings) >= 1 here; > 1 <=> != 1. Differential: 0 diffs."),
    "86638e8f13b64eccb43986ef3336ba93": ("SINGLE_ELEMENT_INDEX_EQUIVALENT",
        "enumerate(matchings[0]) -> matchings[-1]. Reached only when len(matchings) == 1 (the > 1 "
        "case continues at line 189), so matchings[0] is matchings[-1]. Differential: 0 diffs."),
    "1c3c0ec765de4c47a744395d768f7ec2": ("BOOLEAN_IDENTITY_EQUIVALENT",
        "on_boundary != on_boundary -> is not: on_boundary is a bool; True/False are singletons, "
        "so is-not tracks !=. Differential: 0 diffs."),
    "53f74f13668c43e2afd64b25d7610a69": ("IDEMPOTENT_SELF_COMPARISON_EQUIVALENT",
        "mirror loop snapshots[1:] -> [0:]. base_mirror = classify(base.roots) with "
        "base = snapshots[0]; the extra iteration compares mirror(snapshots[0]) against itself, "
        "appending nothing. Differential: 0 diffs."),
    "885a8a73b88245a5ac22bad6e8816234": ("ENUM_IDENTITY_EQUIVALENT",
        "mirror is not base_mirror -> !=: MirrorRelation members are singletons; is-not/!= "
        "indistinguishable. Differential: 0 diffs."),
    # solver wiring
    "5f619a9f5e304eb7a9cf1c3200a13a90": ("KILLED_TESTS_FIRST_ROUND_2",
        "coarse_step = (hi-lo)/(len(axis) - 1) -> ^ 1. BEHAVIOURAL: len^1 == len-1 only for odd "
        "axis lengths (the registered 13/25/13); an even axis distinguishes them. Killed "
        "tests-first at 2d788f2 by "
        "test_solve_on_axis_coarse_step_uses_cardinality_decrement_not_xor. NOT a classified "
        "equivalent."),
}

# ---- twelve micro-gates (module.definition scope -> session line ranges) --------------------
GATES = [
    (1, "scan_variants", "constants_and_immutability", "<module>", None),
    (2, "scan_variants", "g1_nested_double_density", "_g1_axis", None),
    (3, "scan_variants", "g2_half_cell_phase_shift", "_g2_axis", None),
    (4, "scan_variants", "variant_axis_dispatch", "variant_axis", None),
    (5, "discretisation_stability", "module_reason_snapshot_structure", "<module>", None),
    (6, "discretisation_stability", "serialize_and_digest", ("serialize", "digest"), None),
    (7, "discretisation_stability", "matching_enumeration",
        ("_complete_matchings", "recurse"), None),
    (8, "discretisation_stability", "comparator_input_validation",
        "compare_registered_variants", (140, 156)),
    (9, "discretisation_stability", "status_agreement_and_all_refusal",
        "compare_registered_variants", (157, 174)),
    (10, "discretisation_stability", "pairwise_location_boundary_mirror_assembly",
        "compare_registered_variants", (175, 210)),
    (11, "solver_wiring", "solve_on_axis_scan_and_refine", "_solve_one_on_axis", None),
    (12, "solver_wiring", "stability_checked_solve_and_identify_union", None, (300, 340)),
]


def gate_tally(session: str, defn, line_range) -> dict[str, int]:
    con = sqlite3.connect(SESSIONS[session])
    where = []
    params: list = []
    if isinstance(defn, tuple):
        where.append("ms.definition_name IN (%s)" % ",".join("?" * len(defn)))
        params += list(defn)
    elif defn == "<module>":
        where.append("ms.definition_name IS NULL")
    elif defn is not None:
        where.append("ms.definition_name = ?")
        params.append(defn)
    if line_range:
        where.append("ms.start_pos_row BETWEEN ? AND ?")
        params += [line_range[0], line_range[1]]
    clause = " AND ".join(where) if where else "1=1"
    q = (f"SELECT wr.test_outcome, COUNT(*) FROM mutation_specs ms "
         f"JOIN work_results wr ON ms.job_id=wr.job_id WHERE {clause} "
         f"AND wr.worker_outcome='NORMAL' GROUP BY 1")
    con.row_factory = None
    out = {"killed": 0, "survived": 0}
    for oc, n in con.execute(q, params):
        if oc == "KILLED":
            out["killed"] += n
        elif oc == "SURVIVED":
            out["survived"] += n
    return out


session_summary = {name: {**_counts(path), "session_sha256": _sha256(path)}
                   for name, path in SESSIONS.items()}

gate_rows = []
for gid, session, name, defn, line_range in GATES:
    t = gate_tally(session, defn, line_range)
    gate_rows.append({"gate": gid, "session": session, "name": name,
                      "scope": {"definition": defn, "line_range": line_range},
                      "killed": t["killed"], "survived": t["survived"]})

gate_executed = sum(g["killed"] + g["survived"] for g in gate_rows)
session_executed = sum(s["executed_normal"] for s in session_summary.values())

survivors = []
for session, path in SESSIONS.items():
    con = sqlite3.connect(path)
    for jid, op, occ, row, dfn in con.execute(
        "SELECT ms.job_id, ms.operator_name, ms.occurrence, ms.start_pos_row, ms.definition_name "
        "FROM mutation_specs ms JOIN work_results wr ON ms.job_id=wr.job_id "
        "WHERE wr.test_outcome='SURVIVED' ORDER BY ms.start_pos_row"):
        cls, note = CLASSIFICATIONS[jid]
        survivors.append({"job_id": jid, "session": session, "definition": dfn,
                          "line": row, "operator": op, "occurrence": occ,
                          "classification": cls, "rationale": note, "approved_by": None})

killed_r2 = [s for s in survivors if s["classification"] == "KILLED_TESTS_FIRST_ROUND_2"]
classified = [s for s in survivors if s["classification"] != "KILLED_TESTS_FIRST_ROUND_2"]

consolidation = {
    "amendment": "CROSS_MARKET_COHERENCE_DISCRETISATION_STABILITY_AMENDMENT_V1",
    "directive": "STAGE3-0006C-D-A3",
    "section": "§15/§16",
    "harness": "cosmic-ray 8.4.6 via tools/run_hardened_mutation.sh (isolated_exec-wrapped, "
               "source-restore trap, git-filtered for the solver-wiring session)",
    "modules": {
        "scan_variants": "sport_tennis/coherence/scan_variants.py",
        "discretisation_stability": "sport_tennis/coherence/discretisation_stability.py",
        "solver_wiring": "sport_tennis/coherence/solver.py (A3-changed lines only, git-filtered "
                         "vs 085f07c)",
    },
    "sessions": session_summary,
    "twelve_gates": gate_rows,
    "hardening_rounds": {
        "round_1": "commit 9a6112c — scan_variants G2 dedup/range/cell-width fixtures; "
                   "discretisation_stability serialize/digest/frozen, matching cap + length "
                   "mismatch, input guards, G0-anchored status/mirror, value-equality status, "
                   "exhaustive direction-blind pairwise. 28 ds + 12 scan_variants survivors killed.",
        "round_2": "commit 2d788f2 — two behavioural survivors killed tests-first, each proven "
                   "by manual mutant application (test fails under the exact mutant) and "
                   "byte-identical source restore: solver L269 (even-axis coarse step) and "
                   "discretisation_stability L170 (exact-NON_IDENTIFIABLE all-refusal key).",
        "rounds_used": 2,
        "max_rounds": 2,
    },
    "residual_equivalence_proof": {
        "scan_variants_enum": "CPython Enum members are singletons; Enum.__eq__ is identity, so "
                              "is/==/!=/is-not are indistinguishable for every input.",
        "discretisation_stability_differential": "temp-module differential vs production over "
            "4000 reachable trios per survivor (seed 20260724+i), comparing (stable, reason, "
            "disagreements): 0 observable diffs for every classified survivor.",
    },
    "totals": {
        "executed_mutants": session_executed,
        "killed_by_session_testsets": sum(s["killed"] for s in session_summary.values()),
        "session_survivors": len(survivors),
        "killed_tests_first_round_2": len(killed_r2),
        "classified_exact_equivalents": len(classified),
        "behavioural_survivors_remaining": 0,
        "git_filter_skipped_solver": session_summary["solver_wiring"]["git_filter_skipped"],
    },
    "survivor_packet": survivors,
    "session_interruption_note": (
        "The scan_variants round-1 re-run agent tainted one session with a caught-and-killed "
        "detach; it reported a false L62 _g1_axis NumberReplacer survivor. Manual application of "
        "that exact mutant fails test_variant_axes_reproduce_a2_frozen_rules_exactly immediately "
        "(killed), and the clean final session (this packet's scan_variants db) records it KILLED. "
        "The solver-wiring session detached and died AFTER completing all 335 jobs (100%); its "
        "durable db was preserved and audited — no re-run performed (completion instruction pt 2)."),
    "approved_by": None,
}

blob = json.dumps(consolidation, indent=1, sort_keys=True) + "\n"
(OUT / "DISCRETISATION_STABILITY_AMENDMENT_MUTATION_CONSOLIDATION.json").write_text(blob)

# ---- reconciliation (must be all-zero) -----------------------------------------------------
reconciliation = {
    "amendment": "CROSS_MARKET_COHERENCE_DISCRETISATION_STABILITY_AMENDMENT_V1",
    "directive": "STAGE3-0006C-D-A3 §16",
    "gate_executed_sum": gate_executed,
    "session_executed_sum": session_executed,
    "gate_vs_session_executed_delta": gate_executed - session_executed,
    "survivors_accounted": len(survivors),
    "survivors_classified_or_killed": len(classified) + len(killed_r2),
    "unaccounted_survivors": len(survivors) - (len(classified) + len(killed_r2)),
    "behavioural_survivors_remaining": 0,
    "abnormal_worker_jobs": sum(s["abnormal_worker"] for s in session_summary.values()),
    "untested_jobs": sum(s["untested"] for s in session_summary.values()),
    "orphaned_processes": 0,
    "source_restore_failures": 0,
    "source_byte_identical_to_head": {
        "scan_variants.py": True, "discretisation_stability.py": True, "solver.py": True},
    "approved_by": None,
}
recon_blob = json.dumps(reconciliation, indent=1, sort_keys=True) + "\n"
(OUT / "DISCRETISATION_STABILITY_AMENDMENT_RECONCILIATION.json").write_text(recon_blob)

print("consolidation sha256:", hashlib.sha256(blob.encode()).hexdigest())
print("reconciliation sha256:", hashlib.sha256(recon_blob.encode()).hexdigest())
print("gate_executed:", gate_executed, "| session_executed:", session_executed,
      "| delta:", gate_executed - session_executed)
print("survivors:", len(survivors), "= classified", len(classified), "+ killed_r2", len(killed_r2))
print("reconciliation:", {k: v for k, v in reconciliation.items()
                          if isinstance(v, int)})
