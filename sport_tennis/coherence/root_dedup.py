"""CROSS_MARKET_COHERENCE_V1 — canonical set-defined root deduplication (STAGE3-0006C-D-A1).

Implements CANONICAL_COMPONENTS_WITH_DIAMETER_REFUSAL exactly as registered in
``specs/programme/cross-market-coherence-root-dedup-amendment-v1.yaml`` (founder amendment
responding to STOP_ROOT_DEDUP_CONTRACT_GAP). The previous greedy first-seen deduplication was
sequence-defined — the same candidate SET could yield a different root count and public status
under a different enumeration order. This module makes the root set a function of the candidate
SET alone:

* strict-Chebyshev near-equality edges at the RETAINED tolerance (edge iff distance < tol;
  distance == tol has NO edge); coordinates only — residual, first-server and provenance never
  define an edge;
* connected components over content-derived canonical fingerprints (invariant to input, scan,
  seed, first-server-evaluation and worker order);
* component diameter = max pairwise Chebyshev distance; a component is a valid duplicate-root
  cluster ONLY when diameter < tol; a component with diameter >= tol is a non-transitive
  tolerance chain — never merged, never split, REFUSED with the internal reason
  ``AMBIGUOUS_ROOT_TOLERANCE_CHAIN`` (the solver maps this to the existing public
  NON_IDENTIFIABLE);
* canonical representative of a valid cluster: minimum of (residual norm, p_a, p_b, A-first
  before B-first, fingerprint) — always an actual candidate, never a centroid or re-refinement;
* full member provenance retained per cluster in canonical fingerprint order;
* clusters ordered by (representative p_a, p_b, residual norm, cluster provenance digest).

SYNTHETIC-ONLY; no market prices, no outcomes; import-quarantined from execution/pricing/V0.
No outcome, tip or stake field exists anywhere in these contracts.
"""
from __future__ import annotations

import enum
import hashlib
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sport_tennis.coherence.scoring import CoherenceMathError

if TYPE_CHECKING:  # pragma: no cover - typing only; avoids a runtime cycle with solver
    from sport_tennis.coherence.solver import Root


class DedupReason(enum.Enum):
    """Structured INTERNAL refusal reason (never a public SolverStatus)."""

    AMBIGUOUS_ROOT_TOLERANCE_CHAIN = "AMBIGUOUS_ROOT_TOLERANCE_CHAIN"


def chebyshev_distance(left: Root, right: Root) -> float:
    """The retained coordinate metric: max(|p_a - p_a'|, |p_b - p_b'|). Coordinates ONLY."""
    return max(abs(left.p_a - right.p_a), abs(left.p_b - right.p_b))


def have_edge(left: Root, right: Root, tolerance: float) -> bool:
    """Direct near-equality edge iff distance < tolerance (STRICT; == tolerance has no edge)."""
    return chebyshev_distance(left, right) < tolerance


def candidate_fingerprint(candidate: Root) -> str:
    """Stable content-derived provenance ID: sha256 over the exact float.hex() of every numeric
    field plus the boolean flags. Identical fingerprints imply identical field values."""
    text = "|".join([
        float(candidate.p_a).hex(), float(candidate.p_b).hex(),
        str(int(bool(candidate.a_serves_first))),
        float(candidate.residual).hex(), float(candidate.jacobian_det).hex(),
        str(int(bool(candidate.on_boundary))),
    ])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_finite(candidates: list[Root]) -> None:
    for c in candidates:
        if not (math.isfinite(c.p_a) and math.isfinite(c.p_b) and math.isfinite(c.residual)
                and math.isfinite(c.jacobian_det)):
            raise CoherenceMathError("root candidates must be finite")


