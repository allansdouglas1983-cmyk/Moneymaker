"""STAGE3-0006C-D-REV1 §4 — Milestone D pre-change root-semantics freeze.

Derives the solver's ACTUAL root-set semantics from executable source (never from comments), and
executes the §4/§9-mandated order-dependence audit against the REAL production ``_dedup`` on
constructed Root instances (read-only; no production change; no market data; no outcomes).
Emits SOLVER_MILESTONE_D_PRECHANGE.json.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from sport_tennis.coherence import solver as S

D = Path("docs/evidence/stage3-cross-market-audit")
ROOT = Path(".")


def sha256_file(p: str) -> str:
    return "sha256:" + hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()


def mk(pa: float, pb: float) -> S.Root:
    return S.Root(p_a=pa, p_b=pb, a_serves_first=True, residual=0.0, jacobian_det=1.0,
                  on_boundary=False)


# ---- EXECUTED order-dependence demonstration on the REAL production _dedup ------------------
A, B, C = mk(0.5, 0.5), mk(0.5009, 0.5), mk(0.5018, 0.5)
# pairwise Chebyshev distances: |A-B| = 9e-4 < 1e-3 (equivalent); |B-C| = 9e-4 (equivalent);
# |A-C| = 1.8e-3 >= 1e-3 (NOT equivalent) -> a tolerance chain (non-transitive relation).
chain_orders = {
    "A_B_C": [r.p_a for r in S._dedup([A, B, C])],
    "B_A_C": [r.p_a for r in S._dedup([B, A, C])],
    "C_B_A": [r.p_a for r in S._dedup([C, B, A])],
}
representative_orders = {
    "A_B": [r.p_a for r in S._dedup([A, B])],
    "B_A": [r.p_a for r in S._dedup([B, A])],
}
chain_counts = {k: len(v) for k, v in chain_orders.items()}
order_dependent = (len(set(map(tuple, chain_orders.values()))) > 1
                   or len(set(map(tuple, representative_orders.values()))) > 1)
count_changes_under_permutation = len(set(chain_counts.values())) > 1

freeze = {
    "milestone": "STAGE3-0006C-D-REV1",
    "section": "§4 pre-change root-semantics freeze",
    "commit": commit,
    "digests": {
        "solver.py": sha256_file("sport_tennis/coherence/solver.py"),
        "solver_contracts.py": sha256_file("sport_tennis/coherence/solver_contracts.py"),
        "solver_scan.py": sha256_file("sport_tennis/coherence/solver_scan.py"),
        "solver_iteration.py": sha256_file("sport_tennis/coherence/solver_iteration.py"),
        "golden_oracle": sha256_file("tests/unit/coherence/golden/solver_behaviour_golden.json"),
    },
    "existing_root_types": {
        "Root": "frozen dataclass (p_a, p_b, a_serves_first, residual=sqrt(r2), jacobian_det, "
                "on_boundary) — the existing RootCandidate; finite-only via the root gate",
        "ServerSolve": "frozen dataclass (a_serves_first, status, roots tuple) — per-assignment",
        "IdentificationResult": "frozen dataclass (status, roots tuple, per_server pair, domain, "
                                "line, fmt) — the public result",
    },
    "root_coordinate_representation": "float (p_a, p_b), produced by grid refinement + Newton "
                                      "polish, clamped into [lo, hi]",
    "root_comparison_metric": "Chebyshev / infinity norm on coordinates: "
                              "max(|p_a1-p_a2|, |p_b1-p_b2|)",
    "root_equivalence_tolerance": S._DEDUP_TOL,
    "comparison_boundary": "STRICT <: distance < _DEDUP_TOL merges; distance == _DEDUP_TOL keeps "
                           "both (solver.py _dedup)",
    "deduplication_algorithm": "greedy first-seen: iterate candidates in sequence order; keep a "
        "candidate iff its Chebyshev distance to EVERY already-kept root is >= _DEDUP_TOL "
        "(literally: not any(dist < tol)); the FIRST-SEEN representative of an equivalence "
        "neighbourhood is retained, later equivalents are discarded",
    "equivalence_relation_transitivity": "NOT transitive (tolerance relation): A~B and B~C do not "
                                          "imply A~C — demonstrated below",
    "order_dependence_audit": {
        "method": "executed against the REAL production _dedup with constructed Root instances",
        "tolerance": S._DEDUP_TOL,
        "chain_fixture": {"A": 0.5, "B": 0.5009, "C": 0.5018,
                          "pairwise": "|A-B|=9e-4 (equiv), |B-C|=9e-4 (equiv), "
                                      "|A-C|=1.8e-3 (NOT equiv)"},
        "chain_results_p_a_kept": chain_orders,
        "chain_root_counts": chain_counts,
        "representative_results_p_a_kept": representative_orders,
        "output_depends_on_candidate_order": order_dependent,
        "root_count_changes_under_permutation": count_changes_under_permutation,
        "public_status_impact": "a permutation that changes the kept-root count changes the "
            "public status (2 kept -> MULTIPLE_ROOTS; 1 kept -> IDENTIFIED/NON_IDENTIFIABLE/"
            "BOUNDARY_SOLUTION path)",
        "production_determinism_note": "the PRODUCTION pipeline feeds _dedup a DETERMINISTIC "
            "candidate order (rank_seed_nodes residual-norm/index ranking -> per-seed refinement "
            "-> _solve_one append order; identify unions sa-roots-then-sb-roots), so the public "
            "result is a deterministic function of public inputs and the golden is stable. The "
            "gap is SEMANTIC: the deduplicated root set is a function of the candidate SEQUENCE, "
            "not of the candidate SET.",
        "first_server_union_note": "identify's union dedup (sa roots then sb roots, same "
            "predicate) retains the A-serves-first representative whenever the two assignments "
            "produce equivalent roots — reversing evaluation order would retain the B-first "
            "representative (different float coordinates and a_serves_first provenance in the "
            "public output).",
    },
    "canonical_ordering": "NONE — roots appear in DISCOVERY ORDER (seed rank order within a "
        "solve; sa-then-sb within the union); no sort is applied to the public roots tuple "
        "(the golden test sorts for comparison, the solver does not)",
    "boundary_root_definition": "min(pa-lo, hi-pa, pb-lo, hi-pb) < _BOUNDARY_TOL "
                                f"({S._BOUNDARY_TOL}) — strict <, computed per root at "
                                "acceptance time",
    "mirror_handling": "NONE STRUCTURALLY: no mirror transformation, detection or classification "
        "exists anywhere in the solver; a mirror pair (p_a, p_b)/(1-p_a, 1-p_b) surfaces only "
        "generically as two roots -> MULTIPLE_ROOTS. (Module docstring commentary about mirror "
        "degeneracy describes the mathematics, not any implemented machinery.)",
    "root_count_logic": {
        "zero": "status NO_ROOT",
        "one": "NON_IDENTIFIABLE if abs(jacobian_det) < _JAC_TOL (strict); else "
               "BOUNDARY_SOLUTION if on_boundary; else IDENTIFIED (per-solve); identify: "
               "BOUNDARY_SOLUTION if the single union root is on_boundary else IDENTIFIED",
        "multiple": "MULTIPLE_ROOTS (per-solve: len(found) > 1 BEFORE the degeneracy check — "
                    "multiplicity dominates singularity per-root classification; identify: "
                    "NON_IDENTIFIABLE under EITHER assignment dominates, then MULTIPLE_ROOTS "
                    "under either, then the union path)",
    },
    "first_server_semantics": "both assignments solved independently (_solve_one twice); "
        "per_server preserves both verbatim; overall: NON_IDENTIFIABLE > MULTIPLE_ROOTS > union "
        "of roots from assignments with status in {IDENTIFIED, BOUNDARY_SOLUTION}, deduplicated; "
        "empty union -> NO_ROOT; single union root -> BOUNDARY_SOLUTION/IDENTIFIED; >1 union "
        "root -> FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD (never averaged, never merged beyond "
        "the dedup)",
    "serialization": "NONE built into the result types (frozen dataclasses only; the golden test "
                     "serializes ad hoc); no digest method exists on Root/ServerSolve/"
                     "IdentificationResult",
    "exception_behaviour": "CoherenceMathError on invalid domain/targets/line (validators) and "
                           "on math-layer refusals; no exception from iteration exhaustion",
    "golden_root_sets": "tests/unit/coherence/golden/solver_behaviour_golden.json — 6 identify "
                        "cases (IDENTIFIED x2, MULTIPLE_ROOTS x2, NON_IDENTIFIABLE, NO_ROOT)",
    "approved_by": None,
}

blob = json.dumps(freeze, indent=1, sort_keys=True) + "\n"
(D / "SOLVER_MILESTONE_D_PRECHANGE.json").write_text(blob)
print("order_dependent:", order_dependent,
      "| count_changes_under_permutation:", count_changes_under_permutation)
print("chain:", chain_orders)
print("representative:", representative_orders)
print("digest: sha256:" + hashlib.sha256(blob.encode()).hexdigest())
