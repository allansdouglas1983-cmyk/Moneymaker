"""STAGE3-0006C-D-A3 §13/§14 — INDEPENDENT test-only reference for the discretisation-
stability contract (CROSS_MARKET_COHERENCE_DISCRETISATION_STABILITY_AMENDMENT_V1).

Independence boundary: imports NOTHING from ``sport_tennis`` and nothing from the production
``discretisation_stability`` / ``rootset`` / ``root_dedup`` modules (AST-enforced by
``test_stability_independent.py``). Everything below is literal, self-contained stdlib-only
Python operating on PLAIN DATA (dicts), transcribed directly from the registered amendment
(``specs/programme/cross-market-coherence-discretisation-stability-amendment-v1.yaml``) and
from ``sport_tennis/coherence/rootset.py``'s ``classify_mirror_relation`` decision table —
never by importing either.

Deliberately a DIFFERENT algorithm from production where the registration allows it: complete
bipartite matchings are enumerated by brute force over ALL permutations of the right-hand
indices (``itertools.permutations``), not production's pruned/capped depth-first search. The
two independent implementations are compared for AGREEMENT on the final ``stable`` boolean
only — this module makes no claim to reproduce production's disagreement-message strings or
internal control-flow ordering, only the registered agreement/disagreement CONTRACT.

Input shape (per variant snapshot, in registered order [G0_BASELINE, G1_REGISTERED_VALIDATION,
G2_REGISTERED_VALIDATION]):

    {"status": str, "roots": [{"p_a": float, "p_b": float, "on_boundary": bool}, ...]}

plus a symmetric domain ``(lo, hi)`` and a strict-relation ``tolerance``. Returns
``{"stable": bool}``.
"""
from __future__ import annotations

import itertools
import math
import typing

_RootDict = dict[str, object]
_SnapshotDict = dict[str, object]


def mirror_coordinates(p_a: float, p_b: float) -> tuple[float, float]:
    """The pure mirror diagnostic (1 - p_a, 1 - p_b), transcribed from
    ``rootset.mirror_coordinates``. Finite inputs only."""
    if not (math.isfinite(p_a) and math.isfinite(p_b)):
        raise ValueError("mirror coordinates require finite inputs")
    return 1.0 - p_a, 1.0 - p_b


def _near(pa1: float, pb1: float, pa2: float, pb2: float, tolerance: float) -> bool:
    """Strict-Chebyshev near-equality on coordinates only: edge iff distance < tolerance
    (STRICT; distance == tolerance has NO edge). Transcribed from ``root_dedup.have_edge``."""
    return max(abs(pa1 - pa2), abs(pb1 - pb2)) < tolerance


def _root_coords(root: _RootDict) -> tuple[float, float]:
    return float(root["p_a"]), float(root["p_b"])  # type: ignore[arg-type]


def classify_mirror_relation(roots: list[_RootDict], lo: float, hi: float,
                              tolerance: float) -> str:
    """Literal re-implementation of ``rootset.classify_mirror_relation``'s FIXED precedence:

    1. ADMISSIBLE_MIRROR_PAIR -- some pair (i != j) with mirror(r_i) directly near r_j;
    2. MIRROR_FIXED_POINT -- some representative directly near its own mirror;
    3. single representative: mirror outside the domain -> MIRROR_OUTSIDE_DOMAIN; mirror
       exactly on a domain bound -> MIRROR_ON_DOMAIN_BOUNDARY; else NO_MIRROR_RELATION;
    4. multiple representatives with no mirror relation -> UNRELATED_MULTIPLE_ROOTS;
    5. no representatives -> NO_MIRROR_RELATION.

    ``(lo, hi)`` is the symmetric domain bound applied identically to both coordinate axes
    (mirrors ``ParameterDomain.from_symmetric``)."""
    if not roots:
        return "NO_MIRROR_RELATION"
    n = len(roots)
    for i in range(n):
        ma, mb = mirror_coordinates(*_root_coords(roots[i]))
        for j in range(n):
            if i == j:
                continue
            rpa, rpb = _root_coords(roots[j])
            if _near(ma, mb, rpa, rpb, tolerance):
                return "ADMISSIBLE_MIRROR_PAIR"
    for rep in roots:
        pa, pb = _root_coords(rep)
        ma, mb = mirror_coordinates(pa, pb)
        if _near(ma, mb, pa, pb, tolerance):
            return "MIRROR_FIXED_POINT"
    if n == 1:
        pa, pb = _root_coords(roots[0])
        ma, mb = mirror_coordinates(pa, pb)
        if not (lo <= ma <= hi and lo <= mb <= hi):
            return "MIRROR_OUTSIDE_DOMAIN"
        if ma in (lo, hi) or mb in (lo, hi):
            return "MIRROR_ON_DOMAIN_BOUNDARY"
        return "NO_MIRROR_RELATION"
    return "UNRELATED_MULTIPLE_ROOTS"


