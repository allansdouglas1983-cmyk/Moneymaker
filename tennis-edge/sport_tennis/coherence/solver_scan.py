"""CROSS_MARKET_COHERENCE_V1 — extracted solver scan/jacobian seams (STAGE3-0006C Milestone B).

Named, individually-testable seams for the identification solver's inner numerics. Every function
reproduces the solver's existing float arithmetic BYTE-IDENTICALLY — the differential golden oracle
(``tests/unit/coherence/test_solver_golden.py``) guards the end-to-end contract, and the Milestone B
seam tests guard each function in isolation. The extraction exists ONLY to give each arithmetic step
a single closed home with its own hardened mutation gate, replacing scattered inline expressions in
``solver.py``. SYNTHETIC-ONLY; reads no market prices and no outcomes. Import-quarantined from
execution/pricing/V0.

§5/§7 vocabulary divergence (disclosed, SOLVER_MILESTONE_B_PRECHANGE.json ``finding_5_7``): the
directive's ScanCell-corner (§5) and SIGN_CHANGE candidate-region (§7) vocabulary does NOT describe
this solver. This solver evaluates the residual 2-norm at each grid NODE and RANKS/CLUSTERS the
lowest-norm nodes as refinement seeds; it never forms four-corner cells and never classifies a sign
change. §5 therefore has NO independent seam — the seed-selection rule (§7) subsumes it. Per §7's
escape clause the actual rule is preserved EXPLICITLY in :func:`rank_seed_nodes`, never collapsed
into a sign-change model.
"""
from __future__ import annotations

from sport_tennis.coherence.solver_contracts import Jacobian2x2


def build_scan_axis(lo: float, hi: float, n: int) -> list[float]:
    """The coarse scan axis: ``n`` equally spaced nodes from ``lo`` to ``hi`` inclusive.

    Byte-identical to the solver's inline ``[lo + (hi - lo) * i / (n - 1) for i in range(n)]``.
    """
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def rank_seed_nodes(grid: list[list[float]], n_seed: int, cluster_r: int) -> list[tuple[int, int]]:
    """Select refinement seed nodes from the residual-norm grid (§7; §5 folded in — see module
    docstring). Rank every node by (residual-norm, row, col) ascending, take the lowest ``n_seed``,
    and keep a candidate only when it is strictly farther than ``cluster_r`` (Chebyshev / max-norm
    index distance) from every seed already kept, so each deep basin is refined once and distinct
    basins (e.g. the mirror parameter pair) each survive.

    Byte-identical to the solver's inline ranking + clustering loop.
    """
    size = len(grid)
    ranked = sorted(((grid[i][j], i, j) for i in range(size) for j in range(size)),
                    key=lambda t: (t[0], t[1], t[2]))
    seeds: list[tuple[int, int]] = []
    for _r, i, j in ranked[:n_seed]:
        if all(max(abs(i - ci), abs(j - cj)) > cluster_r for ci, cj in seeds):
            seeds.append((i, j))
    return seeds


def perturbation_points(p: float, e: float, clamp_lo: float, clamp_hi: float) -> tuple[float, float]:
    """The two clamped central-difference perturbation points for one parameter: ``(min(p + e,
    clamp_hi), max(p - e, clamp_lo))``. Returns ``(plus, minus)``. Byte-identical to the solver's
    inline ``min(p_a + e, 0.99), max(p_a - e, 0.01)``.
    """
    return min(p + e, clamp_hi), max(p - e, clamp_lo)


def jacobian_from_differences(fa_plus: tuple[float, float], fa_minus: tuple[float, float],
                              fb_plus: tuple[float, float], fb_minus: tuple[float, float],
                              denom_a: float, denom_b: float) -> Jacobian2x2:
    """Assemble the central-difference identification Jacobian from four residual vectors and the
    two perturbation denominators. Residual component 0 is match-odds, 1 is total-games; ``fa_*``
    perturb ``p_a``, ``fb_*`` perturb ``p_b``. Byte-identical to the solver's inline difference
    quotients (``d11=d_mo_d_a``, ``d21=d_tg_d_a``, ``d12=d_mo_d_b``, ``d22=d_tg_d_b``).
    """
    return Jacobian2x2(
        d_mo_d_a=(fa_plus[0] - fa_minus[0]) / denom_a,
        d_mo_d_b=(fb_plus[0] - fb_minus[0]) / denom_b,
        d_tg_d_a=(fa_plus[1] - fa_minus[1]) / denom_a,
        d_tg_d_b=(fb_plus[1] - fb_minus[1]) / denom_b,
    )


def is_singular(det: float, tol: float) -> bool:
    """Whether a determinant magnitude is below a singularity tolerance: ``abs(det) < tol`` (strict).
    Used for both Newton's un-steppable-Jacobian guard (``_NEWTON_SINGULAR``) and the identification
    degeneracy test (``_JAC_TOL``). Byte-identical to the solver's inline ``abs(det) < tol``.
    """
    return abs(det) < tol
