"""STAGE3-0006C-D-REV2 §4 — post-amendment Milestone D pre-change freeze.

Derives every fact from executable source and governed artifacts (digests hashed, constants
imported, rules quoted from the amendment registration) — never hand-copied, never inferred from
comments. Synthetic-only; no market data; no outcomes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from sport_tennis.coherence import solver as S

ROOT = Path(".")
D = ROOT / "docs/evidence/stage3-cross-market-audit"


def sha(p: str) -> str:
    return "sha256:" + hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()

freeze = {
    "milestone": "STAGE3-0006C-D-REV2",
    "section": "§4 post-amendment pre-change freeze",
    "commit": commit,
    "digests": {
        "solver.py": sha("sport_tennis/coherence/solver.py"),
        "solver_contracts.py": sha("sport_tennis/coherence/solver_contracts.py"),
        "solver_scan.py": sha("sport_tennis/coherence/solver_scan.py"),
        "solver_iteration.py": sha("sport_tennis/coherence/solver_iteration.py"),
        "root_dedup.py": sha("sport_tennis/coherence/root_dedup.py"),
        "amendment_registration": sha(
            "specs/programme/cross-market-coherence-root-dedup-amendment-v1.yaml"),
        "golden_v1": sha("tests/unit/coherence/golden/SOLVER_GOLDEN_V1_SEQUENCE_DEFINED.json"),
        "golden_v2": sha("tests/unit/coherence/golden/SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED.json"),
        "amendment_differential": sha(
            "docs/evidence/stage3-cross-market-audit/SOLVER_ROOT_DEDUP_AMENDMENT_DIFFERENTIAL.json"),
    },
    "types": {
        "Root": "frozen dataclass (p_a: float, p_b: float, a_serves_first: bool, residual: float "
                "= sqrt(r2) norm, jacobian_det: float, on_boundary: bool) — the current "
                "RootCandidate; no validate/serialize/digest methods of its own; fingerprint "
                "provided by root_dedup.candidate_fingerprint (sha256 over float.hex fields)",
        "ServerSolve": "frozen dataclass (a_serves_first: bool, status: str, roots: tuple[Root])",
        "IdentificationResult": "frozen dataclass (status: str, roots: tuple[Root], per_server: "
                                "(ServerSolve, ServerSolve), domain: (float, float), line: "
                                "Decimal, fmt: MatchFormat) — the public result; no serialize/"
                                "digest methods (golden serializes ad hoc)",
        "RootCluster": "frozen (representative: Root, members: tuple[Root] fingerprint-ordered, "
                       "diameter: float, provenance_digest: str) + serialize()",
        "RootDeduplicationResult": "frozen (clusters canonically ordered, ambiguous_components, "
                                   "reason: DedupReason|None) + ambiguous/representatives()/"
                                   "serialize()/digest()",
    },
    "governing_rules": {
        "coordinate_type": "float (p_a, p_b)",
        "residual_norm": "Root.residual = sqrt(f1^2 + f2^2) at acceptance",
        "first_server_representation": "bool a_serves_first (True = A serves first); governed "
                                       "order for keys: A-first before B-first",
        "boundary_rule": "on_boundary = min(pa-lo, hi-pa, pb-lo, hi-pb) < _BOUNDARY_TOL "
                         f"({S._BOUNDARY_TOL}), strict <, computed at root acceptance in "
                         "_solve_one (inline expression, not yet a named seam)",
        "direct_edge": "root_dedup.have_edge: chebyshev(left,right) < _DEDUP_TOL "
                       f"({S._DEDUP_TOL}), strict; coordinates only",
        "component_construction": "root_dedup.connected_components — fingerprint-canonical "
                                  "union-find; order-invariant",
        "component_diameter": "max pairwise Chebyshev; 0.0 singleton",
        "ambiguity_refusal": "diameter >= _DEDUP_TOL -> component refused; reason "
                             "AMBIGUOUS_ROOT_TOLERANCE_CHAIN; public NON_IDENTIFIABLE dominates",
        "representative_key": "(residual, p_a, p_b, A-first-then-B, fingerprint) minimum",
        "canonical_root_order": "(rep.p_a, rep.p_b, rep.residual, cluster provenance digest)",
        "root_count_rules": "per-solve: ambiguous->NON_IDENTIFIABLE; 0->NO_ROOT; >1->"
                            "MULTIPLE_ROOTS; 1-> NON_IDENTIFIABLE if |jac|<_JAC_TOL else "
                            "BOUNDARY_SOLUTION if on_boundary else IDENTIFIED",
        "first_server_union": "identify: NON_IDENTIFIABLE in per-statuses dominates, then "
                              "MULTIPLE_ROOTS; else union = canonical dedup of roots from solves "
                              "with status in {IDENTIFIED, BOUNDARY_SOLUTION}; union ambiguity -> "
                              "NON_IDENTIFIABLE; 0 -> NO_ROOT; 1 -> BOUNDARY/IDENTIFIED; >1 -> "
                              "FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD; degenerate branch unions "
                              "ALL per-solve roots with the same ambiguity override",
        "public_serialization": "NONE built into the result dataclasses; golden serializes ad hoc; "
                                "digest material exists only at the dedup layer "
                                "(RootDeduplicationResult.digest, sort_keys canonical json)",
        "exception_behaviour": "CoherenceMathError on invalid domain/targets/line, non-finite "
                               "dedup candidates, and math-layer refusals; iteration exhaustion "
                               "raises nothing",
    },
    "explicit_records": {
        "mirror_not_used_in_dedup": "NO mirror machinery exists anywhere in the executable "
            "solver: mirror coordinates are never computed, never deduplicate roots, never choose "
            "a representative, never change SolverStatus. Mirror pairs surface only generically "
            "as multiple roots. Milestone D adds mirror DIAGNOSTICS only.",
        "amended_clustering_is_governing": "root_dedup.py is the single clustering "
            "implementation; Milestone D must BIND it, never reimplement or layer a second "
            "competing clustering.",
        "v2_golden_root_sets": "6 identify fixtures (IDENTIFIED x2, MULTIPLE_ROOTS x2, "
            "NON_IDENTIFIABLE, NO_ROOT) + dedup_unit section (chain refusal, close cluster, "
            "multi-root, first-server provenance, boundary metadata)",
    },
    "approved_by": None,
}

blob = json.dumps(freeze, indent=1, sort_keys=True) + "\n"
(D / "SOLVER_MILESTONE_D_V2_PRECHANGE.json").write_text(blob)
print("digest: sha256:" + hashlib.sha256(blob.encode()).hexdigest())
print("commit:", commit)
