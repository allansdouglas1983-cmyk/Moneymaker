"""CROSS_MARKET_COHERENCE_V1 — PRODUCTION identification solver (STAGE3-0005 §13/§14/§15).

SYNTHETIC-ONLY, deterministic. Given a format and two target observations — the Match-Odds
implied win probability for player A and the Over probability of ONE selected Total-Games line —
recovers the two latent serve parameters (p_a, p_b) by a **deterministic bounded 2-D root
solve**: a fixed-resolution coarse residual scan over the parameter domain, isolation of every
local-minimum cell, and a fixed-depth nested-grid refinement of each. No random restarts, no
outcome data, no market prices beyond the two supplied target numbers.

First server is a NUISANCE parameter (§2.4): the solve is run for BOTH ``A serves first`` and
``B serves first`` with NO 50/50 prior; the union of solutions is returned. When the two serve
assignments do not converge to the same (p_a, p_b) up to the solver's dedup precision the result
is ``FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD`` — the solver does NOT decide whether the
difference is material (that threshold is founder-pending, coherence-v1.yaml).

Only the structural statuses permitted by coherence-v1.yaml §15 are emitted; categorical
coherence verdicts (COHERENT / INCOHERENT / ...) are NOT produced here. Import-quarantined from
execution/pricing/V0/research.xmarket.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sport_tennis.coherence.discretisation_stability import (
    StabilityDecision,
    VariantSolveSnapshot,
    compare_registered_variants,
)
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.match import match_distribution
from sport_tennis.coherence.pmf import over_under
from sport_tennis.coherence.root_dedup import deduplicate_roots
from sport_tennis.coherence.rootset import (
    classify_overall,
    classify_per_solve,
    within_boundary_tolerance,
)
from sport_tennis.coherence.scan_variants import (
    REGISTERED_VARIANT_ORDER,
    axis_digest,
    variant_axis,
)
from sport_tennis.coherence.solver_contracts import (
    Jacobian2x2,
    ParameterDomain,
    ResidualVector2,
    SolverStatus,
    validate_domain,
    validate_targets,
)
from sport_tennis.coherence.solver_iteration import (
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
from sport_tennis.coherence.solver_scan import (
    build_scan_axis,
    is_singular,
    jacobian_from_differences,
    perturbation_points,
    rank_seed_nodes,
)

# ------------------------------------------------------------- solver numerics (NOT thresholds)
# These are numerical constants of the root solve (grid resolution, refinement depth, matching
# precision). They are NOT the founder-pending coherence or first-server materiality thresholds;
# they never map a residual to a coherence verdict.
_COARSE_N = 13            # coarse scan nodes per axis
_N_SEED = 20              # lowest-residual coarse nodes taken as refinement seeds
_CLUSTER_R = 2            # coarse-index radius within which seeds share one refinement
_REFINE_LEVELS = 6        # nested-grid pre-polish depth (bring the seed onto the valley)
_REFINE_K = 5             # refinement window nodes per axis
_REFINE_SHRINK = 0.5      # window half-width shrink per level
_NEWTON_ITERS = 40        # bounded undamped clamp-projected Newton polish iterations
_NEWTON_SINGULAR = 1e-10  # |det J| below which Newton cannot step (leaves the grid estimate)
_STAGNATION_TOL = 1e-15   # movement strictly below this on BOTH axes stops the Newton polish
_ROOT_TOL = 1e-4          # max per-equation residual for a point to count as a root
_DEDUP_TOL = 1e-3         # max-norm distance below which two roots are the same point
_JAC_EPS = 1e-3           # central-difference step for the identification Jacobian
_JAC_TOL = 5e-3           # |det J| below which identification is degenerate (NON_IDENTIFIABLE)
_BOUNDARY_TOL = 5e-3      # distance to the domain edge below which a root is a boundary solution

# Per-assignment structural statuses (subset of coherence-v1.yaml §15). The public string values
# are sourced from the governed SolverStatus enum (STAGE3-0006C Milestone A) so the vocabulary has
# a single closed definition; the string values are unchanged (byte-identical public contract).
NO_ROOT = SolverStatus.NO_ROOT.value
IDENTIFIED = SolverStatus.IDENTIFIED.value
MULTIPLE_ROOTS = SolverStatus.MULTIPLE_ROOTS.value
NON_IDENTIFIABLE = SolverStatus.NON_IDENTIFIABLE.value
BOUNDARY_SOLUTION = SolverStatus.BOUNDARY_SOLUTION.value
FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD = SolverStatus.FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD.value


@dataclass(frozen=True)
class Root:
    """A recovered parameter pair under a fixed first-server assignment. Outcome-free."""

    p_a: float
    p_b: float
    a_serves_first: bool
    residual: float
    jacobian_det: float
    on_boundary: bool


@dataclass(frozen=True)
class ServerSolve:
    """Result of the bounded root solve under ONE first-server assignment.

    ``stability`` (CROSS_MARKET_COHERENCE_DISCRETISATION_STABILITY_AMENDMENT_V1) carries the
    immutable registered-variant agreement evidence when the assignment was solved through the
    stability-checked path; it is ``None`` only for a bare single-axis solve."""

    a_serves_first: bool
    status: str
    roots: tuple[Root, ...]
    stability: StabilityDecision | None = None


@dataclass(frozen=True)
class IdentificationResult:
    """Union identification result across both first-server assignments (§14)."""

    status: str
    roots: tuple[Root, ...]
    per_server: tuple[ServerSolve, ServerSolve]
    domain: tuple[float, float]
    line: Decimal
    fmt: MatchFormat


def derived_targets(p_a: float, p_b: float, fmt: MatchFormat, line: Decimal, *,
                    a_serves_first: bool) -> tuple[float, float]:
    """The two identification observables produced by a known parameter pair: (match-win-A,
    Over-probability at ``line``). Used to build synthetic targets. Outcome-free."""
    md = match_distribution(p_a, p_b, fmt, a_serves_first_match=a_serves_first)
    return md.match_win_a, over_under(md.total_games_pmf, line).over


def _validate_domain(domain: tuple[float, float]) -> None:
    validate_domain(domain[0], domain[1])


def _clamp(x: float, lo: float, hi: float) -> float:
    # Thin adapter over the closed clamp seam (STAGE3-0006C-C); semantics byte-identical, and the
    # existing direct pins (test_solver_units_fast.test_clamp_exact) are unchanged.
    return clamp_scalar(x, lo, hi)


def _residual(p_a: float, p_b: float, a_first: bool, fmt: MatchFormat, line: Decimal,
              tw: float, to: float) -> tuple[float, float]:
    md = match_distribution(p_a, p_b, fmt, a_serves_first_match=a_first)
    f1 = md.match_win_a - tw
    f2 = over_under(md.total_games_pmf, line).over - to
    return f1, f2


def _r2(f: tuple[float, float]) -> float:
    # Residual 2-norm-squared via the closed ResidualVector2 contract (§6): mo*mo + tg*tg,
    # byte-identical to f[0]*f[0] + f[1]*f[1].
    return ResidualVector2(f[0], f[1]).sum_of_squares()


def _refine(ca: float, cb: float, h: float, a_first: bool, fmt: MatchFormat, line: Decimal,
            tw: float, to: float, lo: float, hi: float) -> tuple[float, float, float]:
    """Deterministic nested-grid refinement around (ca, cb). Returns (p_a, p_b, residual2)."""
    step = 2.0 * h / (_REFINE_K - 1)
    best_r = _r2(_residual(ca, cb, a_first, fmt, line, tw, to))
    best_a, best_b = ca, cb
    for _ in range(_REFINE_LEVELS):
        for ia in range(_REFINE_K):
            pa = _clamp(ca - h + step * ia, lo, hi)
            for ib in range(_REFINE_K):
                pb = _clamp(cb - h + step * ib, lo, hi)
                r = _r2(_residual(pa, pb, a_first, fmt, line, tw, to))
                if r < best_r:
                    best_r, best_a, best_b = r, pa, pb
        ca, cb = best_a, best_b
        h *= _REFINE_SHRINK
        step = 2.0 * h / (_REFINE_K - 1)

    # Newton polish (STAGE3-0006C-C seams): a deterministic bounded UNDAMPED clamp-projected
    # Newton iteration on F=(F1,F2) using the numeric Jacobian. Converges precisely in shallow
    # valleys where the nested grid stalls; if the Jacobian is singular (a degenerate/flat
    # direction) it cannot step and the grid estimate is kept for classification. Each full step
    # is taken unconditionally after clamp projection; the only in-loop terminations are
    # convergence, singularity and stagnation, and the polished point replaces the grid point only
    # on strict final improvement.
    pa, pb = best_a, best_b
    it = 0
    while iteration_is_permitted(it, _NEWTON_ITERS):
        res = ResidualVector2(*_residual(pa, pb, a_first, fmt, line, tw, to))
        if newton_converged(res, _ROOT_TOL):
            break
        jac = _jacobian_matrix(pa, pb, a_first, fmt, line, tw, to)
        if is_singular(jac.determinant(), _NEWTON_SINGULAR):
            break
        na, nb = apply_step_clamped(pa, pb, propose_newton_step(res, jac), lo, hi)
        if is_stagnant(pa, pb, na, nb, _STAGNATION_TOL):
            break
        pa, pb = na, nb
        it = next_iteration_index(it)
    newton_r = _r2(_residual(pa, pb, a_first, fmt, line, tw, to))
    if prefer_newton_candidate(newton_r, best_r):
        return pa, pb, newton_r
    return best_a, best_b, best_r


def _jacobian_matrix(p_a: float, p_b: float, a_first: bool, fmt: MatchFormat, line: Decimal,
                     tw: float, to: float) -> Jacobian2x2:
    """Central-difference identification Jacobian of (F1, F2) w.r.t. (p_a, p_b), assembled through
    the ``perturbation_points`` (§8a) and ``jacobian_from_differences`` (§8b) seams into the closed
    ``Jacobian2x2`` contract. Byte-identical to the prior inline difference quotients."""
    ap, am = perturbation_points(p_a, _JAC_EPS, 0.01, 0.99)
    bp, bm = perturbation_points(p_b, _JAC_EPS, 0.01, 0.99)
    fa_p = _residual(ap, p_b, a_first, fmt, line, tw, to)
    fa_m = _residual(am, p_b, a_first, fmt, line, tw, to)
    fb_p = _residual(p_a, bp, a_first, fmt, line, tw, to)
    fb_m = _residual(p_a, bm, a_first, fmt, line, tw, to)
    return jacobian_from_differences(fa_p, fa_m, fb_p, fb_m, ap - am, bp - bm)


def _jacobian(p_a: float, p_b: float, a_first: bool, fmt: MatchFormat, line: Decimal,
              tw: float, to: float) -> tuple[float, float, float, float]:
    """Tuple view (d11, d21, d12, d22) = (d_mo_d_a, d_tg_d_a, d_mo_d_b, d_tg_d_b) of the
    ``_jacobian_matrix`` seam. Signature preserved byte-for-byte so the existing direct pin
    (``test_solver_units_fast.test_jacobian_exact``) is unchanged by the seam extraction."""
    j = _jacobian_matrix(p_a, p_b, a_first, fmt, line, tw, to)
    return j.d_mo_d_a, j.d_tg_d_a, j.d_mo_d_b, j.d_tg_d_b


def _jacobian_det(p_a: float, p_b: float, a_first: bool, fmt: MatchFormat, line: Decimal,
                  tw: float, to: float) -> float:
    return _jacobian_matrix(p_a, p_b, a_first, fmt, line, tw, to).determinant()


def _canonical_roots(candidates: list[Root]) -> tuple[tuple[Root, ...], bool]:
    """Set-defined canonical deduplication (STAGE3-0006C-D-A1, replaces the sequence-defined
    greedy first-seen rule). Returns the canonically ordered valid-cluster representatives and
    whether any non-transitive tolerance chain was refused (AMBIGUOUS_ROOT_TOLERANCE_CHAIN —
    mapped by callers to the existing public NON_IDENTIFIABLE)."""
    result = deduplicate_roots(candidates, _DEDUP_TOL)
    return result.representatives(), result.ambiguous


def _solve_one_on_axis(a_first: bool, fmt: MatchFormat, line: Decimal, tw: float, to: float,
                       domain: tuple[float, float], axis: list[float]) -> ServerSolve:
    """The bounded solve with the scan axis supplied (STAGE3-0006C-D-A3 §6). For the G0 axis
    this is byte-identical to the pre-amendment ``_solve_one`` body: the step formula
    ``(hi - lo) / (len(axis) - 1)`` equals the former ``(hi - lo) / (_COARSE_N - 1)``."""
    lo, hi = domain
    grid = [[_r2(_residual(a, b, a_first, fmt, line, tw, to)) for b in axis] for a in axis]

    # Seed refinement from the lowest-residual coarse nodes, clustered so each deep basin is
    # refined once (§7 seed-selection rule; §5 scan-cell folded in — see solver_scan docstring).
    # A strict local-minimum test misses a narrow diagonal residual valley that falls BETWEEN
    # coarse nodes; taking the smallest-residual nodes brackets it from both sides. Distinct basins
    # (e.g. the mirror parameter pair) stay in separate clusters and are each refined, so genuine
    # multiplicity is detected rather than collapsed.
    seeds = rank_seed_nodes(grid, _N_SEED, _CLUSTER_R)

    coarse_step = (hi - lo) / (len(axis) - 1)
    found: list[Root] = []
    for i, j in seeds:
        pa, pb, r2 = _refine(axis[i], axis[j], coarse_step, a_first, fmt, line, tw, to, lo, hi)
        if residual_norm2_within_tolerance(r2, _ROOT_TOL):
            on_b = within_boundary_tolerance(pa, pb, lo, hi, _BOUNDARY_TOL)
            jd = _jacobian_det(pa, pb, a_first, fmt, line, tw, to)
            found.append(Root(pa, pb, a_first, r2 ** 0.5, jd, on_b))

    roots, ambiguous = _canonical_roots(found)
    # Exhaustive per-assignment decision table (STAGE3-0006C-D-REV2 §16 seam; byte-identical).
    status = classify_per_solve(ambiguous, roots, _JAC_TOL)
    return ServerSolve(a_serves_first=a_first, status=status, roots=roots)


def _solve_one(a_first: bool, fmt: MatchFormat, line: Decimal, tw: float, to: float,
               domain: tuple[float, float]) -> ServerSolve:
    lo, hi = domain
    return _solve_one_on_axis(a_first, fmt, line, tw, to, domain,
                              build_scan_axis(lo, hi, _COARSE_N))


def _stability_checked_solve(a_first: bool, fmt: MatchFormat, line: Decimal, tw: float,
                             to: float, domain: tuple[float, float]) -> ServerSolve:
    """STAGE3-0006C-D-A3 §6/§9: run the identical production algorithm on every registered
    variant (G0 first, then the validation variants), compare BEFORE the first-server union.
    Stable -> the G0 solve is returned byte-identically with the agreement evidence attached.
    Unstable -> the assignment REFUSES with the existing public NON_IDENTIFIABLE and the
    INTERNAL reason DISCRETISATION_UNSTABLE_ROOT_SET; all snapshots are retained; there is no
    fallback to the G0-only result and no runtime switch. Variant results are never averaged,
    majority-voted or selected by residual; G1/G2 contribute no public root."""
    lo, hi = domain
    solves: list[ServerSolve] = []
    snapshots: list[VariantSolveSnapshot] = []
    for variant in REGISTERED_VARIANT_ORDER:
        axis = variant_axis(variant, lo, hi)
        solve = _solve_one_on_axis(a_first, fmt, line, tw, to, domain, axis)
        solves.append(solve)
        snapshots.append(VariantSolveSnapshot(
            variant=variant, a_serves_first=a_first, status=solve.status,
            roots=solve.roots, axis_digest=axis_digest(axis)))
    decision = compare_registered_variants(
        tuple(snapshots), domain=ParameterDomain.from_symmetric(lo, hi),
        tolerance=_DEDUP_TOL)
    g0 = solves[0]
    if decision.stable:
        return ServerSolve(a_serves_first=a_first, status=g0.status, roots=g0.roots,
                           stability=decision)
    return ServerSolve(a_serves_first=a_first, status=NON_IDENTIFIABLE, roots=(),
                       stability=decision)


def identify(target_match_win_a: float, target_over: float, line: Decimal, fmt: MatchFormat, *,
             domain: tuple[float, float]) -> IdentificationResult:
    """Dual-evaluate the bounded root solve for both first-server assignments (§14) and return
    the union structural result. No 50/50 prior; the solver never decides first-server
    materiality (founder-pending threshold)."""
    _validate_domain(domain)
    validate_targets(target_match_win_a, target_over)

    # STAGE3-0006C-D-A3: each assignment is solved through the registered-variant stability
    # check; an unstable assignment refuses BEFORE this union with the internal reason
    # DISCRETISATION_UNSTABLE_ROOT_SET (public status: the existing NON_IDENTIFIABLE).
    sa = _stability_checked_solve(True, fmt, line, target_match_win_a, target_over, domain)
    sb = _stability_checked_solve(False, fmt, line, target_match_win_a, target_over, domain)
    per = (sa, sb)

    # Exhaustive identify-level decision table (STAGE3-0006C-D-REV2 §16 seam; byte-identical):
    # degeneracy under either assignment dominates, then multiplicity, then the union path; the
    # union pool matches the frozen behaviour (all per-solve roots on the degenerate branch,
    # valid-solve roots otherwise); union ambiguity escalates to NON_IDENTIFIABLE; first-server
    # sensitivity is flagged, never judged (founder-pending threshold).
    if NON_IDENTIFIABLE in (sa.status, sb.status) or MULTIPLE_ROOTS in (sa.status, sb.status):
        pool = [r for s in per for r in s.roots]
    else:
        valid = [s for s in per if s.status in (IDENTIFIED, BOUNDARY_SOLUTION)]
        pool = [r for s in valid for r in s.roots]
    union, union_ambiguous = _canonical_roots(pool)
    overall = classify_overall(sa.status, sb.status, union, union_ambiguous)
    return IdentificationResult(status=overall, roots=union, per_server=per,
                                domain=domain, line=line, fmt=fmt)
