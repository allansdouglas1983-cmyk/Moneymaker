"""STAGE3-0006C-B §12 — independent semantic-equivalence check + differential report.

Independent of the golden oracle (end-to-end) and of the seam unit tests (pinned values): this
recomputes each pre-refactor INLINE expression literally and asserts the extracted seam reproduces
it with EXACT float equality (==, not approx) over a deterministic sample sweep. Emits
SOLVER_MILESTONE_B_DIFFERENTIAL.json. No market data, no outcomes, no randomness dependence
(fixed deterministic samples).
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.solver import _jacobian_matrix, _residual, derived_targets
from sport_tennis.coherence.solver_scan import (
    build_scan_axis,
    is_singular,
    jacobian_from_differences,
    perturbation_points,
    rank_seed_nodes,
)

OUT = "docs/evidence/stage3-cross-market-audit"
checks: list[dict[str, object]] = []


def record(name: str, total: int, mismatches: int, note: str) -> None:
    checks.append({"seam": name, "samples": total, "mismatches": mismatches,
                   "exact_equal": mismatches == 0, "note": note})


# ---- §4 build_scan_axis vs literal comprehension ----------------------------------------
axis_domains = [(0.35, 0.90), (0.50, 0.70), (0.01, 0.99), (0.2, 0.8), (0.123, 0.877)]
mm = 0
n = 13
for lo, hi in axis_domains:
    got = build_scan_axis(lo, hi, n)
    ref = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    mm += sum(1 for a, b in zip(got, ref) if a != b) + (0 if len(got) == len(ref) else 1)
record("build_scan_axis(§4)", len(axis_domains) * n, mm,
       "n=13 nodes; both governed domains + 3 probes; exact ==")

# ---- §7 rank_seed_nodes vs literal ranking+clustering -----------------------------------
def ref_seeds(grid: list[list[float]], n_seed: int, cluster_r: int) -> list[tuple[int, int]]:
    size = len(grid)
    ranked = sorted(((grid[i][j], i, j) for i in range(size) for j in range(size)),
                    key=lambda t: (t[0], t[1], t[2]))
    seeds: list[tuple[int, int]] = []
    for _r, i, j in ranked[:n_seed]:
        if all(max(abs(i - ci), abs(j - cj)) > cluster_r for ci, cj in seeds):
            seeds.append((i, j))
    return seeds


# deterministic pseudo-grids (fixed integer hash, no RNG dependence)
grid_mm = 0
grid_count = 0
for seed in range(40):
    size = 13
    grid = [[((i * 31 + j * 17 + seed * 7) % 97) / 97.0 for j in range(size)] for i in range(size)]
    for n_seed, cluster_r in [(20, 2), (20, 0), (5, 1), (169, 3)]:
        grid_count += 1
        if rank_seed_nodes(grid, n_seed, cluster_r) != ref_seeds(grid, n_seed, cluster_r):
            grid_mm += 1
record("rank_seed_nodes(§7,§5-folded)", grid_count, grid_mm,
       "40 deterministic 13x13 grids x 4 (n_seed,cluster_r); exact list equality")

# ---- §8a perturbation_points vs literal min/max clamp -----------------------------------
pp_mm = 0
pp_count = 0
for p in [0.01, 0.02, 0.35, 0.5, 0.625, 0.9, 0.98, 0.99, 0.995, 0.015]:
    for e in [0.001, 0.01, 0.05]:
        pp_count += 1
        got = perturbation_points(p, e, 0.01, 0.99)
        ref = (min(p + e, 0.99), max(p - e, 0.01))
        if got != ref:
            pp_mm += 1
record("perturbation_points(§8a)", pp_count, pp_mm,
       "clamp lo=0.01 hi=0.99; interior + both clamped edges; exact ==")

# ---- §8b jacobian_from_differences vs literal difference quotients ----------------------
jac_mm = 0
jac_count = 0
_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_LINE = Decimal("22.5")
tw, to = derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
for pa in [0.40, 0.55, 0.63, 0.75, 0.88]:
    for pb in [0.42, 0.57, 0.70]:
        jac_count += 1
        ap, am = min(pa + 1e-3, 0.99), max(pa - 1e-3, 0.01)
        bp, bm = min(pb + 1e-3, 0.99), max(pb - 1e-3, 0.01)
        fa_p = _residual(ap, pb, True, _FMT, _LINE, tw, to)
        fa_m = _residual(am, pb, True, _FMT, _LINE, tw, to)
        fb_p = _residual(pa, bp, True, _FMT, _LINE, tw, to)
        fb_m = _residual(pa, bm, True, _FMT, _LINE, tw, to)
        j = jacobian_from_differences(fa_p, fa_m, fb_p, fb_m, ap - am, bp - bm)
        d11 = (fa_p[0] - fa_m[0]) / (ap - am)
        d21 = (fa_p[1] - fa_m[1]) / (ap - am)
        d12 = (fb_p[0] - fb_m[0]) / (bp - bm)
        d22 = (fb_p[1] - fb_m[1]) / (bp - bm)
        # seam fields AND the seam determinant vs the literal inline determinant
        if (j.d_mo_d_a, j.d_tg_d_a, j.d_mo_d_b, j.d_tg_d_b) != (d11, d21, d12, d22):
            jac_mm += 1
        elif j.determinant() != d11 * d22 - d12 * d21:
            jac_mm += 1
        # cross-check the tuple adapter is byte-identical to the matrix seam
        elif _jacobian_matrix(pa, pb, True, _FMT, _LINE, tw, to).determinant() != (
                d11 * d22 - d12 * d21):
            jac_mm += 1
record("jacobian_from_differences+determinant(§8b)", jac_count, jac_mm,
       "15 (p_a,p_b) points via real _residual; fields, seam det, matrix det all exact ==")

# ---- §9 is_singular vs literal abs(det)<tol ---------------------------------------------
sg_mm = 0
sg_count = 0
for det in [-1.0, -5e-3, -4.9e-3, -1e-4, 0.0, 1e-12, 4.9e-3, 5e-3, 5.1e-3, 1.0]:
    for tol in [5e-3, 1e-10]:
        sg_count += 1
        if is_singular(det, tol) != (abs(det) < tol):
            sg_mm += 1
record("is_singular(§9)", sg_count, sg_mm, "both governed tols; sign-symmetric; strict-< exact ==")

total_mm = sum(int(c["mismatches"]) for c in checks)  # type: ignore[arg-type]
report = {
    "milestone": "STAGE3-0006C-B",
    "section": "§12 independent semantic-equivalence + differential",
    "prechange_commit": "20463e2c8d862ac3061cee39f5115a928282c187",
    "golden_oracle_sha256": "e31b7a51b42f573bb6a01128a1bf13e6ceaa8c11a4645c39bb92de9c9f5c9b35",
    "golden_result": "PASS byte-for-byte (test_solver_golden.py, 2 tests)",
    "seam_checks": checks,
    "total_samples": sum(int(c["samples"]) for c in checks),  # type: ignore[arg-type]
    "total_mismatches": total_mm,
    "byte_identical": total_mm == 0,
    "seams_extracted": [
        "build_scan_axis (§4)",
        "rank_seed_nodes (§7; §5 scan-cell folded in — no independent seam)",
        "perturbation_points (§8a)",
        "jacobian_from_differences (§8b -> Jacobian2x2)",
        "is_singular (§9)",
    ],
    "contract_seams_reused": [
        "ResidualVector2.sum_of_squares (§6, Milestone A)",
        "Jacobian2x2.determinant (§8, Milestone A)",
        "Jacobian2x2.condition_scale (§9 diagnostic, Milestone A)",
    ],
    "finding_5_7": "§5 (ScanCell four-corner residuals) and §7 (SIGN_CHANGE candidate regions) do "
                   "NOT describe this solver; it ranks/clusters lowest-residual-norm grid NODES. Per "
                   "§7 escape clause the actual rule is preserved explicitly in rank_seed_nodes; §5 "
                   "has no independent seam. NOT collapsed to a sign-change model.",
    "exception_to_status_behaviour": "UNCHANGED (validators still raise CoherenceMathError; no "
                                     "raise->status remap in this milestone).",
    "tests_altered": "NONE (existing test_jacobian_exact 4-tuple pin preserved via _jacobian adapter).",
}
path = Path(OUT) / "SOLVER_MILESTONE_B_DIFFERENTIAL.json"
blob = json.dumps(report, indent=1, sort_keys=True)
path.write_text(blob + "\n")
print("total_samples:", report["total_samples"], "total_mismatches:", total_mm,
      "byte_identical:", report["byte_identical"])
print("differential sha256:", hashlib.sha256((blob + "\n").encode()).hexdigest())
print("written:", path)
