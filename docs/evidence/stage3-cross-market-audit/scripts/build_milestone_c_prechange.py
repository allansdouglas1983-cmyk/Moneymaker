"""STAGE3-0006C-C §3 — Milestone C pre-change freeze.

Derives the solver's iteration/convergence/Newton/domain semantics by IMPORTING the constants and
HASHING the sources (never hand-copying), and records the exact current behaviour — including the
directive-assumed constructs that DO NOT EXIST, recorded as explicit NOT_USED sentinels with
source-line proof (never fabricated). Synthetic-only; reads no market data and no outcomes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from sport_tennis.coherence import solver as S

ROOT = Path(".")
D = ROOT / "docs/evidence/stage3-cross-market-audit"


def sha256_file(p: str) -> str:
    return "sha256:" + hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()

freeze = {
    "milestone": "STAGE3-0006C-C",
    "section": "§3 pre-change freeze",
    "commit": commit,
    "digests": {
        "solver.py": sha256_file("sport_tennis/coherence/solver.py"),
        "solver_contracts.py": sha256_file("sport_tennis/coherence/solver_contracts.py"),
        "solver_scan.py": sha256_file("sport_tennis/coherence/solver_scan.py"),
        "golden_oracle": sha256_file("tests/unit/coherence/golden/solver_behaviour_golden.json"),
    },
    # ---- constants imported from the live module (not transcribed) --------------------------
    "convergence_constants": {
        "_ROOT_TOL": S._ROOT_TOL,
        "_NEWTON_SINGULAR": S._NEWTON_SINGULAR,
        "_JAC_TOL": S._JAC_TOL,
        "_BOUNDARY_TOL": S._BOUNDARY_TOL,
        "_DEDUP_TOL": S._DEDUP_TOL,
    },
    "iteration_constants": {
        "_NEWTON_ITERS": S._NEWTON_ITERS,
        "_REFINE_LEVELS": S._REFINE_LEVELS,
        "_REFINE_K": S._REFINE_K,
        "_REFINE_SHRINK": S._REFINE_SHRINK,
    },
    # ---- exact current Newton-polish semantics (solver.py _refine, lines 157-176 at commit) --
    "newton_polish_semantics": {
        "start_point": "grid refinement result (best_a, best_b)",
        "iteration_loop": "for _ in range(_NEWTON_ITERS) -> counter starts 0, increments +1, "
                          "cap _NEWTON_ITERS=40; the loop index is UNUSED in any decision",
        "convergence_rule": "f1*f1 + f2*f2 <= _ROOT_TOL * _ROOT_TOL  (residual 2-norm-squared, "
                            "INCLUSIVE <=, residual-only, checked at loop TOP before stepping)",
        "convergence_uses_step_norm": False,
        "convergence_uses_and_or": "n/a (single residual-norm scalar comparison, no AND/OR)",
        "singularity_break": "is_singular(det, _NEWTON_SINGULAR) -> break (Milestone-B seam; "
                             "leaves grid estimate)",
        "newton_step": "da = (d22*f1 - d12*f2)/det ; db = (-d21*f1 + d11*f2)/det  "
                       "(exact 2x2 solve; d11=d_mo_d_a, d21=d_tg_d_a, d12=d_mo_d_b, d22=d_tg_d_b)",
        "step_application": "na, nb = _clamp(pa - da, lo, hi), _clamp(pb - db, lo, hi)  "
                            "-> full step (factor 1.0), then PROJECTED to [lo,hi] by _clamp",
        "stagnation_break": "if abs(na - pa) < 1e-15 and abs(nb - pb) < 1e-15: break  "
                            "(movement termination; AND; strict <; threshold 1e-15)",
        "state_update": "pa, pb = na, nb  (UNCONDITIONAL; the clamped full step is always taken; "
                        "there is NO per-step residual-improvement acceptance)",
        "final_selection": "newton_r = _r2(_residual(pa,pb,...)); return (pa,pb,newton_r) if "
                           "newton_r < best_r else (best_a,best_b,best_r)  (strict <; the ONLY "
                           "residual-improvement comparison; a FINAL selection, not step gating)",
        "non_convergence_behaviour": "loop simply ends after _NEWTON_ITERS; NO exception is "
                                     "raised; the point becomes a Root only if r2 <= _ROOT_TOL^2 "
                                     "in _solve_one, else contributes nothing",
    },
    # ---- directive-assumed constructs that DO NOT EXIST (recorded, never added) --------------
    "not_used_findings": {
        "STEP_TOLERANCE_NOT_USED": "Convergence (line 160) uses residual norm ONLY. The movement "
                                   "break (line 170) is a stagnation TERMINATION, not a "
                                   "step-tolerance convergence-success criterion. No step_tolerance "
                                   "participates in convergence. Per directive §1/§5.1/§6: recorded, "
                                   "NOT added.",
        "DAMPING_SCHEDULE_NOT_USED": "The Newton step is applied at factor 1.0 (line 169: pa - da). "
                                     "There is no damping factor, no damping schedule, no "
                                     "maximum_damping_attempts anywhere in _refine. Directive §9/§10 "
                                     "damping machinery does not exist.",
        "MAX_DAMPING_ATTEMPTS_NOT_USED": "No damping attempts exist; there is a single unconditional "
                                         "full step per iteration.",
        "STEP_ACCEPTANCE_BY_IMPROVEMENT_NOT_USED": "The clamped full step is accepted "
            "UNCONDITIONALLY each iteration (line 172). There is no per-step ACCEPT/REJECT decision "
            "and no residual-improvement gate within the loop. The only improvement comparison is "
            "the FINAL Newton-vs-grid selection (line 174). Directive §12 reasons "
            "REJECT_NO_IMPROVEMENT / REJECT_OUT_OF_DOMAIN / REJECT_NONFINITE / REJECT_NO_MOVEMENT do "
            "not correspond to current per-step behaviour (movement is a loop-break, not a reject).",
        "ITERATION_TRANSITION_MULTI_FACTOR_NOT_USED": "There is no ordered damping-factor line "
            "search (directive §13). Each iteration computes one full step and takes it.",
        "DOMAIN_HANDLING_IS_CLAMP_PROJECTION": "The current domain behaviour is SILENT CLAMPING / "
            "projection (line 169 _clamp(p - d, lo, hi)), NOT a reject-out-of-domain predicate. "
            "Directive §11's 'no silent clamping, no projection' predicate is NOT the current "
            "behaviour; preserving current behaviour means preserving the clamp. A domain-membership "
            "predicate (ParameterDomain.contains) exists as a Milestone-A contract but is NOT used "
            "in the Newton loop.",
    },
    "semantic_model_divergence": "The directive (§9/§10/§12/§13/§18-gate-4) describes a DAMPED "
        "Newton LINE-SEARCH with per-step improvement acceptance. The actual solver is an UNDAMPED, "
        "CLAMPED Newton polish with residual-only inclusive convergence, a stagnation break, the "
        "Milestone-B singularity break, and a final grid-vs-Newton selection. The genuinely-present "
        "seams (convergence, iteration budget, Newton step, domain-clamp, stagnation, final "
        "selection) are extractable byte-identically; the damping / step-acceptance-by-improvement / "
        "multi-factor-transition seams have NO code to extract and are recorded NOT_USED per the "
        "directive's own conditional language. This is NOT drift introduced by the refactor; it is "
        "the pre-existing algorithm, frozen here before any edit.",
    "emitted_solver_status_values": sorted(
        {c for c in (S.NO_ROOT, S.IDENTIFIED, S.MULTIPLE_ROOTS, S.NON_IDENTIFIABLE,
                     S.BOUNDARY_SOLUTION, S.FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD)}),
    "non_convergence_raises_exception": False,
    "approved_by": None,
}

blob = json.dumps(freeze, indent=1, sort_keys=True) + "\n"
(D / "SOLVER_MILESTONE_C_PRECHANGE.json").write_text(blob)
print("digest:", "sha256:" + hashlib.sha256(blob.encode()).hexdigest())
print("commit:", commit)
print("emitted statuses:", freeze["emitted_solver_status_values"])
print("NOT_USED findings:", list(freeze["not_used_findings"].keys()))
