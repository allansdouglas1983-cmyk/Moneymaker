"""STAGE3-0006C-D-REV2 §5-§16 — root-set/diagnostic contracts (RED, tests-first).

Binds the Milestone-D semantic layer around the amended V2 solver: the governed RootCandidate
helpers (validation/serialization/digest over the existing Root — GOVERN_AS_IS), the bound
direct-nearness seam (delegating to the governing root_dedup rule, never a second policy), the
candidate/cluster/public-root distinction, the immutable RootSet, the bound canonical ordering,
mirror coordinate/relationship DIAGNOSTICS (never dedup, never selection, never status), the
extracted boundary-root seam, and the exhaustive public SolverStatus decision tables. Everything
is behaviour-preserving: V2 golden is load-bearing and untouched.
"""
from __future__ import annotations

import dataclasses
import math

import pytest

from sport_tennis.coherence.root_dedup import candidate_fingerprint, deduplicate_roots
from sport_tennis.coherence.rootset import (
    MirrorRelation,
    RootSet,
    build_root_set,
    candidate_digest,
    classify_mirror_relation,
    classify_overall,
    classify_per_solve,
    direct_root_nearness,
    mirror_coordinates,
    serialize_candidate,
    validate_candidate,
    within_boundary_tolerance,
)
from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver import Root
from sport_tennis.coherence.solver_contracts import ParameterDomain

TOL = 1e-3
_JAC_TOL = 5e-3
_NAN = float("nan")
_INF = float("inf")
_DOM = ParameterDomain.from_symmetric(0.35, 0.90)


def mk(pa: float, pb: float, *, res: float = 1e-5, a_first: bool = True,
       jd: float = 1.0, boundary: bool = False) -> Root:
    return Root(p_a=pa, p_b=pb, a_serves_first=a_first, residual=res, jacobian_det=jd,
                on_boundary=boundary)


# ------------------------------------------------------------------ §7 RootCandidate contract
def test_candidate_validation_refuses_nonfinite() -> None:
    validate_candidate(mk(0.5, 0.6))                      # finite: no raise
    for bad in (mk(_NAN, 0.5), mk(0.5, _INF), mk(0.5, 0.5, res=_NAN),
                mk(0.5, 0.5, jd=-_INF)):
        with pytest.raises(CoherenceMathError):
            validate_candidate(bad)


def test_candidate_is_frozen_and_value_equal() -> None:
    r = mk(0.5, 0.6)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.p_a = 0.0  # type: ignore[misc]
    assert mk(0.5, 0.6) == mk(0.5, 0.6)                   # distinct value-equal instances
    assert mk(0.5, 0.6) != mk(0.5, 0.6, a_first=False)    # first-server identity
    assert mk(0.5, 0.6) != mk(0.5, 0.6, boundary=True)    # boundary identity


def test_candidate_serialization_and_digest_bind_the_governing_fingerprint() -> None:
    r = mk(0.5, 0.6, res=2e-5, a_first=False, jd=1.5, boundary=True)
    s = serialize_candidate(r)
    assert list(s) == ["p_a", "p_b", "a_serves_first", "residual", "jacobian_det", "on_boundary"]
    assert s == {"p_a": 0.5, "p_b": 0.6, "a_serves_first": False, "residual": 2e-5,
                 "jacobian_det": 1.5, "on_boundary": True}
    assert candidate_digest(r) == candidate_fingerprint(r)   # BOUND, not a second digest policy
    assert candidate_digest(r) != candidate_digest(mk(0.5, 0.6))


