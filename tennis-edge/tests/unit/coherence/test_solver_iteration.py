"""STAGE3-0006C-C-REV1 §6-§8, §11-§13 (as revised) — iteration seam tests (tests-first).

Pins each extracted Newton-polish seam exactly: residual-only inclusive convergence, range()
iteration budget, exact Newton-step arithmetic and orientation, clamp projection (including its
frozen incidental signed-zero and NaN passthrough behaviour), stagnation detection, and the final
grid-versus-Newton strict-improvement selection. Boundaries use ``math.nextafter``. No damping
machinery exists and none is tested — REV1 §1 NOT_USED findings.
"""
from __future__ import annotations

import dataclasses
import math

import pytest

from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver_contracts import Jacobian2x2, ResidualVector2
from sport_tennis.coherence.solver_iteration import (
    NewtonStep2,
    apply_step_clamped,
    clamp_scalar,
    is_stagnant,
    iteration_is_permitted,
    newton_converged,
    next_iteration_index,
    prefer_newton_candidate,
    propose_newton_step,
    residual_norm2_within_tolerance,
)

_NAN = float("nan")
_INF = float("inf")
_TOL = 1e-4                     # the governed _ROOT_TOL value, used as a representative tolerance


# ------------------------------------------------------------------ convergence (§6)
def test_convergence_zero_residual_and_inclusive_boundary() -> None:
    assert newton_converged(ResidualVector2(0.0, 0.0), _TOL)
    # sum_of_squares == tol*tol exactly at residual (tol, 0): INCLUSIVE <= must accept.
    assert newton_converged(ResidualVector2(_TOL, 0.0), _TOL)
    assert newton_converged(ResidualVector2(0.0, _TOL), _TOL)


def test_convergence_strictly_above_boundary_refused() -> None:
    assert not newton_converged(ResidualVector2(math.nextafter(_TOL, 1.0), 0.0), _TOL)
    assert not newton_converged(ResidualVector2(0.0, math.nextafter(_TOL, 1.0)), _TOL)
    assert not newton_converged(ResidualVector2(_TOL, _TOL), _TOL)   # sum 2*tol^2 > tol^2


def test_convergence_norm2_form_boundaries() -> None:
    t2 = _TOL * _TOL
    assert residual_norm2_within_tolerance(t2, _TOL)                          # exact: inclusive
    assert residual_norm2_within_tolerance(math.nextafter(t2, 0.0), _TOL)     # just below
    assert not residual_norm2_within_tolerance(math.nextafter(t2, 1.0), _TOL)  # just above
    assert residual_norm2_within_tolerance(0.0, _TOL)


def test_convergence_tolerance_is_squared_not_doubled() -> None:
    # kills tol*tol -> tol+tol: 1.5e-8 is above tol^2=1e-8 but far below tol+tol=2e-4.
    assert not residual_norm2_within_tolerance(1.5e-8, _TOL)


def test_convergence_nonfinite_residual_is_not_converged() -> None:
    # frozen incidental behaviour: NaN/inf make the inclusive comparison False -> keep iterating.
    assert not newton_converged(ResidualVector2(_NAN, 0.0), _TOL)
    assert not newton_converged(ResidualVector2(0.0, _NAN), _TOL)
    assert not newton_converged(ResidualVector2(_INF, 0.0), _TOL)
    assert not newton_converged(ResidualVector2(0.0, -_INF), _TOL)


def test_convergence_uses_sum_of_both_components() -> None:
    # each component below tol alone, sum above tol^2: must NOT converge (rule is on the sum).
    r = ResidualVector2(9e-5, 9e-5)          # sum_sq = 1.62e-8 > 1e-8
    assert not newton_converged(r, _TOL)


# ------------------------------------------------------------------ iteration budget (§7)
def test_iteration_budget_range_semantics() -> None:
    assert not iteration_is_permitted(-1, 40)     # negative index is outside range(40)
    assert iteration_is_permitted(0, 40)
    assert iteration_is_permitted(1, 40)
    assert iteration_is_permitted(38, 40)         # maximum - 2
    assert iteration_is_permitted(39, 40)         # maximum - 1: the LAST permitted index
    assert not iteration_is_permitted(40, 40)     # exact maximum is refused
    assert not iteration_is_permitted(41, 40)
    assert not iteration_is_permitted(10**9, 40)


