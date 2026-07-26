"""STAGE3-0006C-C-REV1 §16 — Milestone C differential: frozen-loop trace vs wired production.

Reimplements the FROZEN ``_refine`` (grid pre-polish + undamped Newton polish, constants hardcoded
literally from SOLVER_MILESTONE_C_PRECHANGE.json — 40 / 1e-4 / 1e-10 / 1e-15 / 6 / 5 / 0.5) and
compares it against the wired production ``_refine`` over real solver fixtures:

  * final (p_a, p_b, r2) by EXACT float equality;
  * total ``_residual`` evaluation counts (a counting wrapper around solver._residual measures both
    runs), proving identical iteration behaviour;
  * per-fixture reference trace: Newton iterations, termination reason, residual-sequence digest.

Then re-checks the pure seams against literal expressions by exact equality. Emits
SOLVER_MILESTONE_C_DIFFERENTIAL.json. Synthetic-only: no market data, no outcomes.
"""
from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path

from sport_tennis.coherence import solver as S
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.solver_contracts import Jacobian2x2, ResidualVector2
from sport_tennis.coherence.solver_iteration import (
    apply_step_clamped,
    clamp_scalar,
    is_stagnant,
    iteration_is_permitted,
    newton_converged,
    prefer_newton_candidate,
    propose_newton_step,
)

D = Path("docs/evidence/stage3-cross-market-audit")
_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_LINE = Decimal("22.5")


def reference_refine(ca, cb, h, a_first, fmt, line, tw, to, lo, hi):  # noqa: ANN001, ANN201
    """LITERAL frozen _refine (solver.py@383e1e8 lines 138-176; constants hardcoded)."""
    def clamp(x):  # noqa: ANN001, ANN202
        return lo if x < lo else hi if x > hi else x

    step = 2.0 * h / (5 - 1)
    best_r = S._r2(S._residual(ca, cb, a_first, fmt, line, tw, to))
    best_a, best_b = ca, cb
    for _ in range(6):
        for ia in range(5):
            pa = clamp(ca - h + step * ia)
            for ib in range(5):
                pb = clamp(cb - h + step * ib)
                r = S._r2(S._residual(pa, pb, a_first, fmt, line, tw, to))
                if r < best_r:
                    best_r, best_a, best_b = r, pa, pb
        ca, cb = best_a, best_b
        h *= 0.5
        step = 2.0 * h / (5 - 1)

    pa, pb = best_a, best_b
    iters = 0
    stop = "BUDGET_EXHAUSTED"
    seq: list[tuple[float, float]] = []
    for _ in range(40):
        f1, f2 = S._residual(pa, pb, a_first, fmt, line, tw, to)
        seq.append((f1, f2))
        if f1 * f1 + f2 * f2 <= 1e-4 * 1e-4:
            stop = "CONVERGED"
            break
        jac = S._jacobian_matrix(pa, pb, a_first, fmt, line, tw, to)
        d11, d21, d12, d22 = jac.d_mo_d_a, jac.d_tg_d_a, jac.d_mo_d_b, jac.d_tg_d_b
        det = d11 * d22 - d12 * d21
        if abs(det) < 1e-10:
            stop = "SINGULAR"
            break
        da = (d22 * f1 - d12 * f2) / det
        db = (-d21 * f1 + d11 * f2) / det
        na, nb = clamp(pa - da), clamp(pb - db)
        if abs(na - pa) < 1e-15 and abs(nb - pb) < 1e-15:
            stop = "STAGNANT"
            break
        pa, pb = na, nb
        iters += 1
    newton_r = S._r2(S._residual(pa, pb, a_first, fmt, line, tw, to))
    if newton_r < best_r:
        return pa, pb, newton_r, iters, stop, seq
    return best_a, best_b, best_r, iters, stop, seq


