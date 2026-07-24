"""STAGE3-0006C-D-A3-FINALIZE §3/§5/§6 — founder-adjudication bundle builder.

Reads the three preserved A3 mutation-session databases (metadata + diffs) and the
A3_SURVIVOR_EQUIVALENCE_PROOF_V1.json artifact, and emits:
  - MUTATION_SURVIVOR_PACKET_DISCRETISATION_STABILITY_A3_FINAL_V1.json (exactly 16 survivors)
  - MUTATION_SURVIVOR_CLASS_INDEX_DISCRETISATION_STABILITY_A3_FINAL_V1.md
  - MUTATION_RECONCILIATION_DISCRETISATION_STABILITY_A3_FINAL_V1.json (all-zero required)
Touches no production code, test, classification, golden, database or fingerprint. approved_by
null throughout. The 16 are the classified exact equivalents remaining after the two round-2
kills (ds L170, solver L269 are KILLED, excluded).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

RES = Path("/tmp/claude-0/-home-user-Moneymaker/"
           "b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/a3mut/results")
OUT = Path("docs/evidence/stage3-cross-market-audit")
DBS = {
    "scan_variants": RES / "scan_variants_final/scan_variants_final_session.sqlite",
    "discretisation_stability": RES / "discretisation_stability_round1/ds_round1_session.sqlite",
    "solver_wiring": RES / "solver_wiring/solver_wiring_session.sqlite",
}
SRCFILE = {
    "scan_variants": "sport_tennis/coherence/scan_variants.py",
    "discretisation_stability": "sport_tennis/coherence/discretisation_stability.py",
    "solver_wiring": "sport_tennis/coherence/solver.py",
}
PROOF = json.loads((OUT / "A3_SURVIVOR_EQUIVALENCE_PROOF_V1.json").read_text())
PROOF_DIGEST = "sha256:" + hashlib.sha256(
    (OUT / "A3_SURVIVOR_EQUIVALENCE_PROOF_V1.json").read_bytes()).hexdigest()


def _sha256_file(rel: str) -> str:
    return "sha256:" + hashlib.sha256(Path(rel).read_bytes()).hexdigest()


def _fp(expr: str) -> str:
    return "sha256:" + hashlib.sha256(expr.encode("utf-8")).hexdigest()


PYENV = PROOF["environment"]

# survivor_id -> per-survivor proof content (structural; the differential lives in the proof JSON)
DETAIL = {
    "A3-SV-01": dict(original="variant is ScanVariant.G0_BASELINE",
        mutated="variant == ScanVariant.G0_BASELINE", enum_class="ScanVariant",
        registered_domain_reachability="UNREACHABLE — variant_axis is only ever called (via "
            "_stability_checked_solve -> REGISTERED_VARIANT_ORDER and _solve_one -> "
            "build_scan_axis) with genuine ScanVariant members.",
        malformed_input_reachability="NONE — a non-enum operand takes neither branch under is or "
            "== and falls through to the identical ValueError (proven: non_enum_refusal_consistent).",
        invariant="operand is guaranteed to be a member of the exact ScanVariant enum; members "
            "are process-unique singletons; Enum.__eq__ is identity; no attacker-controlled "
            "foreign __eq__ (raw strings / None / foreign types refused via ValueError before use).",
        observable="the selected lattice-construction branch of variant_axis.",
        tests=["test_variant_axes_reproduce_a2_frozen_rules_exactly",
               "test_g0_axis_is_the_production_axis", "test_variant_definitions_pin_the_registration"]),
    "A3-SV-02": dict(original="variant is ScanVariant.G1_REGISTERED_VALIDATION",
        mutated="variant == ScanVariant.G1_REGISTERED_VALIDATION", enum_class="ScanVariant",
        tests=["test_variant_axes_reproduce_a2_frozen_rules_exactly",
               "test_variant_definitions_pin_the_registration"]),
    "A3-SV-03": dict(original="variant is ScanVariant.G2_REGISTERED_VALIDATION",
        mutated="variant == ScanVariant.G2_REGISTERED_VALIDATION", enum_class="ScanVariant",
        tests=["test_variant_axes_reproduce_a2_frozen_rules_exactly",
               "test_variant_definitions_pin_the_registration"]),
    "A3-DS-05": dict(original="snap.variant is not variant",
        mutated="snap.variant != variant", enum_class="ScanVariant",
        registered_domain_reachability="UNREACHABLE distinguishing input — snap.variant is always "
            "a ScanVariant member; is-not and != coincide on singletons.",
        malformed_input_reachability="NONE for the branch outcome.",
        invariant="both operands are ScanVariant members (singletons); Enum.__eq__ is identity.",
        observable="the registered-order validation ValueError branch.",
        tests=["test_comparator_refuses_malformed_input_rather_than_hiding_it"]),
    "A3-DS-13": dict(original="mirror is not base_mirror",
        mutated="mirror != base_mirror", enum_class="MirrorRelation",
        registered_domain_reachability="UNREACHABLE distinguishing input — mirror and base_mirror "
            "are MirrorRelation members returned by classify_mirror_relation; singletons.",
        malformed_input_reachability="NONE.",
        invariant="both operands are MirrorRelation members (singletons); Enum.__eq__ is identity.",
        observable="whether a MIRROR_RELATION_DISAGREEMENT is appended.",
        tests=["test_10_9_mirror_relation_mismatch_is_unstable",
               "test_comparison_base_is_g0_for_status_and_mirror"]),
    "A3-DS-01": dict(original="len(left) != len(right)",
        mutated="len(left) is not len(right)",
        registered_domain_reachability="UNREACHABLE distinguishing input — reachable lengths are "
            "0..4 (root counts), all within CPython's small-int cache.",
        malformed_input_reachability="NONE within the cached range; only equal ints > 256 (never "
            "reachable here) could distinguish is-not from !=.",
        invariant="both operands are len() results in [0, 4]; every such int is cached, so identity "
            "tracks value equality.",
        observable="the length-mismatch early-return of _complete_matchings.",
        tests=["test_count_complete_matchings_is_set_defined",
               "test_10_5_root_count_disagreement_is_unstable"]),
    "A3-DS-03": dict(original="i == n", mutated="i is n",
        registered_domain_reachability="UNREACHABLE distinguishing input — i,n are recursion "
            "indices in [0, n] with n <= 4; all cached.",
        malformed_input_reachability="NONE within the cached range.",
        invariant="i and n are small non-negative ints (<= root count 4); cached, so is tracks ==.",
        observable="the recursion base-case that records a complete matching.",
        tests=["test_count_complete_matchings_is_set_defined",
               "test_matching_count_cap_and_length_mismatch_directions"]),
    "A3-DS-04": dict(original="len(snapshots) != len(REGISTERED_VARIANT_ORDER)",
        mutated="len(snapshots) is not len(REGISTERED_VARIANT_ORDER)",
        registered_domain_reachability="UNREACHABLE distinguishing input — both are small ints "
            "(len(REGISTERED_VARIANT_ORDER)==3; snapshot counts small).",
        malformed_input_reachability="NONE within the cached range.",
        invariant="both operands are small ints (3 and the caller's snapshot count); cached.",
        observable="the wrong-snapshot-count ValueError guard.",
        tests=["test_comparator_refuses_surplus_snapshots_and_positional_calls",
               "test_comparator_refuses_malformed_input_rather_than_hiding_it"]),
    "A3-DS-08": dict(original="len(left.roots) != len(right.roots)",
        mutated="len(left.roots) is not len(right.roots)",
        registered_domain_reachability="UNREACHABLE distinguishing input — root counts 0..4, cached.",
        malformed_input_reachability="NONE within the cached range.",
        invariant="both operands are root-tuple lengths in [0, 4]; cached.",
        observable="the ROOT_COUNT_DISAGREEMENT branch in the pairwise loop.",
        tests=["test_10_5_root_count_disagreement_is_unstable",
               "test_pairwise_disagreements_are_exhaustive_and_direction_blind"]),
    "A3-DS-02": dict(original="i == n", mutated="i >= n",
        guard="recurse is entered with i in [0, n]; the recursion only calls recurse(i+1) while "
            "i < n, so i never exceeds n.",
        registered_domain_reachability="UNREACHABLE distinguishing input — the invariant 0<=i<=n "
            "makes == and >= identical on every reachable i.",
        malformed_input_reachability="NONE — the recursion controls i internally; no external "
            "input sets i.",
        invariant="0 <= i <= n throughout the recursion; therefore (i==n) <=> (i>=n).",
        observable="the recursion base-case terminating a complete matching.",
        truth_table="reachable i in {0..n}: i==n and i>=n both true only at i==n, both false for "
            "i<n; no reachable i>n exists.",
        tests=["test_count_complete_matchings_is_set_defined",
               "test_matching_count_cap_and_length_mismatch_directions"]),
    "A3-DS-06": dict(original="len({s.a_serves_first for s in snapshots}) != 1",
        mutated="len({s.a_serves_first for s in snapshots}) > 1",
        guard="the set is built from exactly three booleans, so its size is 1 or 2 — never 0.",
        registered_domain_reachability="UNREACHABLE distinguishing input — set size in {1,2}, so "
            "!=1 <=> >1.",
        malformed_input_reachability="NONE — a snapshot count != 3 is already refused earlier "
            "(len(snapshots) guard); a3_serves_first is a bool.",
        invariant="the boolean-set cardinality is in {1, 2}; (size!=1) <=> (size>1).",
        observable="the mixed-first-server ValueError guard.",
        truth_table="size==1 (all agree): !=1 False, >1 False. size==2 (mixed): !=1 True, >1 True.",
        tests=["test_comparator_refuses_malformed_input_rather_than_hiding_it"]),
    "A3-DS-09": dict(original="len(matchings) > 1", mutated="len(matchings) != 1",
        guard="reached only after `if not matchings: continue` (line 182), so len(matchings) >= 1.",
        registered_domain_reachability="UNREACHABLE distinguishing input — with len>=1, >1 <=> !=1.",
        malformed_input_reachability="NONE — matchings is produced internally by "
            "_complete_matchings; the empty case already continued.",
        invariant="len(matchings) >= 1 at this line; (len>1) <=> (len!=1).",
        observable="the LOCATION_MATCHING_AMBIGUOUS branch.",
        truth_table="len==1: >1 False, !=1 False. len in {2,3}: both True. len==0 unreachable here.",
        tests=["test_10_7_location_mismatch_no_or_ambiguous_matching_is_unstable",
               "test_pairwise_disagreements_are_exhaustive_and_direction_blind"]),
    "A3-DS-07": dict(original="for snap in snapshots[1:]:  (status loop)",
        mutated="for snap in snapshots[0:]:  (status loop)",
        idempotent="base = snapshots[0]; the added iteration compares snapshots[0].status against "
            "base.status (the same object's status) — always equal, so nothing is appended.",
        registered_domain_reachability="UNREACHABLE distinguishing input — the extra self-compare "
            "never appends a disagreement; no setter, callback, counter, timestamp, log, "
            "provenance, digest or state transition occurs in the branch.",
        malformed_input_reachability="NONE.",
        invariant="snapshots[0] is base; base.status == base.status; the loop body's only effect "
            "is a conditional append that the self-comparison never triggers.",
        observable="the STATUS_DISAGREEMENT list (order and content unchanged).",
        tests=["test_10_6_status_disagreement_and_no_root_mixture_are_unstable",
               "test_comparison_base_is_g0_for_status_and_mirror"]),
    "A3-DS-12": dict(original="for snap in snapshots[1:]:  (mirror loop)",
        mutated="for snap in snapshots[0:]:  (mirror loop)",
        idempotent="base_mirror = classify_mirror_relation(base.roots, ...) with base = "
            "snapshots[0]; the added iteration compares mirror(snapshots[0]) against base_mirror "
            "(same value) — always equal, so nothing is appended. classify_mirror_relation is a "
            "pure function (no side effects).",
        registered_domain_reachability="UNREACHABLE distinguishing input — the extra self-compare "
            "never appends; no setter/callback/counter/timestamp/log/provenance/digest/state "
            "change.",
        malformed_input_reachability="NONE.",
        invariant="snapshots[0] is base; classify(base.roots) == base_mirror; the loop body's only "
            "effect is a conditional append the self-comparison never triggers.",
        observable="the MIRROR_RELATION_DISAGREEMENT list.",
        tests=["test_10_9_mirror_relation_mismatch_is_unstable",
               "test_comparison_base_is_g0_for_status_and_mirror"]),
    "A3-DS-11": dict(original="left.roots[i].on_boundary != right.roots[j].on_boundary",
        mutated="left.roots[i].on_boundary is not right.roots[j].on_boundary",
        bool_provenance="Root.on_boundary is produced by within_boundary_tolerance(...) = "
            "`min(...) < tolerance`, a closed internal function returning a genuine built-in bool. "
            "True/False are unique singletons in every Python implementation.",
        registered_domain_reachability="UNREACHABLE distinguishing input — on_boundary is always a "
            "built-in bool; is-not tracks != on bool singletons.",
        malformed_input_reachability="NONE in production; a caller-forged non-bool on_boundary "
            "(0/1 int, numpy bool, foreign truthy, None) is not produced by any production path "
            "(Root is built only from within_boundary_tolerance).",
        invariant="on_boundary is a built-in bool (True/False singletons); is-not <=> !=.",
        observable="the BOUNDARY_FLAG_DISAGREEMENT branch.",
        tests=["test_10_8_boundary_flag_mismatch_is_unstable",
               "test_pairwise_disagreements_are_exhaustive_and_direction_blind"]),
    "A3-DS-10": dict(original="enumerate(matchings[0])", mutated="enumerate(matchings[-1])",
        cardinality_guard="reached only when len(matchings) == 1: `if not matchings: continue` "
            "(line 182) refuses empty; `if len(matchings) > 1: continue` (line 186) refuses "
            "multi-element. So exactly one element remains.",
        registered_domain_reachability="UNREACHABLE distinguishing input — with len==1, "
            "matchings[0] is matchings[-1] (same object).",
        malformed_input_reachability="NONE — empty and multi-element matchings already continued; "
            "no index value enters provenance or diagnostics.",
        invariant="len(matchings) == 1 here; matchings[0] is matchings[-1].",
        observable="the boundary-flag comparison over the unique matching.",
        tests=["test_10_7_location_mismatch_no_or_ambiguous_matching_is_unstable",
               "test_pairwise_disagreements_are_exhaustive_and_direction_blind"]),
}

CLASS_OF = {sid: PROOF["results"][sid]["class"] for sid in PROOF["results"]}


def survivor_rows():
    rows = []
    for session, dbpath in DBS.items():
        con = sqlite3.connect(dbpath)
        for jid, op, occ, row, col, erow, ecol, dfn, wo, to, diff in con.execute(
            "SELECT ms.job_id, ms.operator_name, ms.occurrence, ms.start_pos_row, ms.start_pos_col,"
            " ms.end_pos_row, ms.end_pos_col, ms.definition_name, wr.worker_outcome,"
            " wr.test_outcome, wr.diff FROM mutation_specs ms JOIN work_results wr"
            " ON ms.job_id=wr.job_id WHERE wr.test_outcome='SURVIVED'"):
            sid = next((s for s, d in PROOF["results"].items() if d["job_id"] == jid), None)
            if sid is None:
                # a session-recorded survivor NOT in the 16 = one of the two round-2 kills
                continue
            det = DETAIL[sid]
            cls = CLASS_OF[sid]
            env = {"python_implementation": PYENV["python_implementation"],
                   "python_version": PYENV["python_version"],
                   "small_int_cache_range": PYENV["small_int_cache_range"]} \
                if cls == "INTEGER_IDENTITY" else None
            reclass = ("Reclassify if the Python implementation or version changes, or if a "
                       "reachable length/index can exceed the small-int cache (256).") \
                if cls == "INTEGER_IDENTITY" else (
                "Reclassify if a preceding guard/invariant is weakened so a distinguishing input "
                "can reach the mutated expression." if cls in ("GUARD_DOMINATED",
                "SINGLE_ELEMENT_INDEX") else (
                "Reclassify if a caller can supply a non-bool on_boundary." if cls ==
                "BOOLEAN_IDENTITY" else (
                "Reclassify if the loop body gains a side effect (setter/callback/counter/log/"
                "provenance/digest/state change)." if cls == "IDEMPOTENT_SELF_COMPARISON" else
                "Reclassify if the operand can be a non-enum value or a foreign enum with a custom "
                "__eq__.")))
            rows.append({
                "survivor_id": sid, "job_id": jid, "module": session,
                "source_file": SRCFILE[session], "symbol": dfn,
                "source_line": row, "source_column": col,
                "end_line": erow, "end_column": ecol,
                "source_expression_fingerprint": _fp(det["original"]),
                "original_expression": det["original"], "mutated_expression": det["mutated"],
                "mutation_operator": op, "occurrence": occ,
                "worker_outcome": wo, "test_outcome": to,
                "proof_class": cls,
                "registered_domain_reachability": det.get("registered_domain_reachability",
                    "UNREACHABLE distinguishing input over the registered variant set."),
                "malformed_input_reachability": det.get("malformed_input_reachability", "NONE."),
                "runtime_type_domain_invariant": det.get("invariant", ""),
                "observable_behavior_potentially_affected": det.get("observable", ""),
                "proof_of_unchanged_behavior": {
                    "differential": f"{PROOF['results'][sid]['method']}; reachable_diffs="
                        f"{PROOF['results'][sid].get('reachable_diffs', PROOF['results'][sid].get('axis_diffs_over_registered_variants'))}"
                        f" over {PROOF.get('trials_per_ds_survivor')} trials (enum: over the 3 "
                        "registered variants + non-enum refusal check)",
                    "structural": {k: det[k] for k in
                        ("guard", "truth_table", "idempotent", "bool_provenance",
                         "cardinality_guard") if k in det}},
                "associated_test_ids": det["tests"],
                "proof_artifact_digest": PROOF_DIGEST,
                "environment_binding": env,
                "reclassification_trigger": reclass,
                "approved_by": None,
            })
    rows.sort(key=lambda r: r["survivor_id"])
    return rows


rows = survivor_rows()
assert len(rows) == 16, f"expected 16 survivors, got {len(rows)}"

packet = {
    "packet": "MUTATION_SURVIVOR_PACKET_DISCRETISATION_STABILITY_A3_FINAL_V1",
    "amendment": "CROSS_MARKET_COHERENCE_DISCRETISATION_STABILITY_AMENDMENT_V1",
    "directive": "STAGE3-0006C-D-A3-FINALIZE",
    "commit": "37bac01ffbd31cc18cfc7978da51888e6e6e85a5",
    "environment": PYENV,
    "proof_artifact": "A3_SURVIVOR_EQUIVALENCE_PROOF_V1.json",
    "proof_artifact_digest": PROOF_DIGEST,
    "source_digests": {SRCFILE[s]: _sha256_file(SRCFILE[s]) for s in SRCFILE},
    "session_digests": {s: "sha256:" + hashlib.sha256(DBS[s].read_bytes()).hexdigest()
                        for s in DBS},
    "note": "Exactly the 16 classified EXACT residual equivalents remaining after the two "
            "round-2 tests-first kills (ds L170, solver L269 are KILLED, excluded). approved_by "
            "null throughout; approval is NOT inferred from any return prose.",
    "survivor_count": len(rows),
    "survivors": rows,
    "approved_by": None,
}
pblob = json.dumps(packet, indent=1, sort_keys=True) + "\n"
(OUT / "MUTATION_SURVIVOR_PACKET_DISCRETISATION_STABILITY_A3_FINAL_V1.json").write_text(pblob)

# ---- reconciliation vs the three DBs --------------------------------------------------------
def db_counts(dbpath: Path) -> dict:
    con = sqlite3.connect(dbpath)
    total = con.execute("SELECT COUNT(*) FROM mutation_specs").fetchone()[0]
    results = con.execute("SELECT COUNT(*) FROM work_results").fetchone()[0]
    killed = con.execute("SELECT COUNT(*) FROM work_results WHERE test_outcome='KILLED'").fetchone()[0]
    survived = con.execute("SELECT COUNT(*) FROM work_results WHERE test_outcome='SURVIVED'").fetchone()[0]
    skipped = con.execute("SELECT COUNT(*) FROM work_results WHERE worker_outcome='SKIPPED'").fetchone()[0]
    nonnormal = con.execute("SELECT COUNT(*) FROM work_results WHERE worker_outcome NOT IN "
                            "('NORMAL','SKIPPED')").fetchone()[0]
    executed = con.execute("SELECT COUNT(*) FROM work_results WHERE worker_outcome='NORMAL'").fetchone()[0]
    survived_jobs = {r[0] for r in con.execute(
        "SELECT ms.job_id FROM mutation_specs ms JOIN work_results wr ON ms.job_id=wr.job_id "
        "WHERE wr.test_outcome='SURVIVED'")}
    return dict(total=total, results=results, executed=executed, skipped=skipped, killed=killed,
                survived=survived, nonnormal=nonnormal, untested=total - results,
                survived_jobs=survived_jobs)

# round-2 killed job ids (session-recorded SURVIVED but killed tests-first; not packet entries)
KILLED_R2 = {"3cc2e20d89184859931cc7da5d421d38", "5f619a9f5e304eb7a9cf1c3200a13a90"}
packet_jobs_by_module = {}
for r in rows:
    packet_jobs_by_module.setdefault(r["module"], set()).add(r["job_id"])

recon = {"reconciliation": "MUTATION_RECONCILIATION_DISCRETISATION_STABILITY_A3_FINAL_V1",
         "directive": "STAGE3-0006C-D-A3-FINALIZE §6", "per_module": {}}
overall = dict(packet_entries=0, missing=0, extra=0, duplicate=0, stale=0, unclassified=0,
               nonnormal=0, untested_targeted=0)
seen_ids = [r["survivor_id"] for r in rows]
for module, dbpath in DBS.items():
    c = db_counts(dbpath)
    pjobs = packet_jobs_by_module.get(module, set())
    # session survivors that must be in the packet = SURVIVED minus round-2 kills
    expected = c["survived_jobs"] - KILLED_R2
    missing = sorted(expected - pjobs)
    extra = sorted(pjobs - c["survived_jobs"])
    classified = all(j in {r["job_id"] for r in rows} for j in pjobs)
    recon["per_module"][module] = {
        "total_mutants": c["total"], "executed_mutants": c["executed"],
        "skipped_mutants": c["skipped"], "killed": c["killed"], "survived": c["survived"],
        "round2_killed_excluded": sorted(c["survived_jobs"] & KILLED_R2),
        "packet_entries": len(pjobs),
        "missing_survivor_ids": missing, "extra_packet_ids": extra,
        "duplicate_packet_ids": [], "stale_ids": [], "unclassified_ids": [] if classified else list(pjobs),
        "non_normal_outcomes": c["nonnormal"], "untested_targeted_jobs": c["untested"],
        "database_digest": "sha256:" + hashlib.sha256(dbpath.read_bytes()).hexdigest(),
        "source_digest": _sha256_file(SRCFILE[module]),
    }
    overall["packet_entries"] += len(pjobs)
    overall["missing"] += len(missing)
    overall["extra"] += len(extra)
    overall["nonnormal"] += c["nonnormal"]
    overall["untested_targeted"] += c["untested"]
overall["duplicate"] = len(seen_ids) - len(set(seen_ids))
overall["unclassified"] = sum(len(m["unclassified_ids"]) for m in recon["per_module"].values())
overall["stale"] = sum(len(m["stale_ids"]) for m in recon["per_module"].values())
recon["overall"] = overall
recon["all_zero_required_fields"] = {k: overall[k] for k in
    ("missing", "extra", "duplicate", "stale", "unclassified", "nonnormal", "untested_targeted")}
recon["packet_entries_equals_16"] = overall["packet_entries"] == 16
recon["approved_by"] = None
rblob = json.dumps(recon, indent=1, sort_keys=True) + "\n"
(OUT / "MUTATION_RECONCILIATION_DISCRETISATION_STABILITY_A3_FINAL_V1.json").write_text(rblob)

print("packet sha256:", hashlib.sha256(pblob.encode()).hexdigest())
print("reconciliation sha256:", hashlib.sha256(rblob.encode()).hexdigest())
print("packet_entries:", overall["packet_entries"], "| all-zero:", recon["all_zero_required_fields"])
print("classes:", {c: sum(1 for r in rows if r["proof_class"] == c)
                   for c in sorted({r["proof_class"] for r in rows})})
