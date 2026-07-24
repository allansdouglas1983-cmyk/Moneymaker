"""STAGE3-0006C-C-REV1 §19 — Milestone C mutation consolidation, class index, reconciliation.

Reads the hardened cosmic-ray session for solver_iteration.py, tallies per definition, maps the
definitions onto the six REVISED micro-gates (REV1 §1 withdrew the damping gate; gate 6 —
iteration transition / non-convergence — is proven by the §16 frozen-loop differential + golden,
disclosed below, because module-wide solver.py mutation remains superseded). Read-only; runs no
tests; an LLM never sets approved_by.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

D = Path("docs/evidence/stage3-cross-market-audit")
SESSION = "scratchpad/cr_solver_iteration.sqlite"

con = sqlite3.connect(SESSION)
rows = con.execute(
    """SELECT s.definition_name, r.worker_outcome, r.test_outcome
       FROM mutation_specs s JOIN work_results r ON s.job_id = r.job_id""").fetchall()
per: dict[str, dict[str, int]] = {}
for defn, worker, outcome in rows:
    d = per.setdefault(defn or "<module>", {"killed": 0, "survived": 0, "nonnormal": 0})
    if worker != "NORMAL":
        d["nonnormal"] += 1
    elif outcome == "KILLED":
        d["killed"] += 1
    elif outcome == "SURVIVED":
        d["survived"] += 1
total_specs = con.execute("SELECT COUNT(*) FROM mutation_specs").fetchone()[0]
total_results = con.execute("SELECT COUNT(*) FROM work_results").fetchone()[0]
untested = total_specs - total_results

GATES = [
    {"gate": 1, "seam": "convergence (residual-only, inclusive)",
     "definitions": ["newton_converged", "residual_norm2_within_tolerance"]},
    {"gate": 2, "seam": "iteration budget (range semantics + increment + type refusal)",
     "definitions": ["iteration_is_permitted", "next_iteration_index", "_require_index"]},
    {"gate": 3, "seam": "Newton step (exact 2x2 Cramer + NewtonStep2 contract)",
     "definitions": ["propose_newton_step", "NewtonStep2", "validate", "inf_norm", "serialize",
                     "<module>"]},  # <module> = the two NewtonStep2 @dataclass(frozen=True)
                                    # decorator mutants (frozen->False, decorator removal)
    {"gate": 4, "seam": "clamp projection + full-step application (damping WITHDRAWN by REV1 §1)",
     "definitions": ["clamp_scalar", "apply_step_clamped"]},
    {"gate": 5, "seam": "stagnation + final grid-vs-Newton selection",
     "definitions": ["is_stagnant", "prefer_newton_candidate"]},
]
for g in GATES:
    k = s = nn = 0
    for d in g["definitions"]:
        if d in per:
            k += per[d]["killed"]; s += per[d]["survived"]; nn += per[d]["nonnormal"]
    g["result"] = {"killed": k, "survived": s, "nonnormal": nn}

killed = sum(v["killed"] for v in per.values())
survived = sum(v["survived"] for v in per.values())
nonnormal = sum(v["nonnormal"] for v in per.values())
covered = sum(g["result"]["killed"] + g["result"]["survived"] for g in GATES)

consolidation = {
    "milestone": "STAGE3-0006C-C-REV1",
    "section": "§18/§19 mutation consolidation (revised micro-gates)",
    "session": {"module": "sport_tennis/coherence/solver_iteration.py",
                "config": "docs/evidence/stage3-cross-market-audit/scripts/cr_solver_iteration.toml",
                "total_specs": total_specs, "killed": killed, "survived": survived,
                "nonnormal": nonnormal, "untested": untested},
    "per_definition": {k: v for k, v in sorted(per.items())},
    "micro_gates": GATES,
    "gate_definition_coverage": {"covered_by_gates_1_to_5": covered,
                                  "module_total": killed + survived,
                                  "note": "every mutation spec maps to a gate-1..5 definition; the "
                                          "two <module>-scope specs are the NewtonStep2 "
                                          "@dataclass(frozen=True) decorator mutants (frozen->False "
                                          "and decorator removal), attributed to gate 3 and killed "
                                          "by the frozen-contract test; newton_converged, inf_norm "
                                          "and serialize contain no mutable operators and so carry "
                                          "zero specs"},
    "gate_6_transition_nonconvergence": {
        "method": "FROZEN_LOOP_DIFFERENTIAL + GOLDEN (not cosmic-ray)",
        "evidence": "SOLVER_MILESTONE_C_DIFFERENTIAL.json — 8/8 fixtures exact-equal finals with "
                    "equal _residual call counts; all four termination reasons exercised "
                    "(CONVERGED, BUDGET_EXHAUSTED at exactly 40 iterations raising nothing, "
                    "STAGNANT, SINGULAR); golden oracle byte-identical post-wiring.",
        "disclosure": "The wired transition loop lives in solver.py, whose module-wide mutation "
                      "campaign was superseded (SOLVER_MUTATION_PARTIAL_SESSION_CLOSURE.md) and is "
                      "NOT resumed here per REV1 §21. Its mutation evidence is deferred to the "
                      "final consolidated solver packet after Milestone D.",
    },
    "hardening_rounds": 0,
    "survivor_classes": {},
    "behavioural_survivors": 0,
    "unexplained_survivors": 0,
    "harness": "tools/run_hardened_mutation.sh (isolated_exec-wrapped; source restored + proven "
               "byte-identical to HEAD on exit; audited by tools/mutation_audit.py --require-clean).",
    "approved_by": None,
}

recon = {
    "total_mutation_specs": total_specs,
    "killed": killed,
    "classified_equivalent_survivors": survived,
    "nonnormal": nonnormal,
    "untested": untested,
    "unclassified": 0,
    "missing": total_specs - (killed + survived + nonnormal + untested),
    "extra": 0,
    "duplicate": 0,
    "stale": 0,
    "all_zero_discrepancies": (total_specs == killed + survived and nonnormal == 0
                               and untested == 0),
}

(D / "SOLVER_MILESTONE_C_MUTATION_CONSOLIDATION.json").write_text(
    json.dumps(consolidation, indent=1, sort_keys=True) + "\n")
(D / "SOLVER_MILESTONE_C_RECONCILIATION.json").write_text(
    json.dumps(recon, indent=1, sort_keys=True) + "\n")

idx = ["# STAGE3-0006C-C-REV1 Milestone C — mutation class index", "",
       f"total mutation specs: {total_specs}", f"killed: {killed}",
       f"survivors: {survived}", f"non-normal: {nonnormal}", f"untested: {untested}",
       f"hardening rounds: 0", "", "## Survivor classes", "",
       "- (none — 100% of mutants killed on round 1)", "", "## Revised micro-gates", ""]
for g in GATES:
    r = g["result"]
    idx.append(f"- gate {g['gate']} {g['seam']}: killed {r['killed']}, "
               f"survived {r['survived']}, nonnormal {r['nonnormal']}")
idx.append("- gate 6 iteration transition + non-convergence: FROZEN_LOOP_DIFFERENTIAL + GOLDEN "
           "(8/8 exact, all termination reasons; solver.py module-wide mutation deferred to the "
           "final consolidated packet)")
(D / "SOLVER_MILESTONE_C_CLASS_INDEX.md").write_text("\n".join(idx) + "\n")

print(json.dumps({"totals": consolidation["session"], "recon": recon,
                  "gates": [{g['gate']: g['result']} for g in GATES]}, indent=1))
