"""STAGE3-0006C-C-REV1 §20 — SOLVER_MILESTONE_C_NOT_USED_FEATURES.json.

The seven REV1 §1 NOT_USED findings, each with source-line evidence (frozen solver.py at commit
383e1e8, lines 157-176 = the Newton polish), architecture implication, and confirmation that no
placeholder machinery was introduced. Plus the §14 registered-but-not-emitted status record and
the §10 separately-identified incidental non-finite behaviour (identified, NOT corrected).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

D = Path("docs/evidence/stage3-cross-market-audit")

EVIDENCE_BASE = ("frozen solver.py@383e1e8 _refine Newton polish (lines 157-176): the loop body "
                 "computes the residual, tests f1*f1+f2*f2 <= _ROOT_TOL*_ROOT_TOL, tests "
                 "is_singular(det, _NEWTON_SINGULAR), computes the full Cramer step, applies "
                 "_clamp(pa - da, lo, hi) / _clamp(pb - db, lo, hi), tests the 1e-15 stagnation "
                 "break, and UNCONDITIONALLY assigns pa, pb = na, nb. ")

FINDINGS = {
    "STEP_TOLERANCE_NOT_USED": {
        "source_line_evidence": "line 160: `if f1 * f1 + f2 * f2 <= _ROOT_TOL * _ROOT_TOL: break` "
            "— the ONLY convergence test; no step-norm term appears in it. Line 170's "
            "`abs(na - pa) < 1e-15 and abs(nb - pb) < 1e-15` is a stagnation TERMINATION, not a "
            "convergence-success criterion.",
        "architecture_implication": "The convergence seam (newton_converged) takes residual and "
            "tolerance only; no step_tolerance parameter or field exists anywhere.",
    },
    "DAMPING_SCHEDULE_NOT_USED": {
        "source_line_evidence": "lines 167-169: `da = (d22*f1 - d12*f2)/det; db = (-d21*f1 + "
            "d11*f2)/det; na, nb = _clamp(pa - da, lo, hi), _clamp(pb - db, lo, hi)` — the raw "
            "step is applied directly; no factor sequence exists in the module.",
        "architecture_implication": "No build_damping_schedule seam exists; solver_iteration.py "
            "contains no schedule construct.",
    },
    "DAMPING_FACTOR_NOT_USED": {
        "source_line_evidence": "line 169: `pa - da` (and `pb - db`) — the implicit multiplier is "
            "the constant 1.0 with no representation in code; no variable, constant or parameter "
            "named or acting as a damping factor exists.",
        "architecture_implication": "apply_step_clamped takes no factor parameter; the full step "
            "is the only step.",
    },
    "MAXIMUM_DAMPING_ATTEMPTS_NOT_USED": {
        "source_line_evidence": "the loop body (lines 158-172) contains exactly one step "
            "computation and one application per iteration; no retry counter exists.",
        "architecture_implication": "No IterationBudget field or seam parameter for damping "
            "attempts was created.",
    },
    "MULTI_FACTOR_LINE_SEARCH_NOT_USED": {
        "source_line_evidence": "no inner loop over factors exists between the step computation "
            "(lines 167-168) and the state update (line 172).",
        "architecture_implication": "The one-step transition is linear: residual -> convergence -> "
            "singularity -> step -> clamp -> stagnation -> advance. No search construct exists.",
    },
    "PER_STEP_IMPROVEMENT_ACCEPTANCE_NOT_USED": {
        "source_line_evidence": "line 172: `pa, pb = na, nb` executes UNCONDITIONALLY after the "
            "stagnation test; no residual comparison guards it. The only improvement comparison is "
            "line 174's FINAL `if newton_r < best_r` grid-versus-Newton selection.",
        "architecture_implication": "No step-acceptance seam exists; prefer_newton_candidate is a "
            "final selection, never a per-step gate.",
    },
    "FIRST_ACCEPTED_FACTOR_POLICY_NOT_USED": {
        "source_line_evidence": "with no damping factors (see DAMPING_FACTOR_NOT_USED) there is no "
            "factor ordering and no acceptance policy over factors.",
        "architecture_implication": "No transition field records an accepted factor; none exists "
            "to record.",
    },
}

payload = {
    "milestone": "STAGE3-0006C-C-REV1",
    "section": "§20 NOT_USED feature findings",
    "frozen_source_commit": "383e1e82508871c0271534aba008beec12a13601",
    "findings": {
        name: {**body,
               "evidence_context": EVIDENCE_BASE,
               "placeholder_machinery_introduced": False}
        for name, body in FINDINGS.items()
    },
    "confirmation": "No placeholder fields, parameters, constants, schedules, retry loops or "
                    "acceptance policies were added to production contracts or seams for any of "
                    "the seven findings (REV1 §1). solver_iteration.py exposes only the "
                    "genuinely-existing semantics.",
    "registered_but_not_emitted": {
        "NON_CONVERGED_STATUS_REGISTERED_BUT_NOT_EMITTED": "SolverStatus.NON_CONVERGED exists in "
            "the governed vocabulary (Milestone A registration) but is NOT emitted: iteration "
            "exhaustion simply ends the polish loop with no exception and no status; the point "
            "counts as a root only if its residual meets _ROOT_TOL in _solve_one. Mapping "
            "exhaustion to a status would be a governed contract amendment, not this refactor. "
            "The same applies to INVALID_TARGET / INVALID_DOMAIN / NONFINITE_ARITHMETIC (current "
            "behaviour raises CoherenceMathError for the first two; the third has no emit site).",
    },
    "separately_identified_incidental_behaviour": {
        "NONFINITE_PASSTHROUGH_INCIDENTAL": "If a residual or Jacobian evaluation ever produced a "
            "non-finite value mid-polish, the frozen behaviour is pass-through: the convergence "
            "and singularity comparisons are False against NaN, the clamp passes NaN through, the "
            "stagnation test is False, and the loop advances on a NaN point until exhaustion, "
            "after which the NaN residual norm can never win the strict final selection (grid "
            "point kept). This is frozen incidental behaviour, deliberately NOT corrected in this "
            "structural refactor (REV1 §10 clause); NewtonStep2.validate provides a non-finite "
            "refusal contract for diagnostic/test use only. Returned for separate founder review.",
    },
    "approved_by": None,
}

blob = json.dumps(payload, indent=1, sort_keys=True) + "\n"
(D / "SOLVER_MILESTONE_C_NOT_USED_FEATURES.json").write_text(blob)
print("digest: sha256:" + hashlib.sha256(blob.encode()).hexdigest())
