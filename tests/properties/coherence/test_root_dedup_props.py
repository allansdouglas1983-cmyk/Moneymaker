"""STAGE3-0006C-D-A1 §9 — property tests for canonical set-defined root deduplication (RED).

Proves the amendment's structural properties over generated candidate sets: permutation
invariance, idempotence, deterministic serialization/digest, no input mutation, order-independent
partition, diameter-valid clusters, ambiguous-chain refusal, representative membership and
minimality, complete provenance union, disjoint components, total deterministic output order.
The raw pairwise < tol relationship is deliberately NOT asserted transitive — non-transitive
connected chains must be detected and refused instead.
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from sport_tennis.coherence.root_dedup import (
    candidate_fingerprint,
    chebyshev_distance,
    component_diameter,
    deduplicate_roots,
)
from sport_tennis.coherence.solver import Root

TOL = 1e-3

_coord = st.sampled_from([0.45, 0.5, 0.62, 0.7])
_jitter = st.floats(min_value=-1.2e-3, max_value=1.2e-3, allow_nan=False, allow_infinity=False)


@st.composite
def roots(draw: st.DrawFn) -> Root:
    return Root(
        p_a=draw(_coord) + draw(_jitter),
        p_b=draw(_coord) + draw(_jitter),
        a_serves_first=draw(st.booleans()),
        residual=draw(st.floats(min_value=0.0, max_value=1e-4,
                                allow_nan=False, allow_infinity=False)),
        jacobian_det=draw(st.floats(min_value=-3.0, max_value=3.0,
                                    allow_nan=False, allow_infinity=False)),
        on_boundary=draw(st.booleans()),
    )


_cand_lists = st.lists(roots(), min_size=0, max_size=7)


@settings(max_examples=120, deadline=None)
@given(cands=_cand_lists, seed=st.randoms(use_true_random=False))
def test_permutation_invariance_and_determinism(cands: list[Root], seed) -> None:  # noqa: ANN001
    base = deduplicate_roots(list(cands), TOL)
    shuffled = list(cands)
    seed.shuffle(shuffled)
    perm = deduplicate_roots(shuffled, TOL)
    assert perm.representatives() == base.representatives()
    assert perm.serialize() == base.serialize()
    assert perm.digest() == base.digest()
    assert perm.ambiguous == base.ambiguous


@settings(max_examples=120, deadline=None)
@given(cands=_cand_lists)
def test_partition_validity_provenance_and_representatives(cands: list[Root]) -> None:
    original = list(cands)
    result = deduplicate_roots(cands, TOL)
    assert cands == original                                        # no input mutation
    all_components = [list(c.members) for c in result.clusters] \
        + [list(c) for c in result.ambiguous_components]
    # complete provenance union: every candidate appears exactly once across components
    flat = [candidate_fingerprint(m) for comp in all_components for m in comp]
    assert sorted(flat) == sorted(candidate_fingerprint(c) for c in cands)
    for cluster in result.clusters:
        assert component_diameter(cluster.members) < TOL            # valid => diameter < tol
        assert cluster.representative in cluster.members            # an actual input candidate
        # representative minimality: no member has a strictly smaller canonical key
        rep_key = (cluster.representative.residual, cluster.representative.p_a,
                   cluster.representative.p_b,
                   0 if cluster.representative.a_serves_first else 1,
                   candidate_fingerprint(cluster.representative))
        for m in cluster.members:
            assert rep_key <= (m.residual, m.p_a, m.p_b,
                               0 if m.a_serves_first else 1, candidate_fingerprint(m))
    for comp in result.ambiguous_components:
        assert component_diameter(comp) >= TOL                      # refused => chain diameter
    if result.ambiguous_components:
        assert result.ambiguous and result.reason is not None
    else:
        assert not result.ambiguous and result.reason is None


@settings(max_examples=100, deadline=None)
@given(cands=_cand_lists)
def test_idempotence_and_total_output_order(cands: list[Root]) -> None:
    once = deduplicate_roots(list(cands), TOL)
    reps = list(once.representatives())
    twice = deduplicate_roots(reps, TOL)
    assert twice.representatives() == once.representatives()
    keys = [(c.representative.p_a, c.representative.p_b, c.representative.residual,
             c.provenance_digest) for c in once.clusters]
    assert keys == sorted(keys)                                     # total deterministic order
    # neighbours in the canonical order are strictly distinguishable (total order)
    for left, right in zip(keys, keys[1:]):
        assert left < right


@settings(max_examples=80, deadline=None)
@given(a=roots(), b=roots())
def test_edge_symmetry_matches_distance(a: Root, b: Root) -> None:
    assert chebyshev_distance(a, b) == chebyshev_distance(b, a)
