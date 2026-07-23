"""STAGE3-0006C Milestone B — extracted solver scan/jacobian seams (tests-first).

Pins each extracted seam of the identification solver's inner numerics so a Milestone B micro-gate
kills every mutation of an index, an operator, a bound, a clamp direction, a tie-break key, a
component role or a denominator. The seams reproduce the solver's existing float arithmetic
BYTE-IDENTICALLY; the differential golden oracle (``test_solver_golden.py``) guards the end-to-end
contract, and these tests guard each seam in isolation.

§5/§7 vocabulary divergence (disclosed, SOLVER_MILESTONE_B_PRECHANGE.json ``finding_5_7``): this
solver evaluates the residual 2-norm at each grid NODE and RANKS/CLUSTERS the lowest-norm nodes as
refinement seeds. There are no four-corner scan CELLS and no SIGN_CHANGE candidate regions, so §5
has no independent seam — the seed-selection rule (§7) subsumes it and is preserved EXPLICITLY in
``rank_seed_nodes`` per §7's escape clause, never collapsed into a sign-change model.
"""
from __future__ import annotations

import math

import pytest

from sport_tennis.coherence.solver_contracts import Jacobian2x2
from sport_tennis.coherence.solver_scan import (
    build_scan_axis,
    is_singular,
    jacobian_from_differences,
    perturbation_points,
    rank_seed_nodes,
)


# ------------------------------------------------------------------ build_scan_axis (§4)
def test_build_scan_axis_endpoints_are_exact() -> None:
    axis = build_scan_axis(0.35, 0.90, 13)
    assert axis[0] == 0.35          # first node is exactly lo
    assert axis[-1] == 0.90         # last node is exactly hi (kills (n-1)->n, i->i+1)
    assert len(axis) == 13


def test_build_scan_axis_is_evenly_spaced_and_monotone() -> None:
    lo, hi, n = 0.35, 0.90, 13
    axis = build_scan_axis(lo, hi, n)
    for i in range(n):
        assert axis[i] == lo + (hi - lo) * i / (n - 1)   # pins the exact expression
    for i in range(1, n):
        assert axis[i] > axis[i - 1]                     # strictly increasing


def test_build_scan_axis_golden_both_governed_domains() -> None:
    # Golden node lists pin the arithmetic so */ + - and index mutants all diverge.
    assert build_scan_axis(0.5, 0.7, 13) == [
        0.5 + (0.7 - 0.5) * i / 12 for i in range(13)]
    a = build_scan_axis(0.35, 0.90, 13)
    assert a[6] == pytest.approx(0.625, abs=1e-12)       # midpoint node of 0.35..0.90


# ------------------------------------------------------------------ rank_seed_nodes (§7, §5 folded)
def _flat_grid(size: int, value: float) -> list[list[float]]:
    return [[value for _ in range(size)] for _ in range(size)]


def test_rank_seed_nodes_orders_by_value_then_indices() -> None:
    grid = _flat_grid(5, 1.0)
    grid[3][3] = 0.1      # global minimum
    grid[0][0] = 0.2      # second lowest
    seeds = rank_seed_nodes(grid, n_seed=20, cluster_r=2)
    assert seeds[0] == (3, 3)     # lowest residual first
    assert seeds[1] == (0, 0)     # next lowest, far enough away to survive clustering


def test_rank_seed_nodes_tie_break_is_row_then_col() -> None:
    grid = _flat_grid(5, 1.0)
    # three equal minima; deterministic order is (i, j) ascending.
    grid[0][4] = 0.1
    grid[0][1] = 0.1
    grid[4][0] = 0.1
    seeds = rank_seed_nodes(grid, n_seed=20, cluster_r=0)
    assert seeds[:3] == [(0, 1), (0, 4), (4, 0)]


def test_rank_seed_nodes_clusters_suppress_near_neighbours() -> None:
    grid = _flat_grid(6, 1.0)
    grid[0][0] = 0.1      # deepest
    grid[1][1] = 0.2      # within cluster radius 2 of (0,0) -> suppressed
    grid[5][5] = 0.3      # far basin -> kept
    seeds = rank_seed_nodes(grid, n_seed=20, cluster_r=2)
    assert (0, 0) in seeds
    assert (1, 1) not in seeds
    assert (5, 5) in seeds


def test_rank_seed_nodes_cluster_uses_chebyshev_max_not_min() -> None:
    # (0,0) then (3,0): chebyshev max-distance = 3 (> 2 -> kept); a min() mutant gives 0 (<= 2 ->
    # suppressed). Distinguishes max from min.
    grid = _flat_grid(6, 1.0)
    grid[0][0] = 0.1
    grid[3][0] = 0.2
    seeds = rank_seed_nodes(grid, n_seed=20, cluster_r=2)
    assert (0, 0) in seeds and (3, 0) in seeds