# ------------------------------------------------------------------ §8 direct nearness (bound)
def test_direct_nearness_delegates_to_the_governing_rule() -> None:
    assert direct_root_nearness(mk(0.0, 0.0), mk(math.nextafter(TOL, 0.0), 0.0), TOL)
    assert not direct_root_nearness(mk(0.0, 0.0), mk(TOL, 0.0), TOL)          # exact: no edge
    assert not direct_root_nearness(mk(0.0, 0.0), mk(math.nextafter(TOL, 1.0), 0.0), TOL)
    r = mk(0.5, 0.6)
    assert direct_root_nearness(r, r, TOL)                                    # reflexive
    assert direct_root_nearness(mk(0.5, 0.6), mk(0.5, 0.6), TOL)              # value-equal
    a, b = mk(0.5, 0.6), mk(0.5004, 0.6)
    assert direct_root_nearness(a, b, TOL) == direct_root_nearness(b, a, TOL)  # symmetric
    # provenance never affects nearness
    assert direct_root_nearness(mk(0.5, 0.6, a_first=True, res=1.0),
                                mk(0.5, 0.6, a_first=False, res=1e-9), TOL)
    # mirror coordinates are just coordinates
    assert not direct_root_nearness(mk(0.6, 0.4), mk(0.4, 0.6), TOL)
    with pytest.raises(CoherenceMathError):
        direct_root_nearness(mk(_NAN, 0.5), mk(0.5, 0.5), TOL)


# ------------------------------------------------------------------ §12 mirror transformation
def test_mirror_coordinates_exact() -> None:
    assert mirror_coordinates(0.6, 0.42) == (1 - 0.6, 1 - 0.42)
    assert mirror_coordinates(0.5, 0.5) == (0.5, 0.5)                 # fixed point
    assert mirror_coordinates(0.35, 0.90) == (0.65, 0.09999999999999998)  # no clamping
    ma, mb = mirror_coordinates(*mirror_coordinates(0.61, 0.37))
    assert ma == pytest.approx(0.61, abs=1e-15) and mb == pytest.approx(0.37, abs=1e-15)
    with pytest.raises(CoherenceMathError):
        mirror_coordinates(_NAN, 0.5)
    with pytest.raises(CoherenceMathError):
        mirror_coordinates(0.5, _INF)


# ------------------------------------------------------------------ §13 mirror relationship
def test_mirror_relation_cases() -> None:
    dom = ParameterDomain.from_symmetric(0.35, 0.90)
    # no roots
    assert classify_mirror_relation((), dom, TOL) is MirrorRelation.NO_MIRROR_RELATION
    # 0.5 fixed point (exact and immediately-inside-tolerance)
    assert classify_mirror_relation((mk(0.5, 0.5),), dom, TOL) \
        is MirrorRelation.MIRROR_FIXED_POINT
    assert classify_mirror_relation((mk(0.5004, 0.4998),), dom, TOL) \
        is MirrorRelation.MIRROR_FIXED_POINT
    # admissible pair, both inside the domain
    assert classify_mirror_relation((mk(0.6, 0.42), mk(0.4, 0.58)), dom, TOL) \
        is MirrorRelation.ADMISSIBLE_MIRROR_PAIR
    # pair relation just outside the nearness tolerance -> unrelated
    assert classify_mirror_relation((mk(0.6, 0.42), mk(0.4 + 2e-3, 0.58)), dom, TOL) \
        is MirrorRelation.UNRELATED_MULTIPLE_ROOTS
    # single root whose mirror leaves the domain: mirror(0.8, 0.5) = (0.2, 0.5), 0.2 < 0.35
    assert classify_mirror_relation((mk(0.8, 0.5),), dom, TOL) \
        is MirrorRelation.MIRROR_OUTSIDE_DOMAIN
    # single root whose mirror lands EXACTLY on a domain bound: mirror(0.65, 0.5) = (0.35, 0.5)
    assert classify_mirror_relation((mk(0.65, 0.5),), dom, TOL) \
        is MirrorRelation.MIRROR_ON_DOMAIN_BOUNDARY
    # single root, mirror strictly inside, no second root -> no relation
    assert classify_mirror_relation((mk(0.6, 0.55),), dom, TOL) \
        is MirrorRelation.NO_MIRROR_RELATION
    # three roots containing one mirror pair -> pair dominates
    assert classify_mirror_relation((mk(0.6, 0.42), mk(0.4, 0.58), mk(0.7, 0.7)), dom, TOL) \
        is MirrorRelation.ADMISSIBLE_MIRROR_PAIR
    # first-server-separated equal-coordinate roots never fabricate a mirror relation
    assert classify_mirror_relation((mk(0.62, 0.61, a_first=True),
                                     mk(0.63, 0.60, a_first=False)), dom, TOL) \
        is MirrorRelation.UNRELATED_MULTIPLE_ROOTS