def connected_components(candidates: list[Root] | tuple[Root, ...],
                         tolerance: float) -> tuple[tuple[Root, ...], ...]:
    """Connected components of the strict-Chebyshev edge graph, canonically ordered. Membership,
    member order (fingerprint ascending) and component order (first-member fingerprint ascending)
    are all content-derived, so the partition is invariant to every enumeration order."""
    cands = list(candidates)
    order = sorted(range(len(cands)), key=lambda i: candidate_fingerprint(cands[i]))
    parent = list(range(len(cands)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for ai in range(len(order)):
        for bi in range(ai + 1, len(order)):
            i, j = order[ai], order[bi]
            if have_edge(cands[i], cands[j], tolerance):
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
    groups: dict[int, list[Root]] = {}
    for i in range(len(cands)):
        groups.setdefault(find(i), []).append(cands[i])
    comps = [tuple(sorted(g, key=candidate_fingerprint)) for g in groups.values()]
    return tuple(sorted(comps, key=lambda c: candidate_fingerprint(c[0])))


def component_diameter(component: tuple[Root, ...]) -> float:
    """Maximum pairwise Chebyshev distance over every member pair; 0.0 for a singleton."""
    if len(component) < 2:
        return 0.0
    return max(chebyshev_distance(a, b)
               for i, a in enumerate(component) for b in component[i + 1:])


def representative_key(candidate: Root) -> tuple[float, float, float, int, str]:
    """The governed ordered selection key: (residual norm, p_a, p_b, A-first-then-B,
    fingerprint) — discovery order is never a tie-break."""
    return (candidate.residual, candidate.p_a, candidate.p_b,
            0 if candidate.a_serves_first else 1, candidate_fingerprint(candidate))


def select_representative(component: tuple[Root, ...]) -> Root:
    """The unique canonical representative: the member minimising the governed key. Always an
    actual validated candidate — never recomputed, averaged or re-refined."""
    return min(component, key=representative_key)


@dataclass(frozen=True)
class RootCluster:
    """One valid duplicate-root cluster: canonical representative + full immutable member
    provenance in fingerprint order (both first-server assignments preserved when present)."""

    representative: Root
    members: tuple[Root, ...]
    diameter: float
    provenance_digest: str

    def serialize(self) -> dict[str, object]:
        rep = self.representative
        return {
            "representative": {
                "p_a": rep.p_a, "p_b": rep.p_b, "a_serves_first": rep.a_serves_first,
                "residual": rep.residual, "jacobian_det": rep.jacobian_det,
                "on_boundary": rep.on_boundary,
            },
            "member_fingerprints": [candidate_fingerprint(m) for m in self.members],
            "member_first_servers": [m.a_serves_first for m in self.members],
            "diameter": self.diameter,
            "provenance_digest": self.provenance_digest,
        }


def cluster_order_key(cluster: RootCluster) -> tuple[float, float, float, str]:
    """Canonical output ordering: (p_a, p_b, residual norm, cluster provenance digest)."""
    rep = cluster.representative
    return (rep.p_a, rep.p_b, rep.residual, cluster.provenance_digest)


@dataclass(frozen=True)
class RootDeduplicationResult:
    """The set-defined deduplication outcome: canonically ordered valid clusters, canonically
    ordered ambiguous (refused) components, and the structured internal reason."""

    clusters: tuple[RootCluster, ...]
    ambiguous_components: tuple[tuple[Root, ...], ...]
    reason: DedupReason | None

    @property
    def ambiguous(self) -> bool:
        return len(self.ambiguous_components) > 0

    def representatives(self) -> tuple[Root, ...]:
        return tuple(c.representative for c in self.clusters)

    def serialize(self) -> dict[str, object]:
        return {
            "clusters": [c.serialize() for c in self.clusters],
            "ambiguous_components": [[candidate_fingerprint(m) for m in comp]
                                     for comp in self.ambiguous_components],
            "ambiguous": self.ambiguous,
            "reason": self.reason.value if self.reason is not None else None,
        }

    def digest(self) -> str:
        import json

        return "sha256:" + hashlib.sha256(
            json.dumps(self.serialize(), sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest()


def _cluster_provenance_digest(component: tuple[Root, ...]) -> str:
    return hashlib.sha256(
        "|".join(sorted(candidate_fingerprint(m) for m in component)).encode("utf-8")).hexdigest()


def deduplicate_roots(candidates: list[Root] | tuple[Root, ...],
                      tolerance: float) -> RootDeduplicationResult:
    """The amendment's set-defined canonical deduplication. Refuses non-finite candidates; forms
    components; refuses any component whose diameter >= tolerance (non-transitive chain); selects
    canonical representatives for valid components; orders everything canonically."""
    cands = list(candidates)
    _validate_finite(cands)
    valid: list[RootCluster] = []
    ambiguous: list[tuple[Root, ...]] = []
    for component in connected_components(cands, tolerance):
        diameter = component_diameter(component)
        if diameter < tolerance:
            valid.append(RootCluster(
                representative=select_representative(component),
                members=component,
                diameter=diameter,
                provenance_digest=_cluster_provenance_digest(component),
            ))
        else:
            ambiguous.append(component)
    return RootDeduplicationResult(
        clusters=tuple(sorted(valid, key=cluster_order_key)),
        ambiguous_components=tuple(
            sorted(ambiguous, key=lambda c: candidate_fingerprint(c[0]))),
        reason=DedupReason.AMBIGUOUS_ROOT_TOLERANCE_CHAIN if ambiguous else None,
    )
