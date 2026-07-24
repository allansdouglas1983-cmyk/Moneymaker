"""STAGE3-0006C-D-A1 §6 — canonical set-defined root deduplication (RED, tests-first).

Binds the amended policy CANONICAL_COMPONENTS_WITH_DIAMETER_REFUSAL exactly as registered in
specs/programme/cross-market-coherence-root-dedup-amendment-v1.yaml: strict-Chebyshev edges at the
retained _DEDUP_TOL, order-invariant connected components, diameter refusal of non-transitive
chains (public NON_IDENTIFIABLE, internal AMBIGUOUS_ROOT_TOLERANCE_CHAIN), canonical
best-residual representatives, full member provenance, canonical output ordering, idempotence.
The three-candidate chain fixture is the load-bearing defect example from the Milestone-D stop:
the OLD greedy first-seen dedup returned order-dependent root sets for it (kept {A,C} or {B}
depending on permutation); the amended policy must refuse it identically for every permutation.
"""
from __future__ import annotations

import dataclasses
import itertools
import math

import pytest

from sport_tennis.coherence.root_dedup import (
    DedupReason,
    RootCluster,
    RootDeduplicationResult,
    candidate_fingerprint,
    chebyshev_distance,
    cluster_order_key,
    component_diameter,
    connected_components,
    deduplicate_roots,
    have_edge,
    representative_key,
    select_representative,
)
from sport_tennis.coherence.solver import Root

TOL = 1e-3


def mk(pa: float, pb: float, *, res: float = 1e-5, a_first: bool = True,
       jd: float = 1.0, boundary: bool = False) -> Root:
    return Root(p_a=pa, p_b=pb, a_serves_first=a_first, residual=res, jacobian_det=jd,
                on_boundary=boundary)


# the load-bearing chain: A~B, B~C, A!~C
A = mk(0.5, 0.5, res=3e-5)
B = mk(0.5009, 0.5, res=1e-5)
C = mk(0.5018, 0.5, res=2e-5)


# ------------------------------------------------------------------ distance + strict boundary
def test_chebyshev_distance_exact() -> None:
    assert chebyshev_distance(mk(0.5, 0.5), mk(0.5009, 0.5)) == pytest.approx(9e-4, abs=1e-12)
    assert chebyshev_distance(mk(0.5, 0.5), mk(0.5, 0.5018)) == pytest.approx(1.8e-3, abs=1e-12)
    # max of the two axes, not sum/min
    assert chebyshev_distance(mk(0.1, 0.2), mk(0.4, 0.25)) \
        == pytest.approx(0.3, abs=1e-12)


def test_edge_boundary_is_strict_less_than(  ) -> None:
    # exact-representable differences: 0.0 vs 1e-3 (float 1e-3 exactly)
    assert have_edge(mk(0.0, 0.0), mk(math.nextafter(TOL, 0.0), 0.0), TOL)   # just below -> edge
    assert not have_edge(mk(0.0, 0.0), mk(TOL, 0.0), TOL)                    # exact tol -> NO edge
    assert not have_edge(mk(0.0, 0.0), mk(math.nextafter(TOL, 1.0), 0.0), TOL)
    # residual / first-server / provenance never define the edge
    assert have_edge(mk(0.0, 0.0, res=1.0, a_first=True),
                     mk(1e-4, 0.0, res=1e-9, a_first=False), TOL)


# ------------------------------------------------------------------ §6.1 chain -> refusal, all 6 orders
@pytest.mark.parametrize("perm", list(itertools.permutations([A, B, C])))
def test_chain_refuses_identically_for_every_permutation(perm: tuple[Root, ...]) -> None:
    result = deduplicate_roots(list(perm), TOL)
    assert result.ambiguous
    assert result.reason is DedupReason.AMBIGUOUS_ROOT_TOLERANCE_CHAIN
    assert result.clusters == ()                       # the chain yields NO valid cluster
    assert len(result.ambiguous_components) == 1
    assert len(result.ambiguous_components[0]) == 3    # all three members retained, canonically
    assert result.representatives() == ()


def test_chain_serialization_identical_across_permutations() -> None:
    digests = {deduplicate_roots(list(p), TOL).digest()
               for p in itertools.permutations([A, B, C])}
    assert len(digests) == 1


# ------------------------------------------------------------------ §6.2 valid close cluster
_CLOSE = [mk(0.5, 0.5, res=3e-5), mk(0.5004, 0.5002, res=1e-5), mk(0.4998, 0.5004, res=2e-5)]