# ------------------------------------------------------------------ §14 boundary seam
def test_boundary_seam_matches_frozen_rule() -> None:
    lo, hi, bt = 0.35, 0.90, 5e-3
    assert within_boundary_tolerance(0.35, 0.6, lo, hi, bt)            # exact edge
    assert within_boundary_tolerance(0.6, 0.90, lo, hi, bt)
    assert within_boundary_tolerance(0.3549, 0.6, lo, hi, bt)          # just inside tol window
    assert not within_boundary_tolerance(0.355, 0.6, lo, hi, bt)       # exactly at tol: strict <
    assert not within_boundary_tolerance(0.6, 0.6, lo, hi, bt)         # interior
    assert within_boundary_tolerance(math.nextafter(0.355, 0.0), 0.6, lo, hi, bt)
    assert not within_boundary_tolerance(math.nextafter(0.355, 1.0), 0.6, lo, hi, bt)
    # either coordinate suffices; both-boundary also true
    assert within_boundary_tolerance(0.6, 0.351, lo, hi, bt)
    assert within_boundary_tolerance(0.351, 0.899, lo, hi, bt)


# ------------------------------------------------------------------ §16 status decision tables
def test_per_solve_decision_table_is_exhaustive() -> None:
    root_i = mk(0.6, 0.55, jd=1.0, boundary=False)
    root_b = mk(0.352, 0.6, jd=1.0, boundary=True)
    sing = mk(0.6, 0.55, jd=math.nextafter(_JAC_TOL, 0.0))
    nonsing = mk(0.6, 0.55, jd=_JAC_TOL)
    assert classify_per_solve(True, (), _JAC_TOL) == "NON_IDENTIFIABLE"
    assert classify_per_solve(True, (root_i,), _JAC_TOL) == "NON_IDENTIFIABLE"
    assert classify_per_solve(True, (root_i, root_b), _JAC_TOL) == "NON_IDENTIFIABLE"
    assert classify_per_solve(False, (), _JAC_TOL) == "NO_ROOT"
    assert classify_per_solve(False, (root_i, root_b), _JAC_TOL) == "MULTIPLE_ROOTS"
    assert classify_per_solve(False, (sing,), _JAC_TOL) == "NON_IDENTIFIABLE"   # |jac| just below
    assert classify_per_solve(False, (nonsing,), _JAC_TOL) == "IDENTIFIED"      # exact tol: not <
    assert classify_per_solve(False, (mk(0.6, 0.55, jd=-1e-4),), _JAC_TOL) \
        == "NON_IDENTIFIABLE"                                                    # abs()
    assert classify_per_solve(False, (root_b,), _JAC_TOL) == "BOUNDARY_SOLUTION"
    assert classify_per_solve(False, (root_i,), _JAC_TOL) == "IDENTIFIED"
    # singularity precedes boundary for the single root (frozen precedence)
    assert classify_per_solve(False, (mk(0.352, 0.6, jd=1e-4, boundary=True),), _JAC_TOL) \
        == "NON_IDENTIFIABLE"


