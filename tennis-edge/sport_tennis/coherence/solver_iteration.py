"""CROSS_MARKET_COHERENCE_V1 — undamped Newton-polish iteration seams (STAGE3-0006C-C-REV1).

Named, individually-testable seams for the identification solver's Newton polish. Every function
reproduces the solver's frozen float arithmetic BYTE-IDENTICALLY (SOLVER_MILESTONE_C_PRECHANGE.json);
the golden oracle guards the end-to-end contract and the Milestone C seam tests guard each function
in isolation. SYNTHETIC-ONLY; reads no market prices and no outcomes. Import-quarantined from
execution/pricing/V0.

Reality-bound scope (REV1 §1): the polish is an UNDAMPED, CLAMP-PROJECTED Newton iteration —
residual-only inclusive convergence, full step at factor 1.0, silent clamp projection into the
domain, a stagnation break, the Milestone-B singularity break, and a final grid-versus-Newton
strict-improvement selection. The following constructs DO NOT EXIST and are deliberately absent
(descriptive findings, not settings): STEP_TOLERANCE_NOT_USED, DAMPING_SCHEDULE_NOT_USED,
DAMPING_FACTOR_NOT_USED, MAXIMUM_DAMPING_ATTEMPTS_NOT_USED, MULTI_FACTOR_LINE_SEARCH_NOT_USED,
PER_STEP_IMPROVEMENT_ACCEPTANCE_NOT_USED, FIRST_ACCEPTED_FACTOR_POLICY_NOT_USED.

Frozen incidental behaviour preserved on purpose: NaN residuals never converge (the inclusive
comparison is False); ``clamp_scalar`` uses strict comparisons so an input exactly equal to a bound
is returned as the input object (signed zero survives) and NaN passes through.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver_contracts import Jacobian2x2, ResidualVector2


@dataclass(frozen=True)
class NewtonStep2:
    """One proposed (undamped) Newton step in canonical (p_A, p_B) component order. Immutable.
    The solver SUBTRACTS the deltas: next = (p_a - delta_a, p_b - delta_b)."""

    delta_a: float
    delta_b: float

    def validate(self) -> None:
        if not (math.isfinite(self.delta_a) and math.isfinite(self.delta_b)):
            raise CoherenceMathError("Newton step components must be finite")

    def inf_norm(self) -> float:
        return max(abs(self.delta_a), abs(self.delta_b))

    def serialize(self) -> dict[str, float]:
        return {"delta_a": self.delta_a, "delta_b": self.delta_b}


# --------------------------------------------------------------------- convergence (residual-only)
def residual_norm2_within_tolerance(residual_norm2: float, residual_tolerance: float) -> bool:
    """The frozen convergence/root rule on the squared 2-norm: ``r2 <= tol*tol`` (INCLUSIVE).
    Byte-identical to the solver's ``f1*f1 + f2*f2 <= _ROOT_TOL * _ROOT_TOL`` and to the root
    acceptance ``r2 <= _ROOT_TOL * _ROOT_TOL``. A NaN norm compares False (never converged)."""
    return residual_norm2 <= residual_tolerance * residual_tolerance


def newton_converged(residual: ResidualVector2, residual_tolerance: float) -> bool:
    """Residual-only convergence for one iterate. No step tolerance participates
    (STEP_TOLERANCE_NOT_USED)."""
    return residual_norm2_within_tolerance(residual.sum_of_squares(), residual_tolerance)


# --------------------------------------------------------------------- iteration budget
def _require_index(value: int, role: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CoherenceMathError(f"{role} must be a plain int, got {value!r}")


def iteration_is_permitted(iteration_index: int, maximum_iterations: int) -> bool:
    """``range(maximum_iterations)`` semantics, byte-identical to the frozen
    ``for _ in range(_NEWTON_ITERS)``: the body runs for indices 0 .. maximum-1; the exact maximum
    is refused. Booleans and non-integers are refused, never coerced."""
    _require_index(iteration_index, "iteration_index")
    _require_index(maximum_iterations, "maximum_iterations")
    return 0 <= iteration_index < maximum_iterations


def next_iteration_index(iteration_index: int) -> int:
    """The frozen counter transition: increment by exactly one. No reset, skip, or wrap."""
    _require_index(iteration_index, "iteration_index")
    return iteration_index + 1


# --------------------------------------------------------------------- Newton step (undamped)
def propose_newton_step(residual: ResidualVector2, jacobian: Jacobian2x2) -> NewtonStep2:
    """The frozen exact 2x2 Cramer solve of J·d = F. Rows are (match-odds, total-games); columns
    are (p_A, p_B). Byte-identical to the solver's inline
    ``da = (d22*f1 - d12*f2)/det; db = (-d21*f1 + d11*f2)/det`` with ``det = d11*d22 - d12*d21``.
    Singularity is refused BEFORE entry via the Milestone-B ``is_singular`` seam; no damping and no
    projection happen here."""
    det = jacobian.determinant()
    f1 = residual.match_odds_residual
    f2 = residual.total_games_residual
    return NewtonStep2(
        delta_a=(jacobian.d_tg_d_b * f1 - jacobian.d_mo_d_b * f2) / det,
        delta_b=(-jacobian.d_tg_d_a * f1 + jacobian.d_mo_d_a * f2) / det,
    )


# --------------------------------------------------------------------- clamp projection
def clamp_scalar(x: float, lo: float, hi: float) -> float:
    """The frozen clamp: ``lo if x < lo else hi if x > hi else x``. Strict comparisons — an input
    exactly equal to a bound is returned as the input object (signed zero preserved) and NaN passes
    through unchanged. This SILENT projection is the solver's actual domain behaviour
    (DOMAIN_HANDLING_IS_CLAMP_PROJECTION); no reject-out-of-domain rule exists."""
    return lo if x < lo else hi if x > hi else x


def apply_step_clamped(p_a: float, p_b: float, step: NewtonStep2, lo: float,
                       hi: float) -> tuple[float, float]:
    """The frozen full-step application: SUBTRACT each delta, then clamp-project each coordinate.
    Byte-identical to ``_clamp(pa - da, lo, hi), _clamp(pb - db, lo, hi)``. Always factor 1.0
    (DAMPING_FACTOR_NOT_USED)."""
    return clamp_scalar(p_a - step.delta_a, lo, hi), clamp_scalar(p_b - step.delta_b, lo, hi)


# --------------------------------------------------------------------- stagnation + final selection
def is_stagnant(p_a: float, p_b: float, new_a: float, new_b: float,
                movement_tolerance: float) -> bool:
    """The frozen stagnation break: absolute movement strictly below the tolerance on BOTH axes.
    Byte-identical to ``abs(na - pa) < 1e-15 and abs(nb - pb) < 1e-15``. A termination condition,
    not a convergence success and not a step-acceptance rule
    (PER_STEP_IMPROVEMENT_ACCEPTANCE_NOT_USED)."""
    return abs(new_a - p_a) < movement_tolerance and abs(new_b - p_b) < movement_tolerance


def prefer_newton_candidate(newton_norm2: float, grid_norm2: float) -> bool:
    """The frozen FINAL grid-versus-Newton selection: the polished point replaces the grid point
    only on STRICT improvement of the squared residual norm (``newton_r < best_r``). Ties keep the
    grid point. This is the only residual-improvement comparison in the polish."""
    return newton_norm2 < grid_norm2
