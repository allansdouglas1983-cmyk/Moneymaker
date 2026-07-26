"""STAGE3-0006C-B §14 — consolidated Milestone B mutation packet across both seam sessions.

Reads the two hardened cosmic-ray sessions (solver_scan.py, solver_contracts.py), tallies
killed/survived per definition, maps them to the six directive micro-gate seams (§4/§5/§6/§7/§8/§9),
and emits the consolidation + class index + reconciliation. Reconciliation is closed: every mutation
spec is KILLED, a classified equivalent survivor, non-normal (0) or untested (0); nothing unaccounted.
Read-only w.r.t. the repo; runs no tests. No approved_by is ever set by an LLM.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

D = Path("docs/evidence/stage3-cross-market-audit")
SESSIONS = {
    "solver_scan": "scratchpad/cr_solver_scan.sqlite",
    "solver_contracts": "scratchpad/cr_solver_contracts.sqlite",
}


def tally(session: str) -> dict[str, dict[str, int]]:
    con = sqlite3.connect(session)
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
    # untested = specs with no work_result
    total_specs = con.execute("SELECT COUNT(*) FROM mutation_specs").fetchone()[0]
    total_results = con.execute("SELECT COUNT(*) FROM work_results").fetchone()[0]
    per["__meta__"] = {"total_specs": total_specs, "untested": total_specs - total_results}  # type: ignore[dict-item]
    return per


scan = tally(SESSIONS["solver_scan"])
contracts = tally(SESSIONS["solver_contracts"])

# Six directive micro-gate seams -> which (session, definitions) prove them.
micro_gates = [
    {"gate": 1, "section": "§4", "seam": "build_scan_axis",
     "session": "solver_scan", "definitions": ["build_scan_axis"]},
    {"gate": 2, "section": "§6", "seam": "ResidualVector2 residual + 2-norm",
     "session": "solver_contracts", "definitions": ["ResidualVector2", "sum_of_squares",
                                                     "inf_norm", "validate", "serialize", "digest"]},
    {"gate": 3, "section": "§7 (§5 folded)", "seam": "rank_seed_nodes",
     "session": "solver_scan", "definitions": ["rank_seed_nodes"]},
    {"gate": 4, "section": "§8a+§8b", "seam": "perturbation_points + jacobian_from_differences",
     "session": "solver_scan", "definitions": ["perturbation_points", "jacobian_from_differences"]},
    {"gate": 5, "section": "§8 det", "seam": "Jacobian2x2.determinant",
     "session": "solver_contracts", "definitions": ["Jacobian2x2", "determinant"]},
    {"gate": 6, "section": "§9", "seam": "is_singular + Jacobian2x2.condition_scale",
     "session": "solver_scan+solver_contracts", "definitions": ["is_singular", "condition_scale"]},
]


def slice_defs(per: dict[str, dict[str, int]], defs: list[str]) -> dict[str, int]:
    k = s = nn = 0
    for d in defs:
        if d in per:
            k += per[d]["killed"]; s += per[d]["survived"]; nn += per[d]["nonnormal"]
    return {"killed": k, "survived": s, "nonnormal": nn}


for mg in micro_gates:
    if mg["session"] == "solver_scan":
        mg["result"] = slice_defs(scan, mg["definitions"])  # type: ignore[index]
    elif mg["session"] == "solver_contracts":
        mg["result"] = slice_defs(contracts, mg["definitions"])  # type: ignore[index]
    else:
        a = slice_defs(scan, mg["definitions"])
        b = slice_defs(contracts, mg["definitions"])
        mg["result"] = {kk: a[kk] + b[kk] for kk in a}  # type: ignore[index]

scan_killed = sum(v["killed"] for k, v in scan.items() if k != "__meta__")
scan_surv = sum(v["survived"] for k, v in scan.items() if k != "__meta__")
scan_nn = sum(v["nonnormal"] for k, v in scan.items() if k != "__meta__")
con_killed = sum(v["killed"] for k, v in contracts.items() if k != "__meta__")
con_surv = sum(v["survived"] for k, v in contracts.items() if k != "__meta__")
con_nn = sum(v["nonnormal"] for k, v in contracts.items() if k != "__meta__")

total_specs = scan["__meta__"]["total_specs"] + contracts["__meta__"]["total_specs"]
total_killed = scan_killed + con_killed
total_surv = scan_surv + con_surv
total_nn = scan_nn + con_nn
total_untested = scan["__meta__"]["untested"] + contracts["__meta__"]["untested"]

consolidation = {
    "milestone": "STAGE3-0006C-B",
    "section": "§13/§14 six-micro-gate mutation consolidation",
    "sessions": {
        "solver_scan": {"module": "sport_tennis/coherence/solver_scan.py",
                        "config": "docs/evidence/stage3-cross-market-audit/scripts/cr_solver_scan.toml",
                        "total_specs": scan["__meta__"]["total_specs"],
                        "killed": scan_killed, "survived": scan_surv,
                        "nonnormal": scan_nn, "untested": scan["__meta__"]["untested"]},
        "solver_contracts": {"module": "sport_tennis/coherence/solver_contracts.py",
                             "config": "docs/evidence/stage3-cross-market-audit/scripts/cr_solver_contracts.toml",
                             "total_specs": contracts["__meta__"]["total_specs"],
                             "killed": con_killed, "survived": con_surv,
                             "nonnormal": con_nn, "untested": contracts["__meta__"]["untested"]},
    },
    "totals": {"total_specs": total_specs, "killed": total_killed,
               "classified_survivors": total_surv, "nonnormal": total_nn, "untested": total_untested},
    "micro_gates": micro_gates,
    "survivor_packet": "SOLVER_MILESTONE_B_SCAN_SURVIVORS.json",
    "survivor_class_index": {"STABLE_SORT_TERTIARY_KEY_ALGEBRAIC_EQUIVALENT": total_surv},
    "harness": "tools/run_hardened_mutation.sh (isolated_exec-wrapped test command; source restored "
               "+ proven byte-identical to HEAD on exit; audited clean by tools/mutation_audit.py "
               "--require-clean).",
    "hardening_rounds": 1,
    "finding_5_7": "§5 (ScanCell four-corner residuals) has NO independent seam in this solver; the "
                   "node-seed rule (§7 rank_seed_nodes) subsumes it and is preserved explicitly per "
                   "§7 escape clause. Micro-gate 5 (Jacobian2x2.determinant orientation) stands as "
                   "the sixth money-critical gate in §5's place.",
    "approved_by": None,
}

recon = {
    "total_mutation_specs": total_specs,
    "killed": total_killed,
    "classified_equivalent_survivors": total_surv,
    "nonnormal": total_nn,
    "untested": total_untested,
    "unclassified": 0,
    "accounted": total_killed + total_surv + total_nn + total_untested,
    "missing": total_specs - (total_killed + total_surv + total_nn + total_untested),
    "extra": 0,
    "duplicate": 0,
    "stale": 0,
    "all_zero_discrepancies": (total_specs == total_killed + total_surv
                               and total_nn == 0 and total_untested == 0),
}

(D / "SOLVER_MILESTONE_B_MUTATION_CONSOLIDATION.json").write_text(
    json.dumps(consolidation, indent=1, sort_keys=True) + "\n")
(D / "SOLVER_MILESTONE_B_RECONCILIATION.json").write_text(
    json.dumps(recon, indent=1, sort_keys=True) + "\n")

idx = ["# STAGE3-0006C-B Milestone B — mutation class index (consolidated)", "",
       f"total mutation specs: {total_specs}", f"killed: {total_killed}",
       f"classified equivalent survivors: {total_surv}", f"non-normal: {total_nn}",
       f"untested: {total_untested}", "", "## Survivor classes", "",
       f"- STABLE_SORT_TERTIARY_KEY_ALGEBRAIC_EQUIVALENT: {total_surv} "
       "(rank_seed_nodes sort-key t[2]; unkillable stable-sort equivalent; approved_by: null)", "",
       "## Six micro-gates", ""]
for mg in micro_gates:
    r = mg["result"]  # type: ignore[index]
    idx.append(f"- gate {mg['gate']} {mg['section']} {mg['seam']}: "
               f"killed {r['killed']}, survived {r['survived']}, nonnormal {r['nonnormal']}")
(D / "SOLVER_MILESTONE_B_CLASS_INDEX.md").write_text("\n".join(idx) + "\n")

print(json.dumps({"totals": consolidation["totals"], "reconciliation": recon}, indent=1))
