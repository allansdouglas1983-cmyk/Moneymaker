"""STAGE3-0006C-D-A1 §10 — INDEPENDENT test-only reference for canonical root deduplication.

Independence boundary: imports NOTHING from ``sport_tennis`` and nothing from the production
``root_dedup`` module (AST-enforced). Everything is literal brute force over duck-typed candidate
objects (attributes: p_a, p_b, a_serves_first, residual, jacobian_det, on_boundary): a pairwise
distance matrix, fixpoint closure over frozensets for components (no traversal-order dependence by
construction), literal max-pairwise diameter, and literal ordered keys transcribed directly from
the amendment (specs/programme/cross-market-coherence-root-dedup-amendment-v1.yaml §4).
"""
from __future__ import annotations

import hashlib
from typing import Any


def ref_distance(a: Any, b: Any) -> float:
    return float(max(abs(a.p_a - b.p_a), abs(a.p_b - b.p_b)))


def ref_fingerprint(c: Any) -> str:
    text = "|".join([
        float(c.p_a).hex(), float(c.p_b).hex(), str(int(bool(c.a_serves_first))),
        float(c.residual).hex(), float(c.jacobian_det).hex(), str(int(bool(c.on_boundary))),
    ])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ref_components(cands: list[Any], tol: float) -> list[list[Any]]:
    """Fixpoint closure over frozensets of indices: merge any two sets joined by an edge until no
    merge applies. Order-free by construction."""
    sets = [frozenset([i]) for i in range(len(cands))]
    changed = True
    while changed:
        changed = False
        for i in range(len(sets)):
            for j in range(i + 1, len(sets)):
                if any(ref_distance(cands[x], cands[y]) < tol
                       for x in sets[i] for y in sets[j]):
                    merged = sets[i] | sets[j]
                    sets = [s for k, s in enumerate(sets) if k not in (i, j)] + [merged]
                    changed = True
                    break
            if changed:
                break
    comps = [sorted((cands[i] for i in s), key=ref_fingerprint) for s in sets]
    return sorted(comps, key=lambda comp: ref_fingerprint(comp[0]))


def ref_diameter(comp: list[Any]) -> float:
    if len(comp) < 2:
        return 0.0
    return max(ref_distance(a, b) for i, a in enumerate(comp) for b in comp[i + 1:])


def ref_rep_key(c: Any) -> tuple[float, float, float, int, str]:
    return (c.residual, c.p_a, c.p_b, 0 if c.a_serves_first else 1, ref_fingerprint(c))


def ref_representative(comp: list[Any]) -> Any:
    return min(comp, key=ref_rep_key)


def ref_cluster_order_key(comp: list[Any]) -> tuple[float, float, float, str]:
    rep = ref_representative(comp)
    digest = hashlib.sha256(
        "|".join(sorted(ref_fingerprint(m) for m in comp)).encode("utf-8")).hexdigest()
    return (rep.p_a, rep.p_b, rep.residual, digest)


def ref_dedup(cands: list[Any], tol: float) -> dict[str, Any]:
    comps = ref_components(list(cands), tol)
    valid = [c for c in comps if ref_diameter(c) < tol]
    ambiguous = [c for c in comps if ref_diameter(c) >= tol]
    valid_sorted = sorted(valid, key=ref_cluster_order_key)
    return {
        "representatives": [ref_representative(c) for c in valid_sorted],
        "valid_components": valid_sorted,
        "ambiguous_components": ambiguous,
        "ambiguous": bool(ambiguous),
    }
