"""CROSS_MARKET_COHERENCE_V1 — root-set and diagnostic contracts (STAGE3-0006C-D-REV2).

Milestone D semantic layer around the amended V2 solver vintage. Everything here BINDS the
governing registrations — it never reimplements them:

* RootCandidate = the existing ``Root`` (GOVERN_AS_IS); this module adds the governed validation,
  deterministic serialization, and a digest BOUND to ``root_dedup.candidate_fingerprint``;
* direct root-nearness delegates to ``root_dedup.have_edge`` (the strict-Chebyshev governing rule;
  deliberately NOT called an equivalence relation — the non-transitive chain is handled by the
  governing component-diameter refusal);
* ``RootSet`` wraps the amendment's ``RootDeduplicationResult`` (clusters/representatives/
  ambiguity) with domain-aware diagnostic summaries — it never re-clusters;
* mirror coordinates / MirrorRelation are DIAGNOSTICS ONLY: they never deduplicate, never choose
  a representative, never alter component membership, order or SolverStatus, and stay out of the
  public result schema;
* ``within_boundary_tolerance`` extracts the solver's frozen boundary rule byte-identically;
* ``classify_per_solve`` / ``classify_overall`` extract the exhaustive public SolverStatus
  decision tables byte-identically (no fall-through default; registered-but-non-emitted statuses
  stay non-emitted).

SYNTHETIC-ONLY; no market prices, no outcomes; import-quarantined from execution/pricing/V0.
No outcome, profit, EV, tip or stake field exists anywhere in these contracts.
"""
from __future__ import annotations

import enum
import hashlib
import json
import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from sport_tennis.coherence.root_dedup import (
    DedupReason,
    RootCluster,
    RootDeduplicationResult,
    candidate_fingerprint,
    have_edge,
)
from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver_contracts import ParameterDomain, SolverStatus

if TYPE_CHECKING:  # pragma: no cover - typing only; avoids a runtime cycle with solver
    from sport_tennis.coherence.solver import Root

_NON_IDENTIFIABLE = SolverStatus.NON_IDENTIFIABLE.value
_NO_ROOT = SolverStatus.NO_ROOT.value
_MULTIPLE_ROOTS = SolverStatus.MULTIPLE_ROOTS.value
_IDENTIFIED = SolverStatus.IDENTIFIED.value
_BOUNDARY_SOLUTION = SolverStatus.BOUNDARY_SOLUTION.value
_FIRST_SERVER_SENSITIVE = SolverStatus.FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD.value


# --------------------------------------------------------------- §7 RootCandidate (Root) helpers
def validate_candidate(candidate: Root) -> None:
    """Governed finite-only validation of a root candidate (the frozen Root)."""
    if not (math.isfinite(candidate.p_a) and math.isfinite(candidate.p_b)
            and math.isfinite(candidate.residual) and math.isfinite(candidate.jacobian_det)):
        raise CoherenceMathError("root candidate fields must be finite")


def serialize_candidate(candidate: Root) -> dict[str, object]:
    """Deterministic candidate serialization in canonical field order."""
    return {"p_a": candidate.p_a, "p_b": candidate.p_b,
            "a_serves_first": candidate.a_serves_first, "residual": candidate.residual,
            "jacobian_det": candidate.jacobian_det, "on_boundary": candidate.on_boundary}


def candidate_digest(candidate: Root) -> str:
    """The candidate digest IS the governing fingerprint (bound, never a second policy)."""
    return candidate_fingerprint(candidate)


# --------------------------------------------------------------- §8 direct nearness (bound)
def direct_root_nearness(left: Root, right: Root, tolerance: float) -> bool:
    """Direct near-equality, delegating to the governing amended rule (strict Chebyshev
    ``< tolerance``; coordinates only). Reflexive and symmetric on valid candidates; deliberately
    NOT transitive and never claimed to be — chains are refused by the governing
    component-diameter rule, not here. Non-finite candidates are refused."""
    validate_candidate(left)
    validate_candidate(right)
    return have_edge(left, right, tolerance)