def test_overall_decision_table_is_exhaustive() -> None:
    ri = mk(0.6, 0.55)
    rb = mk(0.352, 0.6, boundary=True)
    NI, MR, NR, ID, BS = ("NON_IDENTIFIABLE", "MULTIPLE_ROOTS", "NO_ROOT", "IDENTIFIED",
                          "BOUNDARY_SOLUTION")
    FS = "FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD"
    assert classify_overall(NI, ID, (ri,), False) == NI          # degeneracy dominates
    assert classify_overall(ID, NI, (), False) == NI
    assert classify_overall(NI, MR, (ri, rb), True) == NI
    assert classify_overall(MR, ID, (ri, rb), False) == MR       # multiplicity next
    assert classify_overall(ID, MR, (ri,), True) == NI           # union ambiguity overrides MR
    assert classify_overall(ID, ID, (ri,), True) == NI           # union ambiguity on valid branch
    assert classify_overall(NR, NR, (), False) == NR
    assert classify_overall(ID, NR, (ri,), False) == ID
    assert classify_overall(BS, NR, (rb,), False) == BS
    assert classify_overall(ID, ID, (ri, rb), False) == FS       # union multiplicity -> sensitive


# ------------------------------------------------------------------ §9/§10 RootSet contract
def test_root_set_valid_cluster_facts() -> None:
    cands = [mk(0.6, 0.42, res=3e-5, a_first=True), mk(0.6004, 0.4202, res=1e-5, a_first=False),
             mk(0.4, 0.58, res=2e-5)]
    rs = build_root_set(deduplicate_roots(cands, TOL), _DOM, TOL)
    assert isinstance(rs, RootSet)
    assert rs.root_count == 2 == len(rs.representatives)
    assert rs.representatives == tuple(c.representative for c in rs.clusters)
    assert not rs.ambiguous and rs.reason is None
    # canonical order inherited from the amendment (p_a ascending here)
    assert [r.p_a for r in rs.representatives] == [0.4, 0.6004]
    # first-server provenance summary retains BOTH assignments for the merged cluster
    assert rs.first_server_summary() == ((True,), (False, True))
    assert rs.boundary_summary() == (False, False)
    assert rs.mirror_relation() is MirrorRelation.ADMISSIBLE_MIRROR_PAIR
    with pytest.raises(dataclasses.FrozenInstanceError):
        rs.clusters = ()  # type: ignore[misc]


def test_root_set_ambiguous_chain_facts() -> None:
    chain = [mk(0.5, 0.5, res=3e-5), mk(0.5009, 0.5, res=1e-5), mk(0.5018, 0.5, res=2e-5)]
    rs = build_root_set(deduplicate_roots(chain, TOL), _DOM, TOL)
    assert rs.ambiguous and rs.reason is not None
    assert rs.root_count == 0 and rs.representatives == ()
    # an ambiguous result can never claim an identified root set
    assert classify_per_solve(rs.ambiguous, rs.representatives, _JAC_TOL) == "NON_IDENTIFIABLE"


def test_root_set_serialization_digest_and_permutation_invariance() -> None:
    cands = [mk(0.6, 0.42, res=3e-5), mk(0.4, 0.58, res=2e-5), mk(0.7, 0.7, res=1e-5)]
    a = build_root_set(deduplicate_roots(cands, TOL), _DOM, TOL)
    b = build_root_set(deduplicate_roots(list(reversed(cands)), TOL), _DOM, TOL)
    assert a.serialize() == b.serialize()
    assert a.digest() == b.digest()
    assert a.serialize()["root_count"] == 3
    assert a.serialize()["mirror_relation"] == "ADMISSIBLE_MIRROR_PAIR"
    empty = build_root_set(deduplicate_roots([], TOL), _DOM, TOL)
    assert empty.root_count == 0 and empty.serialize()["root_count"] == 0
    assert empty.digest() != a.digest()


def test_root_set_boundary_root_facts() -> None:
    rb = mk(0.352, 0.6, res=1e-5, boundary=True)
    rs = build_root_set(deduplicate_roots([rb], TOL), _DOM, TOL)
    assert rs.boundary_summary() == (True,)
    assert rs.root_count == 1
