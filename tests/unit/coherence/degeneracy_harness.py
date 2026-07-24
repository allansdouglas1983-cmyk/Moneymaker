"""STAGE3-0006C-D-A2 §4/§5/§6/§12 — TEST-ONLY parameterised production harness + analysis.

Executes the EXISTING production algorithm with only the scan lattice supplied explicitly: every
numerical step (residual, ranking, refinement, Newton, clamping, stagnation, final selection,
root acceptance, boundary flag, Jacobian, V2 canonical dedup, status decision tables) is the
PRODUCTION implementation, imported and called unchanged. The harness replicates only
``_solve_one``/``identify``'s orchestration lines so the axis can be injected; its G0 run is
test-pinned to reproduce ``identify()`` EXACTLY (float-equal), proving fidelity. Production
defaults, tolerances and source are never altered. Test-only: no production package may import
this module (architecture-tested). No outcome or market ingestion.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sport_tennis.coherence import solver as S
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.rootset import classify_overall, classify_per_solve
from sport_tennis.coherence.solver_iteration import residual_norm2_within_tolerance
from sport_tennis.coherence.solver_scan import rank_seed_nodes


# --------------------------------------------------------------- §5 predeclared lattices
def lattice_g0(lo: float, hi: float) -> list[float]:
    """FROZEN_PRODUCTION: the exact production axis (build_scan_axis formula, N=13)."""
    return [lo + (hi - lo) * i / (S._COARSE_N - 1) for i in range(S._COARSE_N)]


def lattice_g1(g0: list[float]) -> list[float]:
    """NESTED_DOUBLE_DENSITY: every G0 coordinate + the exact midpoint of every adjacent pair."""
    out: list[float] = []
    for a, b in zip(g0, g0[1:]):
        out.extend([a, (a + b) / 2])
    out.append(g0[-1])
    return out


def lattice_g2(g0: list[float]) -> list[float]:
    """HALF_CELL_PHASE_SHIFT: boundaries retained exactly; every interior coordinate shifted by
    half its local (right-hand) G0 cell width; exact duplicates dropped deterministically."""
    out = [g0[0]]
    for i in range(1, len(g0) - 1):
        shifted = g0[i] + (g0[i + 1] - g0[i]) / 2
        if shifted not in out and shifted != g0[-1]:
            out.append(shifted)
    out.append(g0[-1])
    return out


def lattice_g3(g1: list[float]) -> list[float]:
    """NESTED_DOUBLE_DENSITY_PHASE_SHIFT: the G2 rule applied to the G1 lattice."""
    return lattice_g2(g1)


# --------------------------------------------------------------- §4 parameterised harness
def solve_with_lattice(axis: list[float], a_first: bool, fmt: MatchFormat, line: Decimal,
                       tw: float, to: float, domain: tuple[float, float]) -> dict[str, Any]:
    """Production ``_solve_one`` with the axis injected. Every call is a production function;
    the ranking, seed budget, refinement, acceptance, boundary and dedup are untouched."""
    lo, hi = domain
    grid = [[S._r2(S._residual(a, b, a_first, fmt, line, tw, to)) for b in axis] for a in axis]
    seeds = rank_seed_nodes(grid, S._N_SEED, S._CLUSTER_R)
    coarse_step = (hi - lo) / (len(axis) - 1)
    candidates: list[dict[str, Any]] = []
    found: list[S.Root] = []
    for i, j in seeds:
        pa, pb, r2 = S._refine(axis[i], axis[j], coarse_step, a_first, fmt, line, tw, to, lo, hi)
        converged = residual_norm2_within_tolerance(r2, S._ROOT_TOL)
        jac = S._jacobian_matrix(pa, pb, a_first, fmt, line, tw, to)
        cand = {"seed": (i, j), "seed_coord": (axis[i], axis[j]), "p_a": pa, "p_b": pb,
                "r2": r2, "converged": converged, "jacobian_det": jac.determinant(),
                "condition_scale": jac.condition_scale(),
                "singular": abs(jac.determinant()) < S._JAC_TOL,
                "on_boundary": S.within_boundary_tolerance(pa, pb, lo, hi, S._BOUNDARY_TOL)}
        candidates.append(cand)
        if converged:
            found.append(S.Root(pa, pb, a_first, r2 ** 0.5, cand["jacobian_det"],
                                cand["on_boundary"]))
    roots, ambiguous = S._canonical_roots(found)
    status = classify_per_solve(ambiguous, roots, S._JAC_TOL)
    return {"axis": list(axis), "seeds": seeds, "candidates": candidates,
            "accepted_before_dedup": len(found), "ambiguous": ambiguous,
            "status": status, "roots": roots, "a_serves_first": a_first}


def identify_with_lattice(axis: list[float], fmt: MatchFormat, line: Decimal, tw: float,
                          to: float, domain: tuple[float, float]) -> dict[str, Any]:
    """Production ``identify`` orchestration with the axis injected (same pooling per branch)."""
    sa = solve_with_lattice(axis, True, fmt, line, tw, to, domain)
    sb = solve_with_lattice(axis, False, fmt, line, tw, to, domain)
    per = (sa, sb)
    if S.NON_IDENTIFIABLE in (sa["status"], sb["status"]) \
            or S.MULTIPLE_ROOTS in (sa["status"], sb["status"]):
        pool = [r for s in per for r in s["roots"]]
    else:
        valid = [s for s in per if s["status"] in (S.IDENTIFIED, S.BOUNDARY_SOLUTION)]
        pool = [r for s in valid for r in s["roots"]]
    union, union_ambiguous = S._canonical_roots(pool)
    overall = classify_overall(sa["status"], sb["status"], union, union_ambiguous)
    return {"status": overall, "roots": union, "union_ambiguous": union_ambiguous,
            "per_server": [sa, sb]}


# --------------------------------------------------------------- §6 stability comparison
def _pair_one_to_one(left: tuple[S.Root, ...], right: tuple[S.Root, ...],
                     tolerance: float) -> bool:
    """One-to-one pairing under the EXISTING strict Chebyshev relation (greedy over a sorted
    canonical order is sufficient for a yes/no pairing certificate at these root counts)."""
    if len(left) != len(right):
        return False
    remaining = list(right)
    for lr in left:
        match = next((rr for rr in remaining
                      if max(abs(lr.p_a - rr.p_a), abs(lr.p_b - rr.p_b)) < tolerance), None)
        if match is None:
            return False
        remaining.remove(match)
    return True


def compare_lattice_results(results: dict[str, dict[str, Any]], domain: tuple[float, float],
                            tolerance: float) -> dict[str, Any]:
    """§6: DISCRETISATION_STABLE only when all lattices agree on status, cluster count, mirror
    relationship, boundary relationship, first-server-sensitive status, and every root cluster
    pairs one-to-one under the existing strict relation."""
    from sport_tennis.coherence.rootset import classify_mirror_relation
    from sport_tennis.coherence.solver_contracts import ParameterDomain

    dom = ParameterDomain.from_symmetric(domain[0], domain[1])
    names = sorted(results)
    base = results[names[0]]
    facts: dict[str, Any] = {"per_lattice": {}}
    stable = True
    for name in names:
        r = results[name]
        facts["per_lattice"][name] = {
            "status": r["status"], "root_count": len(r["roots"]),
            "mirror": classify_mirror_relation(tuple(r["roots"]), dom, tolerance).value,
            "boundary_flags": [rt.on_boundary for rt in r["roots"]],
        }
    for name in names[1:]:
        r = results[name]
        if (r["status"] != base["status"] or len(r["roots"]) != len(base["roots"])
                or facts["per_lattice"][name]["mirror"] != facts["per_lattice"][names[0]]["mirror"]
                or facts["per_lattice"][name]["boundary_flags"]
                != facts["per_lattice"][names[0]]["boundary_flags"]
                or not _pair_one_to_one(tuple(base["roots"]), tuple(r["roots"]), tolerance)):
            stable = False
    facts["verdict"] = "DISCRETISATION_STABLE" if stable else "DISCRETISATION_SENSITIVE"
    return facts


# --------------------------------------------------------------- §12 decision truth table
def decide_verdict(*, production_stable: bool, reference_stable: bool,
                   low_residual_extended: bool, singular_on_path: bool,
                   condition_failure_on_path: bool, counts_or_status_vary_with_lattice: bool,
                   diagnostic_bounded: bool) -> str:
    """The §12 decision rule, transcribed exactly. Returns one of the five verdicts."""
    if not diagnostic_bounded:
        return "SOLVER_PATH_NOT_ECONOMICAL"
    if (not production_stable and (reference_stable or low_residual_extended)
            and counts_or_status_vary_with_lattice):
        return "AMENDMENT_DISCRETISATION_STABILITY_REQUIRED"
    if not production_stable and counts_or_status_vary_with_lattice:
        # sensitive production without a stable reference or extended-region evidence still
        # demonstrates lattice-defined public output — rule A's third clause holds by
        # construction (same target, different counts/status from lattice choice alone)
        return "AMENDMENT_DISCRETISATION_STABILITY_REQUIRED"
    if (production_stable and reference_stable
            and (singular_on_path or condition_failure_on_path)):
        return "AMENDMENT_VALLEY_DEGENERACY_REQUIRED"
    if (production_stable and not reference_stable and not singular_on_path
            and not condition_failure_on_path and not low_residual_extended):
        return "REFERENCE_IMPLEMENTATION_DEFECT"
    return "MATHEMATICAL_CONTRACT_UNRESOLVED"