# --------------------------------------------------------------- §12 mirror transformation
def mirror_coordinates(p_a: float, p_b: float) -> tuple[float, float]:
    """The pure mirror diagnostic (1 - p_a, 1 - p_b). No clamping, no selection, no dedup, no
    status effect. Finite inputs only."""
    if not (math.isfinite(p_a) and math.isfinite(p_b)):
        raise CoherenceMathError("mirror coordinates require finite inputs")
    return 1.0 - p_a, 1.0 - p_b


# --------------------------------------------------------------- §13 mirror relationship
class MirrorRelation(enum.Enum):
    """Closed mirror DIAGNOSTIC vocabulary. Internal only — never public serialization."""

    NO_MIRROR_RELATION = "NO_MIRROR_RELATION"
    MIRROR_FIXED_POINT = "MIRROR_FIXED_POINT"
    ADMISSIBLE_MIRROR_PAIR = "ADMISSIBLE_MIRROR_PAIR"
    MIRROR_OUTSIDE_DOMAIN = "MIRROR_OUTSIDE_DOMAIN"
    MIRROR_ON_DOMAIN_BOUNDARY = "MIRROR_ON_DOMAIN_BOUNDARY"
    UNRELATED_MULTIPLE_ROOTS = "UNRELATED_MULTIPLE_ROOTS"


def _mirrored(candidate: Root) -> Root:
    ma, mb = mirror_coordinates(candidate.p_a, candidate.p_b)
    return replace(candidate, p_a=ma, p_b=mb)


def classify_mirror_relation(representatives: tuple[Root, ...], domain: ParameterDomain,
                             tolerance: float) -> MirrorRelation:
    """Diagnostic classification with FIXED precedence (recorded here, pinned by tests):
    1. ADMISSIBLE_MIRROR_PAIR — some pair (i != j) with mirror(r_i) directly near r_j;
    2. MIRROR_FIXED_POINT — some representative directly near its own mirror;
    3. single representative: mirror outside the domain -> MIRROR_OUTSIDE_DOMAIN; mirror exactly
       on a domain bound -> MIRROR_ON_DOMAIN_BOUNDARY; else NO_MIRROR_RELATION;
    4. multiple representatives with no mirror relation -> UNRELATED_MULTIPLE_ROOTS;
    5. no representatives -> NO_MIRROR_RELATION.
    Consumes only the amended representatives, the Milestone-A ParameterDomain and the bound
    nearness seam. Never alters roots, order or status."""
    if not representatives:
        return MirrorRelation.NO_MIRROR_RELATION
    for i, left in enumerate(representatives):
        m = _mirrored(left)
        for j, right in enumerate(representatives):
            if i != j and direct_root_nearness(m, right, tolerance):
                return MirrorRelation.ADMISSIBLE_MIRROR_PAIR
    for rep in representatives:
        if direct_root_nearness(_mirrored(rep), rep, tolerance):
            return MirrorRelation.MIRROR_FIXED_POINT
    if len(representatives) == 1:
        ma, mb = mirror_coordinates(representatives[0].p_a, representatives[0].p_b)
        if not domain.contains(ma, mb):
            return MirrorRelation.MIRROR_OUTSIDE_DOMAIN
        if ma in (domain.lower_a, domain.upper_a) or mb in (domain.lower_b, domain.upper_b):
            return MirrorRelation.MIRROR_ON_DOMAIN_BOUNDARY
        return MirrorRelation.NO_MIRROR_RELATION
    return MirrorRelation.UNRELATED_MULTIPLE_ROOTS


# --------------------------------------------------------------- §14 boundary seam (frozen rule)
def within_boundary_tolerance(p_a: float, p_b: float, lo: float, hi: float,
                              tolerance: float) -> bool:
    """The solver's frozen boundary-root rule, byte-identical: the minimum distance from either
    coordinate to either domain edge is strictly below the tolerance (one coordinate suffices)."""
    return min(p_a - lo, hi - p_a, p_b - lo, hi - p_b) < tolerance