def test_iteration_budget_refuses_bool_and_non_integer() -> None:
    with pytest.raises(CoherenceMathError):
        iteration_is_permitted(True, 40)          # Boolean-as-integer refused
    with pytest.raises(CoherenceMathError):
        iteration_is_permitted(0, True)
    with pytest.raises(CoherenceMathError):
        iteration_is_permitted(0.0, 40)           # type: ignore[arg-type]
    with pytest.raises(CoherenceMathError):
        iteration_is_permitted(0, 40.0)           # type: ignore[arg-type]


def test_next_iteration_index_increments_by_exactly_one() -> None:
    assert next_iteration_index(0) == 1
    assert next_iteration_index(1) == 2
    assert next_iteration_index(38) == 39
    assert next_iteration_index(7) - 7 == 1       # +1: not +0, +2, -, <<, or a reset
    with pytest.raises(CoherenceMathError):
        next_iteration_index(True)
    with pytest.raises(CoherenceMathError):
        next_iteration_index(1.0)                 # type: ignore[arg-type]


# ------------------------------------------------------------------ Newton step (§8)
def test_newton_step_identity_jacobian_returns_residual() -> None:
    j = Jacobian2x2(d_mo_d_a=1.0, d_mo_d_b=0.0, d_tg_d_a=0.0, d_tg_d_b=1.0)
    s = propose_newton_step(ResidualVector2(0.3, -0.2), j)
    assert s.delta_a == 0.3 and s.delta_b == -0.2


def test_newton_step_diagonal_jacobian_divides_componentwise() -> None:
    j = Jacobian2x2(d_mo_d_a=2.0, d_mo_d_b=0.0, d_tg_d_a=0.0, d_tg_d_b=4.0)
    s = propose_newton_step(ResidualVector2(0.3, -0.2), j)
    assert s.delta_a == 0.3 / 2.0 and s.delta_b == -0.2 / 4.0


def test_newton_step_off_diagonal_jacobian_swaps_roles() -> None:
    # J = [[0, 3], [5, 0]]: det = -15; da = f2/5, db = f1/3 exactly.
    j = Jacobian2x2(d_mo_d_a=0.0, d_mo_d_b=3.0, d_tg_d_a=5.0, d_tg_d_b=0.0)
    s = propose_newton_step(ResidualVector2(0.3, -0.2), j)
    det = 0.0 * 0.0 - 3.0 * 5.0
    assert s.delta_a == (0.0 * 0.3 - 3.0 * -0.2) / det
    assert s.delta_b == (-5.0 * 0.3 + 0.0 * -0.2) / det


def test_newton_step_coupled_jacobian_exact_cramer() -> None:
    # all-distinct entries + all-distinct residual components: any row/column/sign/operator swap
    # changes at least one field. Expected values recomputed with the identical literal expressions.
    j = Jacobian2x2(d_mo_d_a=2.0, d_mo_d_b=3.0, d_tg_d_a=5.0, d_tg_d_b=7.0)
    s = propose_newton_step(ResidualVector2(0.11, 0.23), j)
    det = 2.0 * 7.0 - 3.0 * 5.0                    # -1.0
    assert s.delta_a == (7.0 * 0.11 - 3.0 * 0.23) / det
    assert s.delta_b == (-5.0 * 0.11 + 2.0 * 0.23) / det
    # non-integer quotients so a / -> // mutant diverges
    assert s.delta_a != (7.0 * 0.11 - 3.0 * 0.23) // det


def test_newton_step_sign_reversed_residual_negates_step() -> None:
    j = Jacobian2x2(d_mo_d_a=2.0, d_mo_d_b=3.0, d_tg_d_a=5.0, d_tg_d_b=7.0)
    s = propose_newton_step(ResidualVector2(0.11, 0.23), j)
    n = propose_newton_step(ResidualVector2(-0.11, -0.23), j)
    assert n.delta_a == -s.delta_a and n.delta_b == -s.delta_b


