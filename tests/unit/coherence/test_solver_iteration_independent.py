"""STAGE3-0006C-C-REV1 §17 — independent semantic checks for the iteration seams.

Expected values come ONLY from ``iteration_reference`` (literal equations / exact Decimal), which
imports nothing from ``sport_tennis`` — enforced here by an architecture test. The comparisons
sweep deterministic fixtures including ``math.nextafter`` boundaries, so a production-seam defect
cannot be mirrored into the oracle.
"""
from __future__ import annotations

import ast
import math
from pathlib import Path

from sport_tennis.coherence.solver_contracts import Jacobian2x2, ResidualVector2
from sport_tennis.coherence.solver_iteration import (
    clamp_scalar,
    is_stagnant,
    iteration_is_permitted,
    newton_converged,
    prefer_newton_candidate,
    propose_newton_step,
)

from . import iteration_reference as ref

_TOL = 1e-4


# ------------------------------------------------------------------ architecture boundary
def test_reference_module_is_independent_of_production() -> None:
    src = (Path(__file__).parent / "iteration_reference.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for n in names:
            assert not n.startswith("sport_tennis"), f"reference imports production: {n}"
            assert "solver_iteration" not in n, f"reference imports the seams under test: {n}"


# ------------------------------------------------------------------ convergence truth
def test_convergence_matches_literal_rule_across_boundary_sweep() -> None:
    t2 = _TOL * _TOL
    probes = [0.0, 1e-9, math.nextafter(_TOL, 0.0), _TOL, math.nextafter(_TOL, 1.0),
              1e-3, math.sqrt(t2 / 2.0), -_TOL]
    for f1 in probes:
        for f2 in probes:
            assert newton_converged(ResidualVector2(f1, f2), _TOL) \
                == ref.converged_literal(f1, f2, _TOL), (f1, f2)


# ------------------------------------------------------------------ iteration-budget boundary
def test_budget_matches_range_semantics() -> None:
    for maximum in (1, 2, 40):
        for index in (-2, -1, 0, 1, maximum - 2, maximum - 1, maximum, maximum + 1, 10**6):
            assert iteration_is_permitted(index, maximum) \
                == ref.budget_literal(index, maximum), (index, maximum)


# ------------------------------------------------------------------ exact 2x2 Newton solution
def test_newton_step_matches_decimal_cramer_and_reconstructs_residual() -> None:
    fixtures = [
        (0.11, 0.23, 2.0, 5.0, 3.0, 7.0),
        (0.3, -0.2, 1.0, 0.0, 0.0, 1.0),
        (-0.05, 0.4, 4.0, -1.5, 2.5, 6.0),
        (1e-3, -2e-3, 0.7, 0.2, -0.4, 1.1),
    ]
    for f1, f2, d11, d21, d12, d22 in fixtures:
        j = Jacobian2x2(d_mo_d_a=d11, d_mo_d_b=d12, d_tg_d_a=d21, d_tg_d_b=d22)
        s = propose_newton_step(ResidualVector2(f1, f2), j)
        da_ref, db_ref = ref.newton_step_decimal(f1, f2, d11, d21, d12, d22)
        assert abs(s.delta_a - float(da_ref)) <= 1e-12 * max(1.0, abs(float(da_ref)))
        assert abs(s.delta_b - float(db_ref)) <= 1e-12 * max(1.0, abs(float(db_ref)))
        # independent reconstruction: J @ step must reproduce the residual (Cramer correctness)
        assert abs(d11 * s.delta_a + d12 * s.delta_b - f1) <= 1e-9
        assert abs(d21 * s.delta_a + d22 * s.delta_b - f2) <= 1e-9


# ------------------------------------------------------------------ clamp membership
def test_clamp_matches_literal_across_boundary_sweep() -> None:
    lo, hi = 0.35, 0.9
    probes = [0.0, math.nextafter(lo, 0.0), lo, math.nextafter(lo, 1.0), 0.5,
              math.nextafter(hi, 0.0), hi, math.nextafter(hi, 1.0), 1.0, -0.0]
    for x in probes:
        got, want = clamp_scalar(x, lo, hi), ref.clamp_literal(x, lo, hi)
        assert got == want and math.copysign(1.0, got) == math.copysign(1.0, want), x


# ------------------------------------------------------------------ stagnation + selection truth
def test_stagnation_and_selection_match_literal() -> None:
    t = 1e-15
    moves = [0.0, math.nextafter(t, 0.0), t, math.nextafter(t, 1.0), 1e-3, -1e-3]
    for da in moves:
        for db in moves:
            assert is_stagnant(0.5, 0.6, 0.5 + da, 0.6 + db, t) \
                == ref.stagnant_literal(0.5, 0.6, 0.5 + da, 0.6 + db, t), (da, db)
    r2s = [0.0, 1e-10, math.nextafter(1e-9, 0.0), 1e-9, math.nextafter(1e-9, 1.0), 1e-3]
    for n in r2s:
        for g in r2s:
            assert prefer_newton_candidate(n, g) == ref.prefer_newton_literal(n, g), (n, g)