# --------------------------------------------------------------- §16 status decision tables
def classify_per_solve(ambiguous: bool, roots: tuple[Root, ...], jac_tol: float) -> str:
    """The exhaustive per-assignment mapping, byte-identical to the amended V2 solver:
    ambiguity -> NON_IDENTIFIABLE; zero roots -> NO_ROOT; multiple -> MULTIPLE_ROOTS; one ->
    NON_IDENTIFIABLE when |jacobian_det| < jac_tol (strict), else BOUNDARY_SOLUTION when
    on_boundary, else IDENTIFIED. No fall-through default beyond this closed table."""
    if ambiguous:
        return _NON_IDENTIFIABLE
    if not roots:
        return _NO_ROOT
    if len(roots) > 1:
        return _MULTIPLE_ROOTS
    r = roots[0]
    if abs(r.jacobian_det) < jac_tol:
        return _NON_IDENTIFIABLE
    if r.on_boundary:
        return _BOUNDARY_SOLUTION
    return _IDENTIFIED


def classify_overall(sa_status: str, sb_status: str, union_roots: tuple[Root, ...],
                     union_ambiguous: bool) -> str:
    """The exhaustive identify-level mapping, byte-identical to the amended V2 solver:
    NON_IDENTIFIABLE under either assignment dominates; then MULTIPLE_ROOTS (escalated to
    NON_IDENTIFIABLE by union ambiguity); then the union path: ambiguity -> NON_IDENTIFIABLE,
    empty -> NO_ROOT, single -> BOUNDARY_SOLUTION/IDENTIFIED, several ->
    FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD (the pending materiality threshold is never
    decided here)."""
    if _NON_IDENTIFIABLE in (sa_status, sb_status):
        return _NON_IDENTIFIABLE
    if _MULTIPLE_ROOTS in (sa_status, sb_status):
        return _NON_IDENTIFIABLE if union_ambiguous else _MULTIPLE_ROOTS
    if union_ambiguous:
        return _NON_IDENTIFIABLE
    if not union_roots:
        return _NO_ROOT
    if len(union_roots) == 1:
        return _BOUNDARY_SOLUTION if union_roots[0].on_boundary else _IDENTIFIED
    return _FIRST_SERVER_SENSITIVE


# --------------------------------------------------------------- §9/§10 RootSet contract
@dataclass(frozen=True)
class RootSet:
    """Immutable amended-canonical root evidence: the candidate/cluster/public-root distinction
    made explicit. Clusters and ambiguity come verbatim from the governing deduplication;
    diagnostics are derived, never re-clustered. Internal evidence object — the public
    IdentificationResult schema is unchanged in this milestone."""

    clusters: tuple[RootCluster, ...]
    ambiguous_components: tuple[tuple[Root, ...], ...]
    reason: DedupReason | None
    domain: ParameterDomain
    nearness_tolerance: float

    @property
    def representatives(self) -> tuple[Root, ...]:
        return tuple(c.representative for c in self.clusters)

    @property
    def root_count(self) -> int:
        return len(self.clusters)

    @property
    def ambiguous(self) -> bool:
        return len(self.ambiguous_components) > 0

    def boundary_summary(self) -> tuple[bool, ...]:
        return tuple(c.representative.on_boundary for c in self.clusters)

    def first_server_summary(self) -> tuple[tuple[bool, ...], ...]:
        """Per-cluster sorted unique member first-server assignments — both retained when a
        cluster merged candidates from both solves."""
        return tuple(tuple(sorted({m.a_serves_first for m in c.members})) for c in self.clusters)

    def mirror_relation(self) -> MirrorRelation:
        return classify_mirror_relation(self.representatives, self.domain,
                                        self.nearness_tolerance)

    def serialize(self) -> dict[str, object]:
        return {
            "clusters": [c.serialize() for c in self.clusters],
            "ambiguous_components": [[candidate_fingerprint(m) for m in comp]
                                     for comp in self.ambiguous_components],
            "reason": self.reason.value if self.reason is not None else None,
            "domain": self.domain.serialize(),
            "root_count": self.root_count,
            "boundary_flags": list(self.boundary_summary()),
            "first_server_assignments": [list(x) for x in self.first_server_summary()],
            "mirror_relation": self.mirror_relation().value,
        }

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            json.dumps(self.serialize(), sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest()


def build_root_set(result: RootDeduplicationResult, domain: ParameterDomain,
                   nearness_tolerance: float) -> RootSet:
    """Wrap the governing deduplication result verbatim — clusters, ambiguity and order are
    inherited, never recomputed."""
    return RootSet(clusters=result.clusters, ambiguous_components=result.ambiguous_components,
                   reason=result.reason, domain=domain, nearness_tolerance=nearness_tolerance)
