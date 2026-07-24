"""CROSS_MARKET_COHERENCE_DISCRETISATION_STABILITY_AMENDMENT_V1 — stability contract.

STAGE3-0006C-D-A3 §7/§8. Immutable per-variant solve snapshots and the exact registered
agreement contract deciding whether the G0 public root set is discretisation-stable:

- status agreement (identical per-solve SolverStatus across G0/G1/G2);
- root-count agreement;
- location agreement: between EVERY pair of variants there exists EXACTLY ONE complete
  bipartite matching of representatives under the EXISTING strict Chebyshev < tolerance
  relation (``root_dedup.have_edge`` — coordinates only, set-defined, never greedy; zero
  complete matchings AND two-or-more distinct complete matchings are both disagreement);
- boundary agreement on the uniquely matched representatives;
- mirror agreement under the existing ``classify_mirror_relation`` decision table;
- all three variants refusing with NON_IDENTIFIABLE is agreement (stable refusal); a NO_ROOT
  mixture is status disagreement and therefore unstable;
- operational failures PROPAGATE (malformed comparator input raises) — they are never
  converted into, or hidden behind, the internal instability reason.

The internal reason DISCRETISATION_UNSTABLE_ROOT_SET mirrors the A1 AMBIGUOUS_ROOT_
TOLERANCE_CHAIN pattern: INTERNAL only, never a public SolverStatus.
"""
from __future__ import annotations

import enum
import hashlib
import itertools
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sport_tennis.coherence.root_dedup import candidate_fingerprint, have_edge
from sport_tennis.coherence.rootset import classify_mirror_relation
from sport_tennis.coherence.scan_variants import REGISTERED_VARIANT_ORDER, ScanVariant
from sport_tennis.coherence.solver_contracts import ParameterDomain, SolverStatus

if TYPE_CHECKING:  # pragma: no cover - typing only; avoids a runtime cycle with solver
    from sport_tennis.coherence.solver import Root


class StabilityReason(enum.Enum):
    """Structured INTERNAL refusal reason (never a public SolverStatus)."""

    DISCRETISATION_UNSTABLE_ROOT_SET = "DISCRETISATION_UNSTABLE_ROOT_SET"


@dataclass(frozen=True)
class VariantSolveSnapshot:
    """Immutable record of ONE variant's solve for ONE first-server assignment."""

    variant: ScanVariant
    a_serves_first: bool
    status: str
    roots: tuple[Root, ...]
    axis_digest: str

    def serialize(self) -> dict[str, object]:
        return {
            "variant": self.variant.value,
            "a_serves_first": self.a_serves_first,
            "status": self.status,
            "roots": [{
                "p_a": r.p_a, "p_b": r.p_b, "a_serves_first": r.a_serves_first,
                "residual": r.residual, "jacobian_det": r.jacobian_det,
                "on_boundary": r.on_boundary, "fingerprint": candidate_fingerprint(r),
            } for r in self.roots],
            "axis_digest": self.axis_digest,
        }

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.serialize(), sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StabilityDecision:
    """Outcome of the registered-variant comparison. Snapshots are ALWAYS retained."""

    stable: bool
    reason: StabilityReason | None
    disagreements: tuple[str, ...]
    snapshots: tuple[VariantSolveSnapshot, ...]

    def serialize(self) -> dict[str, object]:
        return {
            "stable": self.stable,
            "reason": self.reason.value if self.reason is not None else None,
            "disagreements": list(self.disagreements),
            "snapshots": [s.serialize() for s in self.snapshots],
        }

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.serialize(), sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest()


_MATCHING_ENUMERATION_CAP = 2  # only 0, 1 or ">= 2" is ever decision-relevant


def _complete_matchings(left: tuple[Root, ...], right: tuple[Root, ...], tolerance: float,
                        cap: int = _MATCHING_ENUMERATION_CAP) -> list[tuple[int, ...]]:
    """Enumerate complete bipartite matchings (as right-index assignments per left index)
    under the strict edge relation, stopping once ``cap + 1`` are found (the decision only
    distinguishes zero, exactly one, and more than one)."""
    if len(left) != len(right):
        return []
    n = len(left)
    adjacency = [[have_edge(lr, rr, tolerance) for rr in right] for lr in left]
    found: list[tuple[int, ...]] = []
    used = [False] * n
    assignment: list[int] = []

    def recurse(i: int) -> None:
        if len(found) > cap:
            return
        if i == n:
            found.append(tuple(assignment))
            return
        for j in range(n):
            if not used[j] and adjacency[i][j]:
                used[j] = True
                assignment.append(j)
                recurse(i + 1)
                assignment.pop()
                used[j] = False

    recurse(0)
    return found


