"""STAGE3-0006C-C-REV1 §17 — INDEPENDENT test-only reference oracles for the iteration seams.

This module is the independence boundary: it must import NOTHING from ``sport_tennis`` (enforced
by an architecture test). Expected values are computed from literal equations or exact Decimal
arithmetic only, so the comparison tests cannot inherit a defect from the production seams.
"""
from __future__ import annotations

from decimal import Decimal


def converged_literal(f1: float, f2: float, tol: float) -> bool:
    """The frozen convergence rule, literally: f1*f1 + f2*f2 <= tol*tol (inclusive)."""
    return f1 * f1 + f2 * f2 <= tol * tol


def budget_literal(index: int, maximum: int) -> bool:
    """range() semantics, literally: the loop body runs for indices 0 .. maximum-1."""
    return index in range(maximum)


def clamp_literal(x: float, lo: float, hi: float) -> float:
    """The frozen clamp, literally (strict comparisons, input object passthrough otherwise)."""
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def newton_step_decimal(f1: float, f2: float, d11: float, d21: float, d12: float,
                        d22: float) -> tuple[Decimal, Decimal]:
    """Exact Decimal solve of J·d = F with J rows (match-odds, total-games) and columns
    (p_A, p_B): d11=dMO/dA, d21=dTG/dA, d12=dMO/dB, d22=dTG/dB. Cramer form identical to the
    frozen implementation: da = (d22*f1 - d12*f2)/det, db = (-d21*f1 + d11*f2)/det."""
    det = Decimal(d11) * Decimal(d22) - Decimal(d12) * Decimal(d21)
    da = (Decimal(d22) * Decimal(f1) - Decimal(d12) * Decimal(f2)) / det
    db = (-Decimal(d21) * Decimal(f1) + Decimal(d11) * Decimal(f2)) / det
    return da, db


def stagnant_literal(p_a: float, p_b: float, new_a: float, new_b: float, tol: float) -> bool:
    """The frozen stagnation break, literally: abs-movement strictly below tol on BOTH axes."""
    return abs(new_a - p_a) < tol and abs(new_b - p_b) < tol


def prefer_newton_literal(newton_r2: float, grid_r2: float) -> bool:
    """The frozen final selection, literally: Newton wins only on strict improvement."""
    return newton_r2 < grid_r2