def test_rank_seed_nodes_cluster_boundary_is_strict_greater() -> None:
    # exact distance == cluster_r must SUPPRESS (rule is strictly-greater-than to keep). (0,0) then
    # (2,0): distance 2 == cluster_r 2 -> not > -> suppressed. Kills > -> >=.
    grid = _flat_grid(5, 1.0)
    grid[0][0] = 0.1
    grid[2][0] = 0.2
    seeds = rank_seed_nodes(grid, n_seed=20, cluster_r=2)
    assert (0, 0) in seeds
    assert (2, 0) not in seeds


def test_rank_seed_nodes_respects_n_seed_truncation() -> None:
    # Only the lowest n_seed ranked nodes are eligible. Make node (4,4) the 2nd lowest but cap
    # n_seed=1 so it is never considered.
    grid = _flat_grid(5, 1.0)
    grid[0][0] = 0.1
    grid[4][4] = 0.2
    seeds = rank_seed_nodes(grid, n_seed=1, cluster_r=2)
    assert seeds == [(0, 0)]


def test_rank_seed_nodes_all_not_any_over_existing_seeds() -> None:
    # A candidate near ONE existing seed but far from another must be suppressed (rule is `all`
    # existing seeds are far). Kills all()->any().
    grid = _flat_grid(9, 1.0)
    grid[0][0] = 0.1      # seed 1
    grid[8][8] = 0.2      # seed 2 (far from both)
    grid[1][1] = 0.3      # near seed 1 (dist 1), far from seed 2 -> suppressed under `all`
    seeds = rank_seed_nodes(grid, n_seed=20, cluster_r=2)
    assert (0, 0) in seeds and (8, 8) in seeds
    assert (1, 1) not in seeds


# ------------------------------------------------------------------ perturbation_points (§8a)
def test_perturbation_points_interior_is_symmetric() -> None:
    hi_pt, lo_pt = perturbation_points(0.5, 0.001, 0.01, 0.99)
    assert hi_pt == 0.501
    assert lo_pt == 0.499


def test_perturbation_points_clamps_upper_edge() -> None:
    hi_pt, lo_pt = perturbation_points(0.995, 0.01, 0.01, 0.99)
    assert hi_pt == 0.99          # min(1.005, 0.99) -> 0.99
    assert lo_pt == pytest.approx(0.985, abs=1e-12)


def test_perturbation_points_clamps_lower_edge() -> None:
    hi_pt, lo_pt = perturbation_points(0.015, 0.01, 0.01, 0.99)
    assert hi_pt == pytest.approx(0.025, abs=1e-12)
    assert lo_pt == 0.01          # max(0.005, 0.01) -> 0.01


# ------------------------------------------------------------------ jacobian_from_differences (§8b)
def test_jacobian_from_differences_maps_every_role() -> None:
    # distinct residual components and denominators so any index/role/denominator swap changes a
    # field. fa_* vary A; fb_* vary B. component 0 = match-odds, component 1 = total-games.
    fa_p = (0.20, 0.03)
    fa_m = (0.10, 0.01)
    fb_p = (0.40, 0.09)
    fb_m = (0.10, 0.03)
    j = jacobian_from_differences(fa_p, fa_m, fb_p, fb_m, denom_a=0.002, denom_b=0.004)
    assert isinstance(j, Jacobian2x2)
    assert j.d_mo_d_a == (0.20 - 0.10) / 0.002
    assert j.d_tg_d_a == (0.03 - 0.01) / 0.002
    assert j.d_mo_d_b == (0.40 - 0.10) / 0.004
    assert j.d_tg_d_b == (0.09 - 0.03) / 0.004


def test_jacobian_from_differences_determinant_orientation_preserved() -> None:
    fa_p = (0.20, 0.03)
    fa_m = (0.10, 0.01)
    fb_p = (0.40, 0.09)
    fb_m = (0.10, 0.03)
    j = jacobian_from_differences(fa_p, fa_m, fb_p, fb_m, denom_a=0.002, denom_b=0.004)
    d11, d21, d12, d22 = j.d_mo_d_a, j.d_tg_d_a, j.d_mo_d_b, j.d_tg_d_b
    assert j.determinant() == pytest.approx(d11 * d22 - d12 * d21, abs=1e-12)


# ------------------------------------------------------------------ is_singular (§9)
def test_is_singular_strict_below_tolerance() -> None:
    tol = 5e-3
    assert is_singular(0.0, tol)
    assert is_singular(math.nextafter(tol, 0.0), tol)     # just below -> singular
    assert not is_singular(tol, tol)                      # exactly tol -> not (strict <)
    assert not is_singular(math.nextafter(tol, 1.0), tol)  # just above -> not singular


def test_is_singular_uses_absolute_value() -> None:
    tol = 5e-3
    assert is_singular(-1e-4, tol)        # negative small magnitude is singular
    assert not is_singular(-1.0, tol)     # negative large magnitude is not
