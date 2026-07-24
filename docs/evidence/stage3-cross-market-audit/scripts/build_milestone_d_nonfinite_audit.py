"""STAGE3-0006C-D-REV1 §1 — non-finite reachability audit artifact.

Source-derived call-path and invariant audit resolving NONFINITE_PASSTHROUGH_INCIDENTAL.
Verdict: STRUCTURALLY_UNREACHABLE_FROM_VALIDATED_PUBLIC_SOLVER. Emits
SOLVER_MILESTONE_D_NONFINITE_AUDIT.json. Read-only; runs no solver; synthetic-only.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

D = Path("docs/evidence/stage3-cross-market-audit")
commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()

AUDIT = {
    "1_public_input_validation": "identify() calls _validate_domain -> validate_domain "
        "(solver_contracts: refuses unless 0 < lo < hi < 1; every comparison with NaN/inf is "
        "False -> non-finite domains refused) and validate_targets (refuses unless both targets "
        "in [0,1]; NaN/inf refused the same way).",
    "2_target_validation": "validate_targets — inclusive [0,1] window; NaN/±inf refused "
        "(injection tests: test_identify_refuses_nonfinite_targets).",
    "3_parameter_domain_validation": "validate_domain — strict (0,1) window; NaN/±inf refused "
        "(test_identify_refuses_nonfinite_domain). The Decimal line is validated by pmf._validate_"
        "line at first residual evaluation: Decimal('NaN') is refused (NaN != NaN is True -> "
        "raise). NOTED QUIRK: Decimal('Infinity') passes the multiple-of-0.5 check (Inf*2 == "
        "Inf.to_integral_value()) but produces only FINITE outputs (over=0.0, under=1.0 — every "
        "Decimal(t) > Inf comparison is False); no non-finite float arises. Recorded, not "
        "corrected here.",
    "4_residual_generation": "FINITE BY CONSTRUCTION for validated inputs. _residual = "
        "match_distribution(...).match_win_a - tw and over_under(...).over - to. The entire chain "
        "(scoring.py, match.py, pmf.py) contains EXACTLY TWO divisions: (a) scoring.py:88 "
        "ff/total in _deuce_tail_first_win, guarded by `if total < _EPS: return 0.5` — division "
        "only when total >= _EPS > 0; (b) scoring.py:158 p*p/(p*p+q*q) with q=1-p — denominator "
        ">= 0.5 for all p in [0,1], never zero. No log/exp/pow/sqrt in the chain. All other "
        "operations are sums/products of probabilities in [0,1] over finite DP state spaces. "
        "Additionally pmf._validate_pmf -> scoring.check_normalized(sum) EXPLICITLY refuses "
        "NaN/inf mass (`if not math.isfinite(total) or ...: raise`) — a non-finite pmf cannot "
        "even be consumed by over_under.",
    "5_jacobian_generation": "Central differences of finite residuals over non-zero denominators: "
        "perturbation_points clamps to [0.01, 0.99]; ap-am can only vanish if both clamps bind "
        "simultaneously, which requires p >= 0.99-e AND p <= 0.01+e — empty for e=_JAC_EPS=1e-3. "
        "Finite numerators / non-zero finite denominators -> finite entries.",
    "6_singularity_and_nonfinite_checks": "is_singular(det, tol) = abs(det) < tol (Milestone B). "
        "For finite det this gates Newton exactly as frozen. (A hypothetical NaN det would test "
        "not-singular — but a NaN det is unreachable per items 4-5, and even under injection the "
        "next evaluation refuses: see item 9.)",
    "7_newton_step_construction": "propose_newton_step divides by det with |det| >= "
        "_NEWTON_SINGULAR=1e-10 guaranteed by the preceding is_singular gate; finite residuals & "
        "entries -> finite bounded deltas (no overflow: |entries| bounded by residual range / "
        "min denominator ~ 1e3, |deltas| <= ~1e14 << float max).",
    "8_undamped_candidate_construction": "pa - delta_a with finite operands -> finite; "
        "apply_step_clamped projects into [lo, hi].",
    "9_clamp_projection": "clamp_scalar receives only finite candidates on the validated path "
        "(items 4-8). Its NaN passthrough is INCIDENTAL and unreachable publicly. Injection proof "
        "that even a poisoned candidate is contained: a NaN candidate coordinate cannot be "
        "residual-evaluated — check_normalized raises typed CoherenceMathError on the NaN-mass "
        "pmf (test_injected_nan_jacobian_is_refused_by_the_math_layer). Refusal, not silent "
        "propagation.",
    "10_stagnation": "is_stagnant receives finite points on the validated path; injected NaN "
        "movement tests False (frozen) and the loop is budget-bounded — no infinite loop.",
    "11_root_candidate_construction": "A Root is constructed ONLY behind "
        "residual_norm2_within_tolerance(r2, _ROOT_TOL) — an inclusive <= comparison that is "
        "False for NaN/inf (test_root_gate_refuses_nonfinite_norms). A non-finite candidate can "
        "NEVER become a Root, regardless of how it might arise.",
    "12_final_grid_vs_newton_selection": "prefer_newton_candidate strict < is False for NaN/inf "
        "Newton norms (test_final_selection_refuses_nonfinite_newton_norms) — a poisoned Newton "
        "candidate can never displace the finite grid candidate.",
    "13_root_set_construction": "_dedup and the identify union operate only on Root instances, "
        "which item 11 proves are finite-only.",
    "14_public_serialization": "IdentificationResult/ServerSolve/Root are frozen dataclasses of "
        "the above finite-only values; the golden serialization contains no non-finite value "
        "(test_validated_path_public_output_is_entirely_finite).",
}

payload = {
    "milestone": "STAGE3-0006C-D-REV1",
    "section": "§1 non-finite reachability audit",
    "commit": commit,
    "finding": "STRUCTURALLY_UNREACHABLE_FROM_VALIDATED_PUBLIC_SOLVER",
    "invariant_chain": [
        "LAYER 1 — boundary refusal: validate_targets / validate_domain / _validate_line refuse "
        "every non-finite public input (NaN Decimal line included).",
        "LAYER 2 — finite arithmetic: the residual/Jacobian chain is finite-by-construction "
        "(two guarded divisions only; no transcendentals; bounded DP sums/products; "
        "check_normalized explicitly refuses non-finite pmf mass).",
        "LAYER 3 — evaluation refusal: a hypothetically non-finite candidate coordinate cannot "
        "even be residual-evaluated — check_normalized raises typed CoherenceMathError "
        "(refusal-by-exception, proven by injection).",
        "LAYER 4 — root gating: residual_norm2_within_tolerance and prefer_newton_candidate are "
        "False for non-finite norms, so no non-finite value can reach Root construction, "
        "deduplication, final selection output, or public serialization even under injection.",
    ],
    "call_path_audit": AUDIT,
    "injection_tests": "tests/unit/coherence/test_solver_nonfinite_reachability.py (17 tests: "
                       "NaN/±inf targets, domain, NaN line, injected NaN/inf residuals, injected "
                       "NaN Jacobian, gate invariants, validated-path output finiteness).",
    "direct_helper_status": "clamp_scalar's NaN/signed-zero passthrough remains INCIDENTAL "
        "behaviour of a private helper, NOT part of the public solver contract; it is unreachable "
        "with a non-finite argument from the validated public path (layers 1-3).",
    "noted_quirks_not_corrected": {
        "DECIMAL_INFINITY_LINE_ACCEPTED": "pmf._validate_line accepts Decimal('Infinity') (its "
            "multiple-of-0.5 check is vacuously satisfied); outputs remain finite (over=0.0, "
            "under=1.0). No non-finite propagation; a validation-tightening would be a separate "
            "governed amendment.",
    },
    "approved_by": None,
}

blob = json.dumps(payload, indent=1, sort_keys=True) + "\n"
(D / "SOLVER_MILESTONE_D_NONFINITE_AUDIT.json").write_text(blob)
print("finding:", payload["finding"])
print("digest: sha256:" + hashlib.sha256(blob.encode()).hexdigest())