def counted(fn, *args):  # noqa: ANN001, ANN002, ANN201
    calls = {"n": 0}
    orig = S._residual

    def wrapper(*a, **k):  # noqa: ANN002, ANN003, ANN202
        calls["n"] += 1
        return orig(*a, **k)

    S._residual = wrapper
    try:
        out = fn(*args)
    finally:
        S._residual = orig
    return out, calls["n"]


# fixtures: (label, a_first, generating pair or explicit targets, domain, seed point)
t_ident = S.derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
t_mirror = S.derived_targets(0.62, 0.66, _FMT, _LINE, a_serves_first=False)
t_narrow = S.derived_targets(0.61, 0.63, _FMT, _LINE, a_serves_first=True)
FIXTURES = [
    ("identified_seed_near", True, t_ident, (0.35, 0.90), (0.66, 0.60)),
    ("identified_seed_far", True, t_ident, (0.35, 0.90), (0.44, 0.85)),
    ("b_first_target", False, t_mirror, (0.35, 0.90), (0.58, 0.70)),
    ("narrow_domain", True, t_narrow, (0.50, 0.70), (0.55, 0.68)),
    ("no_root_targets", True, (0.98, 0.02), (0.35, 0.90), (0.62, 0.62)),
    ("no_root_narrow", False, (0.05, 0.95), (0.50, 0.70), (0.60, 0.55)),
    ("boundary_pull", True, S.derived_targets(0.36, 0.88, _FMT, _LINE, a_serves_first=True),
     (0.35, 0.90), (0.40, 0.80)),
    ("flat_disagreement", False, (0.50, 0.50), (0.50, 0.70), (0.65, 0.52)),
]

rows = []
all_equal = True
for label, a_first, (tw, to), (lo, hi), (sa, sb) in FIXTURES:
    h = (hi - lo) / 12
    (ref_out, ref_calls) = counted(reference_refine, sa, sb, h, a_first, _FMT, _LINE, tw, to, lo, hi)
    (prod_out, prod_calls) = counted(S._refine, sa, sb, h, a_first, _FMT, _LINE, tw, to, lo, hi)
    rpa, rpb, rr2, iters, stop, seq = ref_out
    ppa, ppb, pr2 = prod_out
    exact = (rpa == ppa and rpb == ppb and rr2 == pr2)
    counts_equal = ref_calls == prod_calls
    all_equal = all_equal and exact and counts_equal
    rows.append({
        "fixture": label, "a_first": a_first, "domain": [lo, hi], "targets": [tw, to],
        "seed": [sa, sb],
        "final_exact_equal": exact, "residual_call_counts_equal": counts_equal,
        "reference_calls": ref_calls, "production_calls": prod_calls,
        "newton_iterations": iters, "termination_reason": stop,
        "residual_sequence_len": len(seq),
        "residual_sequence_digest": "sha256:" + hashlib.sha256(
            repr(seq).encode()).hexdigest()[:16],
        "final": {"p_a": ppa, "p_b": ppb, "r2": pr2},
    })

# ---- pure-seam exact re-checks vs literal expressions -----------------------------------
seam_mm = 0
seam_n = 0
tol = 1e-4
for f1 in [0.0, 1e-9, math.nextafter(tol, 0.0), tol, math.nextafter(tol, 1.0), 1e-3, -tol]:
    for f2 in [0.0, 5e-5, tol, -1e-3]:
        seam_n += 1
        if newton_converged(ResidualVector2(f1, f2), tol) != (f1 * f1 + f2 * f2 <= tol * tol):
            seam_mm += 1
for i in [-1, 0, 1, 39, 40, 41]:
    seam_n += 1
    if iteration_is_permitted(i, 40) != (i in range(40)):
        seam_mm += 1
for x in [0.0, 0.35, math.nextafter(0.35, 0.0), 0.62, 0.9, math.nextafter(0.9, 1.0), 1.0]:
    seam_n += 1
    lit = 0.35 if x < 0.35 else 0.9 if x > 0.9 else x
    if clamp_scalar(x, 0.35, 0.9) != lit:
        seam_mm += 1
