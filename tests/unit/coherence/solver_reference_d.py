"""STAGE3-0006C-D-REV2 §17 — INDEPENDENT test-only reference solver for root-set/status evidence.

Permitted imports ONLY: the stable scoring generator (match_distribution / over_under) and the
immutable format contract (MatchFormat) — enforced by an AST architecture test. Everything else is
literal and self-contained: own dense grid (a DIFFERENT resolution from production), own residuals,
own shrink refinement (no Newton), own central-difference Jacobian determinant, brute-force
fixpoint dedup (via dedup_reference, itself import-clean), literal mirror/boundary/status
classification transcribed from the governed registrations.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.match import match_distribution
from sport_tennis.coherence.pmf import over_under

from .dedup_reference import ref_dedup, ref_distance

_ROOT_TOL = 1e-4      # governed public constants, transcribed literally
_DEDUP_TOL = 1e-3
_JAC_TOL = 5e-3
_BOUNDARY_TOL = 5e-3


class RefRoot:
    """Duck-typed candidate compatible with dedup_reference (attributes only)."""

    def __init__(self, p_a: float, p_b: float, a_serves_first: bool, residual: float,
                 jacobian_det: float, on_boundary: bool) -> None:
        self.p_a, self.p_b = p_a, p_b
        self.a_serves_first = a_serves_first
        self.residual = residual
        self.jacobian_det = jacobian_det
        self.on_boundary = on_boundary

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"RefRoot({self.p_a:.6f},{self.p_b:.6f},{self.a_serves_first})"


def ref_residual(pa: float, pb: float, a_first: bool, fmt: MatchFormat, line: Decimal,
                 tw: float, to: float) -> tuple[float, float]:
    md = match_distribution(pa, pb, fmt, a_serves_first_match=a_first)
    return md.match_win_a - tw, over_under(md.total_games_pmf, line).over - to


def _norm2(f: tuple[float, float]) -> float:
    return f[0] * f[0] + f[1] * f[1]


def _jac_det(pa: float, pb: float, a_first: bool, fmt: MatchFormat, line: Decimal,
             tw: float, to: float) -> float:
    e = 1e-3
    ap, am = min(pa + e, 0.99), max(pa - e, 0.01)
    bp, bm = min(pb + e, 0.99), max(pb - e, 0.01)
    fa_p = ref_residual(ap, pb, a_first, fmt, line, tw, to)
    fa_m = ref_residual(am, pb, a_first, fmt, line, tw, to)
    fb_p = ref_residual(pa, bp, a_first, fmt, line, tw, to)
    fb_m = ref_residual(pa, bm, a_first, fmt, line, tw, to)
    d11 = (fa_p[0] - fa_m[0]) / (ap - am)
    d21 = (fa_p[1] - fa_m[1]) / (ap - am)
    d12 = (fb_p[0] - fb_m[0]) / (bp - bm)
    d22 = (fb_p[1] - fb_m[1]) / (bp - bm)
    return d11 * d22 - d12 * d21


def ref_solve_assignment(a_first: bool, fmt: MatchFormat, line: Decimal, tw: float, to: float,
                         lo: float, hi: float, n: int = 27) -> list[RefRoot]:
    """Own dense scan (n x n, deliberately != production 13) + own shrink refinement."""
    axis = [lo + (hi - lo) * k / (n - 1) for k in range(n)]
    norms = [[_norm2(ref_residual(a, b, a_first, fmt, line, tw, to)) for b in axis] for a in axis]
    seeds = []
    for i in range(n):
        for j in range(n):
            v = norms[i][j]
            neigh = [norms[x][y] for x in range(max(0, i - 1), min(n, i + 2))
                     for y in range(max(0, j - 1), min(n, j + 2)) if (x, y) != (i, j)]
            if all(v <= w for w in neigh):
                seeds.append((axis[i], axis[j]))
    roots: list[RefRoot] = []
    for ca, cb in seeds:
        h = (hi - lo) / (n - 1)
        best_a, best_b = ca, cb
        best = _norm2(ref_residual(ca, cb, a_first, fmt, line, tw, to))
        # adaptive walk-then-shrink: keep moving at the CURRENT scale until no improvement (this
        # tracks the solver's narrow diagonal residual valley, which a fixed-shrink axis-aligned
        # window cannot follow), then halve the scale. Bounded by the guard and the scale floor.
        while h > 1e-9:
            improved, guard = True, 0
            while improved and guard < 80:
                improved, guard = False, guard + 1
                for ia in range(5):
                    pa = min(max(best_a - h + h / 2 * ia, lo), hi)
                    for ib in range(5):
                        pb = min(max(best_b - h + h / 2 * ib, lo), hi)
                        v = _norm2(ref_residual(pa, pb, a_first, fmt, line, tw, to))
                        if v < best:
                            best, best_a, best_b = v, pa, pb
                            improved = True
            h *= 0.5
        if best <= _ROOT_TOL * _ROOT_TOL:
            jd = _jac_det(best_a, best_b, a_first, fmt, line, tw, to)
            on_b = min(best_a - lo, hi - best_a, best_b - lo, hi - best_b) < _BOUNDARY_TOL
            roots.append(RefRoot(best_a, best_b, a_first, best ** 0.5, jd, on_b))
    # collapse refinement duplicates from the same basin (literal, distance-based)
    kept: list[RefRoot] = []
    for r in roots:
        if not any(ref_distance(r, k) < _DEDUP_TOL for k in kept):
            kept.append(r)
    return kept


def ref_identify(fmt: MatchFormat, line: Decimal, tw: float, to: float,
                 lo: float, hi: float) -> dict[str, Any]:
    """Literal end-to-end reference: both assignments, literal per-solve status, literal union."""
    per = {}
    for a_first in (True, False):
        cands = ref_solve_assignment(a_first, fmt, line, tw, to, lo, hi)
        dd = ref_dedup(cands, _DEDUP_TOL)
        reps = dd["representatives"]
        if dd["ambiguous"]:
            status = "NON_IDENTIFIABLE"
        elif not reps:
            status = "NO_ROOT"
        elif len(reps) > 1:
            status = "MULTIPLE_ROOTS"
        elif abs(reps[0].jacobian_det) < _JAC_TOL:
            status = "NON_IDENTIFIABLE"
        elif reps[0].on_boundary:
            status = "BOUNDARY_SOLUTION"
        else:
            status = "IDENTIFIED"
        per[a_first] = {"status": status, "roots": reps}
    sa, sb = per[True]["status"], per[False]["status"]
    if "NON_IDENTIFIABLE" in (sa, sb):
        overall = "NON_IDENTIFIABLE"
        pool = per[True]["roots"] + per[False]["roots"]
    elif "MULTIPLE_ROOTS" in (sa, sb):
        pool = per[True]["roots"] + per[False]["roots"]
        overall = "MULTIPLE_ROOTS"
    else:
        pool = [r for a in (True, False)
                if per[a]["status"] in ("IDENTIFIED", "BOUNDARY_SOLUTION")
                for r in per[a]["roots"]]
        overall = None
    union = ref_dedup(pool, _DEDUP_TOL)
    reps = union["representatives"]
    if overall is None:
        if union["ambiguous"]:
            overall = "NON_IDENTIFIABLE"
        elif not reps:
            overall = "NO_ROOT"
        elif len(reps) == 1:
            overall = "BOUNDARY_SOLUTION" if reps[0].on_boundary else "IDENTIFIED"
        else:
            overall = "FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD"
    elif union["ambiguous"]:
        overall = "NON_IDENTIFIABLE"
    return {"status": overall, "roots": reps, "per": {True: sa, False: sb}}