def count_complete_matchings(left: tuple[Root, ...], right: tuple[Root, ...],
                             tolerance: float) -> int:
    """Number of complete bipartite matchings under the strict relation (exact for 0, 1, 2;
    values above the enumeration cap are reported as cap + 1 — equally 'ambiguous')."""
    return len(_complete_matchings(left, right, tolerance))


def compare_registered_variants(
        snapshots: tuple[VariantSolveSnapshot, ...], *, domain: ParameterDomain,
        tolerance: float) -> StabilityDecision:
    """The §8 stability contract over exactly the registered variant order. Malformed input
    (wrong count, wrong order, mixed first-server assignment) RAISES — an operational failure
    is never presented as discretisation instability."""
    if len(snapshots) != len(REGISTERED_VARIANT_ORDER):
        raise ValueError(
            f"expected {len(REGISTERED_VARIANT_ORDER)} registered variant snapshots, "
            f"got {len(snapshots)}")
    for snap, variant in zip(snapshots, REGISTERED_VARIANT_ORDER):
        if snap.variant is not variant:
            raise ValueError(
                f"snapshots must be in registered order {[v.value for v in REGISTERED_VARIANT_ORDER]}; "
                f"got {[s.variant.value for s in snapshots]}")
    if len({s.a_serves_first for s in snapshots}) != 1:
        raise ValueError("snapshots mix first-server assignments; compare one assignment only")

    base = snapshots[0]
    disagreements: list[str] = []

    for snap in snapshots[1:]:
        if snap.status != base.status:
            disagreements.append(
                f"STATUS_DISAGREEMENT[{base.variant.value}={base.status},"
                f"{snap.variant.value}={snap.status}]")
    if disagreements:
        return StabilityDecision(
            stable=False, reason=StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET,
            disagreements=tuple(disagreements), snapshots=snapshots)

    if all(s.status == SolverStatus.NON_IDENTIFIABLE.value for s in snapshots):
        # unanimous refusal is stable agreement: the same refusal is published from G0
        return StabilityDecision(stable=True, reason=None, disagreements=(),
                                 snapshots=snapshots)

    for left, right in itertools.combinations(snapshots, 2):
        if len(left.roots) != len(right.roots):
            disagreements.append(
                f"ROOT_COUNT_DISAGREEMENT[{left.variant.value}={len(left.roots)},"
                f"{right.variant.value}={len(right.roots)}]")
            continue
        matchings = _complete_matchings(left.roots, right.roots, tolerance)
        if not matchings:
            disagreements.append(
                f"LOCATION_MATCHING_ABSENT[{left.variant.value},{right.variant.value}]")
            continue
        if len(matchings) > 1:
            disagreements.append(
                f"LOCATION_MATCHING_AMBIGUOUS[{left.variant.value},{right.variant.value}]")
            continue
        for i, j in enumerate(matchings[0]):
            if left.roots[i].on_boundary != right.roots[j].on_boundary:
                disagreements.append(
                    f"BOUNDARY_FLAG_DISAGREEMENT[{left.variant.value},{right.variant.value}]")
                break

    base_mirror = classify_mirror_relation(base.roots, domain, tolerance)
    for snap in snapshots[1:]:
        mirror = classify_mirror_relation(snap.roots, domain, tolerance)
        if mirror is not base_mirror:
            disagreements.append(
                f"MIRROR_RELATION_DISAGREEMENT[{base.variant.value}={base_mirror.value},"
                f"{snap.variant.value}={mirror.value}]")

    if disagreements:
        return StabilityDecision(
            stable=False, reason=StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET,
            disagreements=tuple(disagreements), snapshots=snapshots)
    return StabilityDecision(stable=True, reason=None, disagreements=(), snapshots=snapshots)