def _complete_matchings(left: list[_RootDict], right: list[_RootDict],
                         tolerance: float) -> list[tuple[int, ...]]:
    """Complete bipartite matchings of ``left`` onto ``right`` under the strict near-equality
    relation, enumerated by BRUTE FORCE over every permutation of the right-hand indices
    (``itertools.permutations``) -- deliberately a different algorithm from production's
    pruned depth-first search. A mismatched length yields no matchings; two empty sequences
    match uniquely (the vacuous empty matching)."""
    n = len(left)
    if n != len(right):
        return []
    if n == 0:
        return [()]
    matchings: list[tuple[int, ...]] = []
    for perm in itertools.permutations(range(n)):
        ok = True
        for i in range(n):
            lpa, lpb = _root_coords(left[i])
            rpa, rpb = _root_coords(right[perm[i]])
            if not _near(lpa, lpb, rpa, rpb, tolerance):
                ok = False
                break
        if ok:
            matchings.append(perm)
    return matchings


def compare_stability(snapshots: list[_SnapshotDict], *, domain: tuple[float, float],
                       tolerance: float) -> dict[str, bool]:
    """The §8 stability contract, transcribed literally from the registered amendment, over
    plain-data snapshots in registered order [G0, G1, G2]:

    - status agreement (identical status string across all three); all three
      "NON_IDENTIFIABLE" is agreement (stable refusal) and short-circuits the remaining checks;
    - root-count agreement (identical root-list length across all three);
    - location agreement: for EVERY pair, exactly one complete bipartite matching under the
      strict near-equality relation (zero or two-or-more is disagreement);
    - boundary agreement on the uniquely matched representatives of every pair;
    - mirror agreement: identical ``classify_mirror_relation`` label across all three variants'
      own root lists (computed independently per variant, never by pairing).

    Returns ``{"stable": bool}`` only -- this reference makes no claim about matching
    production's disagreement-message strings."""
    if len(snapshots) != 3:
        raise ValueError(f"expected exactly 3 snapshots in registered order, got {len(snapshots)}")
    lo, hi = domain

    statuses = [str(s["status"]) for s in snapshots]
    if len(set(statuses)) != 1:
        return {"stable": False}
    if statuses[0] == "NON_IDENTIFIABLE":
        return {"stable": True}

    roots_by_snapshot: list[list[_RootDict]] = [
        typing.cast("list[_RootDict]", s["roots"]) for s in snapshots
    ]
    counts = [len(r) for r in roots_by_snapshot]
    if len(set(counts)) != 1:
        return {"stable": False}

    for i, j in itertools.combinations(range(3), 2):
        left, right = roots_by_snapshot[i], roots_by_snapshot[j]
        matchings = _complete_matchings(left, right, tolerance)
        if len(matchings) != 1:
            return {"stable": False}
        matching = matchings[0]
        for a_idx, b_idx in enumerate(matching):
            if bool(left[a_idx]["on_boundary"]) != bool(right[b_idx]["on_boundary"]):
                return {"stable": False}

    mirrors = [classify_mirror_relation(roots, lo, hi, tolerance) for roots in roots_by_snapshot]
    if len(set(mirrors)) != 1:
        return {"stable": False}

    return {"stable": True}