def test_newton_step_small_determinant_above_threshold_is_finite() -> None:
    # det = 1e-9 (> _NEWTON_SINGULAR=1e-10; singularity is refused BEFORE entry, Milestone B seam)
    j = Jacobian2x2(d_mo_d_a=1.0, d_mo_d_b=1.0, d_tg_d_a=1.0, d_tg_d_b=1.0 + 1e-9)
    s = propose_newton_step(ResidualVector2(1e-6, 2e-6), j)
    assert math.isfinite(s.delta_a) and math.isfinite(s.delta_b)


def test_newton_step_contract_is_frozen_finite_and_ordered() -> None:
    s = NewtonStep2(delta_a=0.25, delta_b=-0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.delta_a = 0.0  # type: ignore[misc]
    assert s.inf_norm() == 0.5
    assert s.serialize() == {"delta_a": 0.25, "delta_b": -0.5}
    assert list(s.serialize()) == ["delta_a", "delta_b"]
    s.validate()
    with pytest.raises(CoherenceMathError):
        NewtonStep2(_NAN, 0.0).validate()
    with pytest.raises(CoherenceMathError):
        NewtonStep2(0.0, _INF).validate()


# ------------------------------------------------------------------ clamp projection (§11 revised)
def test_clamp_scalar_matches_frozen_semantics() -> None:
    assert clamp_scalar(0.5, 0.35, 0.9) == 0.5
    assert clamp_scalar(0.1, 0.35, 0.9) == 0.35
    assert clamp_scalar(0.99, 0.35, 0.9) == 0.9
    assert clamp_scalar(0.35, 0.35, 0.9) == 0.35
    assert clamp_scalar(0.9, 0.35, 0.9) == 0.9
    assert clamp_scalar(math.nextafter(0.35, 0.0), 0.35, 0.9) == 0.35   # just below lo -> lo
    assert clamp_scalar(math.nextafter(0.9, 1.0), 0.35, 0.9) == 0.9     # just above hi -> hi
    assert clamp_scalar(math.nextafter(0.35, 1.0), 0.35, 0.9) \
        == math.nextafter(0.35, 1.0)                                     # just inside -> unchanged


def test_clamp_scalar_frozen_incidental_signed_zero_passthrough() -> None:
    # strict comparisons: an input exactly equal to a bound is returned AS THE INPUT (frozen
    # incidental behaviour) — -0.0 at a 0.0 bound stays -0.0. Kills < -> <= and > -> >= mutants.
    assert math.copysign(1.0, clamp_scalar(-0.0, 0.0, 1.0)) == -1.0
    assert math.copysign(1.0, clamp_scalar(-0.0, -1.0, 0.0)) == -1.0


def test_clamp_scalar_frozen_incidental_nan_passthrough() -> None:
    assert math.isnan(clamp_scalar(_NAN, 0.35, 0.9))


def test_apply_step_clamped_orientation_and_projection() -> None:
    # the step is SUBTRACTED (pa - delta_a): kills +/- reversal and the a/b swap.
    na, nb = apply_step_clamped(0.5, 0.6, NewtonStep2(0.1, -0.2), 0.0, 1.0)
    assert na == 0.4 and nb == 0.8
    # zero step: point unchanged
    assert apply_step_clamped(0.5, 0.6, NewtonStep2(0.0, 0.0), 0.0, 1.0) == (0.5, 0.6)
    # a-only and b-only steps move exactly one coordinate
    assert apply_step_clamped(0.5, 0.6, NewtonStep2(0.25, 0.0), 0.0, 1.0) == (0.25, 0.6)
    assert apply_step_clamped(0.5, 0.6, NewtonStep2(0.0, 0.25), 0.0, 1.0) == (0.5, 0.35)
    # projection at both edges
    assert apply_step_clamped(0.5, 0.6, NewtonStep2(2.0, -2.0), 0.35, 0.9) == (0.35, 0.9)


# ------------------------------------------------------------------ stagnation (§12 revised)
def test_stagnation_zero_movement_is_stagnant() -> None:
    assert is_stagnant(0.5, 0.6, 0.5, 0.6, 1e-15)


def test_stagnation_strict_boundary_and_and_logic() -> None:
    t = 1e-15
    below = math.nextafter(t, 0.0)
    # movement exactly t on one axis: strict < makes it NOT stagnant
    assert not is_stagnant(0.0, 0.0, t, 0.0, t)
    assert not is_stagnant(0.0, 0.0, 0.0, t, t)
    # movement just below t on both axes: stagnant
    assert is_stagnant(0.0, 0.0, below, below, t)
    # AND, not OR: one axis stagnant + one moving is NOT stagnant
    assert not is_stagnant(0.0, 0.0, 0.0, 1e-3, t)
    assert not is_stagnant(0.0, 0.0, 1e-3, 0.0, t)


def test_stagnation_uses_absolute_movement() -> None:
    t = 1e-15
    assert not is_stagnant(0.5, 0.5, 0.5 - 1e-3, 0.5, t)     # negative movement counts
    assert is_stagnant(0.5, 0.5, 0.5 - math.nextafter(t, 0.0), 0.5, t)


# ------------------------------------------------------------------ final selection (§13 revised)
def test_final_selection_strict_improvement_only() -> None:
    assert prefer_newton_candidate(1e-10, 1e-9)                          # better -> Newton
    assert not prefer_newton_candidate(1e-9, 1e-9)                       # EQUAL -> grid (strict <)
    assert not prefer_newton_candidate(1e-8, 1e-9)                       # worse -> grid
    assert prefer_newton_candidate(math.nextafter(1e-9, 0.0), 1e-9)      # just better
    assert not prefer_newton_candidate(math.nextafter(1e-9, 1.0), 1e-9)  # just worse


def test_final_selection_nonfinite_candidates_keep_grid() -> None:
    # frozen semantics: NaN/inf Newton norms are never a strict improvement, so the grid candidate
    # is kept; a finite Newton norm still beats an infinite grid norm (all via the same strict <).
    assert not prefer_newton_candidate(_NAN, 1e-9)
    assert not prefer_newton_candidate(_INF, 1e-9)
    assert not prefer_newton_candidate(_NAN, _NAN)
    assert prefer_newton_candidate(1e-9, _INF)


# ------------------------------------------------------------------ REV1 full-text required pins
def test_convergence_negative_zero_residual() -> None:
    assert newton_converged(ResidualVector2(-0.0, -0.0), _TOL)           # (-0)^2 == 0
    assert newton_converged(ResidualVector2(-0.0, _TOL), _TOL)           # inclusive at the edge


def test_clamp_scalar_infinities_project_to_the_correct_edge() -> None:
    assert clamp_scalar(_INF, 0.35, 0.9) == 0.9
    assert clamp_scalar(-_INF, 0.35, 0.9) == 0.35


def test_clamp_scalar_is_idempotent() -> None:
    for x in (0.5, 0.1, 0.99, 0.35, 0.9):
        once = clamp_scalar(x, 0.35, 0.9)
        assert clamp_scalar(once, 0.35, 0.9) == once


def test_apply_step_clamped_every_violation_pattern() -> None:
    # both below; both above; opposite-side violations; coordinate independence
    assert apply_step_clamped(0.5, 0.6, NewtonStep2(2.0, 2.0), 0.35, 0.9) == (0.35, 0.35)
    assert apply_step_clamped(0.5, 0.6, NewtonStep2(-2.0, -2.0), 0.35, 0.9) == (0.9, 0.9)
    assert apply_step_clamped(0.5, 0.6, NewtonStep2(2.0, -2.0), 0.35, 0.9) == (0.35, 0.9)
    assert apply_step_clamped(0.5, 0.6, NewtonStep2(-2.0, 2.0), 0.35, 0.9) == (0.9, 0.35)
    # clamping one coordinate never perturbs the other
    assert apply_step_clamped(0.5, 0.6, NewtonStep2(2.0, 0.0), 0.35, 0.9) == (0.35, 0.6)
    assert apply_step_clamped(0.5, 0.6, NewtonStep2(0.0, 2.0), 0.35, 0.9) == (0.5, 0.35)


def test_stagnation_one_ulp_movement_and_boundary_clamp_no_movement() -> None:
    # one-ULP movement of a ~0.5-scale point (~1.1e-16) is strictly below 1e-15 -> stagnant
    assert is_stagnant(0.5, 0.6, math.nextafter(0.5, 1.0), 0.6, 1e-15)
    # a clamp that returns the same boundary point produces zero movement -> stagnant
    na = clamp_scalar(0.3, 0.35, 0.9)          # projected to the lower edge 0.35
    assert na == 0.35
    assert is_stagnant(0.35, 0.6, na, 0.6, 1e-15)