@pytest.mark.parametrize("perm", list(itertools.permutations(_CLOSE)))
def test_valid_close_cluster_all_permutations(perm: tuple[Root, ...]) -> None:
    result = deduplicate_roots(list(perm), TOL)
    assert not result.ambiguous and result.reason is None
    assert len(result.clusters) == 1
    cluster = result.clusters[0]
    assert cluster.representative == _CLOSE[1]         # lowest residual (1e-5) wins
    assert len(cluster.members) == 3                   # full provenance retained
    assert cluster.diameter < TOL
    assert result.digest() == deduplicate_roots(list(_CLOSE), TOL).digest()


# ------------------------------------------------------------------ §6.3 distinct roots
def test_distinct_roots_preserved_and_canonically_ordered() -> None:
    far = [mk(0.7, 0.3, res=5e-5), mk(0.4, 0.6, res=1e-5), mk(0.55, 0.45, res=9e-5)]
    for perm in itertools.permutations(far):
        result = deduplicate_roots(list(perm), TOL)
        assert not result.ambiguous
        assert len(result.clusters) == 3
        # canonical order: by representative p_a ascending (all distinct here)
        assert [c.representative.p_a for c in result.clusters] == [0.4, 0.55, 0.7]


# ------------------------------------------------------------------ §6.5 representative selection
def test_representative_lowest_residual_wins() -> None:
    lo, hi = mk(0.5002, 0.5, res=1e-6), mk(0.5, 0.5, res=1e-4)
    for order in ([lo, hi], [hi, lo]):
        r = deduplicate_roots(order, TOL)
        assert r.clusters[0].representative == lo


def test_representative_residual_tie_lower_p_a_then_p_b() -> None:
    x, y = mk(0.5, 0.5006, res=1e-5), mk(0.5004, 0.5, res=1e-5)
    for order in ([x, y], [y, x]):
        assert deduplicate_roots(order, TOL).clusters[0].representative == x   # lower p_a
    m, n = mk(0.5, 0.5004, res=1e-5), mk(0.5, 0.5, res=1e-5)
    for order in ([m, n], [n, m]):
        assert deduplicate_roots(order, TOL).clusters[0].representative == n   # lower p_b


def test_representative_full_tie_first_server_then_fingerprint() -> None:
    a_first = mk(0.5, 0.5, res=1e-5, a_first=True)
    b_first = mk(0.5, 0.5, res=1e-5, a_first=False)
    for order in ([a_first, b_first], [b_first, a_first]):
        assert deduplicate_roots(order, TOL).clusters[0].representative == a_first
    # everything tied except provenance (jacobian_det differs) -> ascending fingerprint wins
    p1 = mk(0.5, 0.5, res=1e-5, jd=1.0)
    p2 = mk(0.5, 0.5, res=1e-5, jd=2.0)
    expected = min([p1, p2], key=candidate_fingerprint)
    for order in ([p1, p2], [p2, p1]):
        assert deduplicate_roots(order, TOL).clusters[0].representative == expected


def test_representative_key_orientation() -> None:
    r = mk(0.4, 0.6, res=7e-5, a_first=False)
    key = representative_key(r)
    assert key[0] == 7e-5 and key[1] == 0.4 and key[2] == 0.6 and key[3] == 1
    assert representative_key(mk(0.4, 0.6, res=7e-5, a_first=True))[3] == 0


# ------------------------------------------------------------------ §6.6 first-server provenance
def test_first_server_cluster_retains_both_assignments() -> None:
    ra = mk(0.5, 0.5, res=2e-5, a_first=True)
    rb = mk(0.5002, 0.5001, res=1e-5, a_first=False)
    for order in ([ra, rb], [rb, ra]):
        result = deduplicate_roots(order, TOL)
        assert len(result.clusters) == 1
        assert {m.a_serves_first for m in result.clusters[0].members} == {True, False}
    assert deduplicate_roots([ra, rb], TOL).serialize() \
        == deduplicate_roots([rb, ra], TOL).serialize()


# ------------------------------------------------------------------ §6.7 mirror roots
def test_mirror_roots_beyond_tolerance_stay_distinct() -> None:
    root, mirror = mk(0.6, 0.42), mk(1 - 0.6, 1 - 0.42)
    result = deduplicate_roots([root, mirror], TOL)
    assert len(result.clusters) == 2                   # never collapsed, never preferred
    fixed = deduplicate_roots([mk(0.5, 0.5)], TOL)
    assert len(fixed.clusters) == 1                    # 0.5/0.5 fixed point: one coordinate root