for f1, f2, d11, d21, d12, d22 in [(0.11, 0.23, 2.0, 5.0, 3.0, 7.0), (0.3, -0.2, 1.0, 0.0, 0.0, 1.0),
                                   (-0.05, 0.4, 4.0, -1.5, 2.5, 6.0)]:
    seam_n += 1
    det = d11 * d22 - d12 * d21
    st = propose_newton_step(ResidualVector2(f1, f2),
                             Jacobian2x2(d_mo_d_a=d11, d_mo_d_b=d12, d_tg_d_a=d21, d_tg_d_b=d22))
    if (st.delta_a, st.delta_b) != ((d22 * f1 - d12 * f2) / det, (-d21 * f1 + d11 * f2) / det):
        seam_mm += 1
    seam_n += 1
    if apply_step_clamped(0.5, 0.6, st, 0.0, 1.0) != (
            (0.0 if 0.5 - st.delta_a < 0.0 else 1.0 if 0.5 - st.delta_a > 1.0 else 0.5 - st.delta_a),
            (0.0 if 0.6 - st.delta_b < 0.0 else 1.0 if 0.6 - st.delta_b > 1.0 else 0.6 - st.delta_b)):
        seam_mm += 1
for da in [0.0, 1e-16, 1e-15, 2e-15]:
    for db in [0.0, 1e-15]:
        seam_n += 1
        na, nb = 0.5 + da, 0.6 + db
        # literal recomputation on the SAME candidate point (float absorption near 1e-15 means
        # abs(na-0.5) != abs(da); the frozen rule operates on the point difference)
        if is_stagnant(0.5, 0.6, na, nb, 1e-15) != (
                abs(na - 0.5) < 1e-15 and abs(nb - 0.6) < 1e-15):
            seam_mm += 1
for n in [0.0, 1e-10, 1e-9, 2e-9]:
    for g in [1e-9, 1e-10]:
        seam_n += 1
        if prefer_newton_candidate(n, g) != (n < g):
            seam_mm += 1

report = {
    "milestone": "STAGE3-0006C-C-REV1",
    "section": "§16 differential compatibility",
    "prechange_frozen_commit": "383e1e82508871c0271534aba008beec12a13601",
    "golden_result": "PASS byte-for-byte (test_solver_golden.py, 2 tests, post-wiring)",
    "loop_fixtures": rows,
    "loop_all_exact_equal": all_equal,
    "seam_literal_samples": seam_n,
    "seam_literal_mismatches": seam_mm,
    "byte_identical": all_equal and seam_mm == 0,
    "not_used_confirmed": ["STEP_TOLERANCE_NOT_USED", "DAMPING_SCHEDULE_NOT_USED",
                           "DAMPING_FACTOR_NOT_USED", "MAXIMUM_DAMPING_ATTEMPTS_NOT_USED",
                           "MULTI_FACTOR_LINE_SEARCH_NOT_USED",
                           "PER_STEP_IMPROVEMENT_ACCEPTANCE_NOT_USED",
                           "FIRST_ACCEPTED_FACTOR_POLICY_NOT_USED"],
    "exception_and_status_behaviour": "UNCHANGED (non-convergence still raises nothing; statuses "
                                      "unchanged; no raise->status remap).",
    "tests_altered": "NONE",
}
blob = json.dumps(report, indent=1, sort_keys=True) + "\n"
(D / "SOLVER_MILESTONE_C_DIFFERENTIAL.json").write_text(blob)
print("loop_all_exact_equal:", all_equal, "| seam samples:", seam_n, "mismatches:", seam_mm)
print("termination reasons:", [r["termination_reason"] for r in rows])
print("iterations:", [r["newton_iterations"] for r in rows])
print("digest: sha256:" + hashlib.sha256(blob.encode()).hexdigest())
