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
    "milestone": "STAGE3-0006C-C-REV1",
    "section": "§3/§5 pre-change freeze (amended under REV1; supersedes the STAGE3-0006C-C freeze "
               "labels in place — the frozen solver sources are unchanged and their digests below "
               "are identical to the original freeze at commit 383e1e8)",
    "commit": commit,
    "frozen_source_commit": "383e1e82508871c0271534aba008beec12a13601",
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
    # ---- REV1 §1 descriptive findings: constructs that DO NOT EXIST (recorded, never added,
    # ---- never given placeholder production fields) ------------------------------------------
    "not_used_findings": {
        "STEP_TOLERANCE_NOT_USED": "Convergence (line 160) uses residual norm ONLY. The movement "
                                   "break (line 170) is a stagnation TERMINATION, not a "
                                   "step-tolerance convergence-success criterion. No step_tolerance "
                                   "participates in convergence. Recorded, NOT added.",
        "DAMPING_SCHEDULE_NOT_USED": "There is no damping schedule anywhere in _refine. The Newton "
                                     "step is applied once per iteration at factor 1.0 (line 169: "
                                     "pa - da).",
        "DAMPING_FACTOR_NOT_USED": "No damping factor exists; the implicit step multiplier is the "
                                   "constant 1.0 with no representation in code.",
        "MAXIMUM_DAMPING_ATTEMPTS_NOT_USED": "No damping attempts exist; there is a single "
                                             "unconditional full step per iteration.",
        "MULTI_FACTOR_LINE_SEARCH_NOT_USED": "There is no ordered damping-factor line search. Each "
                                             "iteration computes one full step and takes it.",
        "PER_STEP_IMPROVEMENT_ACCEPTANCE_NOT_USED": "The clamped full step is accepted "
            "UNCONDITIONALLY each iteration (line 172). There is no per-step ACCEPT/REJECT decision "
            "and no residual-improvement gate within the loop. The only improvement comparison is "
            "the FINAL grid-versus-Newton selection (line 174, strict <).",
        "FIRST_ACCEPTED_FACTOR_POLICY_NOT_USED": "With no damping factors there is no "
                                                 "first-accepted-factor policy to preserve.",
        "DOMAIN_HANDLING_IS_CLAMP_PROJECTION": "The current domain behaviour is SILENT CLAMPING / "
            "projection (line 169 _clamp(p - d, lo, hi)), NOT a reject-out-of-domain predicate. "
            "Preserving current behaviour means preserving the clamp. ParameterDomain.contains "
            "exists as a Milestone-A contract but is NOT used in the Newton loop.",
    },
    "incidental_behaviour": {
        "clamp_signed_zero": "_clamp uses strict comparisons (x < lo, x > hi); an input exactly "
            "equal to a bound is returned AS THE INPUT OBJECT (e.g. -0.0 at a 0.0 bound stays "
            "-0.0). Frozen as-is.",
        "clamp_nan_passthrough": "_clamp(NaN, lo, hi) returns NaN (both strict comparisons are "
            "False). Frozen as-is.",
        "nan_residual_never_converges": "A NaN residual makes the inclusive comparison False, so "
            "iteration continues; no NONFINITE branch exists. Frozen as-is.",
        "newton_iters_comment": "The _NEWTON_ITERS comment reads 'bounded damped-Newton polish "
            "iterations' — misleading prose (the polish is undamped). REV1 §2 authorises correcting "
            "this comment only; recorded here pre-correction.",
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