# ------------------------------------------------------------------ §6.8 boundary roots
def test_boundary_metadata_preserved_from_actual_candidates() -> None:
    interior = mk(0.5, 0.5, res=1e-5, boundary=False)
    boundary = mk(0.5004, 0.5, res=2e-5, boundary=True)
    result = deduplicate_roots([boundary, interior], TOL)
    assert len(result.clusters) == 1
    rep = result.clusters[0].representative
    assert rep == interior and rep.on_boundary is False      # actual candidate identity
    assert {m.on_boundary for m in result.clusters[0].members} == {True, False}
    distinct = deduplicate_roots([mk(0.35, 0.5, boundary=True), mk(0.9, 0.5, boundary=True)], TOL)
    assert len(distinct.clusters) == 2


# ------------------------------------------------------------------ §6.9 idempotence
def test_idempotence_on_representatives() -> None:
    cands = _CLOSE + [mk(0.7, 0.3, res=4e-5), mk(0.42, 0.61, res=6e-5)]
    once = deduplicate_roots(cands, TOL)
    reps = list(once.representatives())
    twice = deduplicate_roots(reps, TOL)
    assert twice.representatives() == once.representatives()
    assert deduplicate_roots(list(twice.representatives()), TOL).digest() == twice.digest()


# ------------------------------------------------------------------ contracts + refusals
def test_contracts_are_frozen_and_finite_only() -> None:
    result = deduplicate_roots([A], TOL)
    cluster = result.clusters[0]
    assert isinstance(cluster, RootCluster) and isinstance(result, RootDeduplicationResult)
    with pytest.raises(dataclasses.FrozenInstanceError):
        cluster.diameter = 0.0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.reason = None  # type: ignore[misc]
    from sport_tennis.coherence.scoring import CoherenceMathError
    with pytest.raises(CoherenceMathError):
        deduplicate_roots([mk(float("nan"), 0.5)], TOL)
    with pytest.raises(CoherenceMathError):
        deduplicate_roots([mk(0.5, float("inf"))], TOL)


def test_component_and_diameter_seams() -> None:
    comps = connected_components([A, B, C, mk(0.9, 0.9)], TOL)
    sizes = sorted(len(c) for c in comps)
    assert sizes == [1, 3]
    chain = next(c for c in comps if len(c) == 3)
    assert component_diameter(chain) == pytest.approx(1.8e-3, abs=1e-12)
    assert component_diameter((A,)) == 0.0
    assert select_representative(tuple(_CLOSE)) == _CLOSE[1]
    k = cluster_order_key(deduplicate_roots([A], TOL).clusters[0])
    assert k[0] == A.p_a and k[1] == A.p_b


def test_empty_input_yields_empty_result() -> None:
    result = deduplicate_roots([], TOL)
    assert result.clusters == () and not result.ambiguous and result.reason is None


# ------------------------------------------------------------------ solver wiring (old defect)
def test_solver_chain_candidates_refuse_as_non_identifiable(
        monkeypatch: "pytest.MonkeyPatch") -> None:
    """The load-bearing defect at the WIRED solver level: three chained candidates must yield the
    public NON_IDENTIFIABLE refusal for the solve. The OLD greedy first-seen dedup instead kept an
    order-dependent subset ({A,C} -> MULTIPLE_ROOTS under this enumeration), so this test fails
    against the pre-amendment solver — the §6 'old implementation must fail' demonstration."""
    from decimal import Decimal

    from sport_tennis.coherence import solver as S
    from sport_tennis.coherence.formats import MatchFormat

    chain_points = iter([(0.5, 0.5, 0.0), (0.5009, 0.5, 0.0), (0.5018, 0.5, 0.0)])
    monkeypatch.setattr(S, "rank_seed_nodes", lambda grid, n, r: [(0, 0), (6, 6), (12, 12)])
    monkeypatch.setattr(S, "_refine", lambda *a, **k: next(chain_points))
    solve = S._solve_one(True, MatchFormat.BO3_AD_TB7_ALL_SETS, Decimal("22.5"),
                         0.6, 0.5, (0.35, 0.90))
    assert solve.status == S.NON_IDENTIFIABLE
    assert solve.roots == ()                       # the chain contributes no public root
