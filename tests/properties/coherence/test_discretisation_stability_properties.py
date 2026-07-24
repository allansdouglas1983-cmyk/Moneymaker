"""STAGE3-0006C-D-A3 §13/§14 — property tests for the discretisation-stability comparator.

Proves structural properties of the PRODUCTION ``compare_registered_variants`` (the §8 stability
contract in ``sport_tennis.coherence.discretisation_stability``) over generated registered-order
snapshot trios: determinism, root-order permutation invariance, agreement of identical trios,
unconditional snapshot retention, unstable-implies-structured-reason, isolated-displacement
refusal, and the set-defined symmetry of ``count_complete_matchings``.
"""
from __future__ import annotations

import random
from dataclasses import replace

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from sport_tennis.coherence.discretisation_stability import (
    StabilityReason,
    VariantSolveSnapshot,
    compare_registered_variants,
    count_complete_matchings,
)
from sport_tennis.coherence.scan_variants import (
    REGISTERED_VARIANT_ORDER,
    ScanVariant,
    axis_digest,
    variant_axis,
)
from sport_tennis.coherence.solver import Root
from sport_tennis.coherence.solver_contracts import ParameterDomain

_LO, _HI = 0.35, 0.90
_TOL = 1e-3
_DOMAIN = ParameterDomain.from_symmetric(_LO, _HI)
_AXIS_DIGEST = {v: axis_digest(tuple(variant_axis(v, _LO, _HI))) for v in ScanVariant}

_coord = st.floats(min_value=_LO, max_value=_HI, allow_nan=False,
                    allow_infinity=False).map(lambda x: round(x, 6))
_residual = st.floats(min_value=0.0, max_value=1e-4, allow_nan=False, allow_infinity=False)
_jacobian = st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False)


def _status_for_count(n: int) -> str:
    if n == 0:
        return "NO_ROOT"
    if n == 1:
        return "IDENTIFIED"
    return "MULTIPLE_ROOTS"


@st.composite
def _root(draw: st.DrawFn) -> Root:
    return Root(p_a=draw(_coord), p_b=draw(_coord), a_serves_first=draw(st.booleans()),
                residual=draw(_residual), jacobian_det=draw(_jacobian),
                on_boundary=draw(st.booleans()))


def _roots_of_size(n: int) -> st.SearchStrategy[tuple[Root, ...]]:
    return st.lists(_root(), min_size=n, max_size=n).map(tuple)


def _chebyshev(a: Root, b: Root) -> float:
    return max(abs(a.p_a - b.p_a), abs(a.p_b - b.p_b))


def _well_separated(roots: tuple[Root, ...], margin: float) -> bool:
    return all(_chebyshev(a, b) >= margin
               for i, a in enumerate(roots) for b in roots[i + 1:])


def _snap(variant: ScanVariant, status: str, roots: tuple[Root, ...],
          a_first: bool) -> VariantSolveSnapshot:
    return VariantSolveSnapshot(variant=variant, a_serves_first=a_first, status=status,
                                roots=roots, axis_digest=_AXIS_DIGEST[variant])


@st.composite
def general_trio(draw: st.DrawFn) -> tuple[VariantSolveSnapshot, ...]:
    """Any well-formed registered-order trio: each variant's root count (0-3) and roots are
    drawn independently, status derived from that variant's own root count. Counts commonly
    disagree across variants, so both stable and unstable outcomes occur."""
    a_first = draw(st.booleans())
    snaps = []
    for variant in REGISTERED_VARIANT_ORDER:
        n = draw(st.integers(min_value=0, max_value=3))
        roots = draw(_roots_of_size(n))
        snaps.append(_snap(variant, _status_for_count(n), roots, a_first))
    return tuple(snaps)


@st.composite
def stable_identical_trio(draw: st.DrawFn, *, min_size: int = 0,
                          max_size: int = 3) -> tuple[VariantSolveSnapshot, ...]:
    """A trio where all three variants carry THE SAME root tuple (identical, well-separated so
    the bipartite matching between any two variants is never ambiguous) and the same status /
    first-server assignment -- trivially agrees on every axis of the stability contract."""
    a_first = draw(st.booleans())
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    roots = draw(_roots_of_size(n))
    assume(_well_separated(roots, 2 * _TOL))
    status = _status_for_count(n)
    return tuple(_snap(v, status, roots, a_first) for v in REGISTERED_VARIANT_ORDER)


def _reflect_into_domain(x: float, shift: float) -> float:
    y = x + shift
    if y > _HI:
        y = x - shift
    if y < _LO:
        y = (_LO + _HI) / 2.0
    return round(min(max(y, _LO), _HI), 6)


# ---------------------------------------------------------------------------------- P1
@settings(max_examples=80, deadline=None)
@given(trio=general_trio())
def test_p1_determinism(trio: tuple[VariantSolveSnapshot, ...]) -> None:
    d1 = compare_registered_variants(trio, domain=_DOMAIN, tolerance=_TOL)
    d2 = compare_registered_variants(trio, domain=_DOMAIN, tolerance=_TOL)
    assert d1.serialize() == d2.serialize()
    assert d1.digest() == d2.digest()


# ---------------------------------------------------------------------------------- P2
@settings(max_examples=80, deadline=None)
@given(trio=general_trio(), shuffle_seed=st.randoms(use_true_random=False))
def test_p2_root_order_permutation_invariance(
        trio: tuple[VariantSolveSnapshot, ...], shuffle_seed: random.Random) -> None:
    permuted = tuple(
        replace(snap, roots=tuple(shuffle_seed.sample(snap.roots, len(snap.roots))))
        for snap in trio
    )
    d1 = compare_registered_variants(trio, domain=_DOMAIN, tolerance=_TOL)
    d2 = compare_registered_variants(permuted, domain=_DOMAIN, tolerance=_TOL)
    assert (d1.stable, d1.reason, d1.disagreements) == (d2.stable, d2.reason, d2.disagreements)


# ---------------------------------------------------------------------------------- P3
@settings(max_examples=60, deadline=None)
@given(trio=stable_identical_trio())
def test_p3_identical_trios_are_stable(trio: tuple[VariantSolveSnapshot, ...]) -> None:
    d = compare_registered_variants(trio, domain=_DOMAIN, tolerance=_TOL)
    assert d.stable is True
    assert d.reason is None
    assert d.disagreements == ()


# ---------------------------------------------------------------------------------- P4
@settings(max_examples=80, deadline=None)
@given(trio=general_trio())
def test_p4_snapshots_always_retained(trio: tuple[VariantSolveSnapshot, ...]) -> None:
    d = compare_registered_variants(trio, domain=_DOMAIN, tolerance=_TOL)
    assert d.snapshots == trio


# ---------------------------------------------------------------------------------- P5
@settings(max_examples=150, deadline=None)
@given(trio=general_trio())
def test_p5_unstable_implies_reason_and_disagreements(
        trio: tuple[VariantSolveSnapshot, ...]) -> None:
    d = compare_registered_variants(trio, domain=_DOMAIN, tolerance=_TOL)
    if not d.stable:
        assert d.reason is StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET
        assert d.disagreements != ()


# ---------------------------------------------------------------------------------- P6
@settings(max_examples=60, deadline=None)
@given(trio=stable_identical_trio(min_size=1, max_size=3),
       root_index=st.integers(min_value=0, max_value=2),
       move_g2=st.booleans(),
       shift=st.floats(min_value=0.05, max_value=0.3, allow_nan=False, allow_infinity=False))
def test_p6_isolated_displacement_refuses(
        trio: tuple[VariantSolveSnapshot, ...], root_index: int, move_g2: bool,
        shift: float) -> None:
    base = trio[0]
    n = len(base.roots)
    assume(root_index < n)
    original = base.roots[root_index]
    new_pa = _reflect_into_domain(original.p_a, shift)
    new_pb = _reflect_into_domain(original.p_b, shift)
    moved_root = replace(original, p_a=new_pa, p_b=new_pb)
    # guarantee the displaced root is unpairable with EVERY original root (Chebyshev >= 2*tol),
    # so the pair(s) touching the modified variant have zero complete matchings
    assume(all(_chebyshev(moved_root, r) >= 2 * _TOL for r in base.roots))

    target_variant = (ScanVariant.G2_REGISTERED_VALIDATION if move_g2
                      else ScanVariant.G1_REGISTERED_VALIDATION)
    new_snaps = []
    for snap in trio:
        if snap.variant is target_variant:
            new_roots = tuple(moved_root if i == root_index else r
                              for i, r in enumerate(snap.roots))
            new_snaps.append(replace(snap, roots=new_roots))
        else:
            new_snaps.append(snap)

    d = compare_registered_variants(tuple(new_snaps), domain=_DOMAIN, tolerance=_TOL)
    assert d.stable is False
    assert d.reason is StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET


# ---------------------------------------------------------------------------------- P7
@settings(max_examples=100, deadline=None)
@given(left=st.integers(min_value=0, max_value=3).flatmap(_roots_of_size),
       right=st.integers(min_value=0, max_value=3).flatmap(_roots_of_size))
def test_p7_count_complete_matchings_symmetry(
        left: tuple[Root, ...], right: tuple[Root, ...]) -> None:
    c1 = count_complete_matchings(left, right, _TOL)
    c2 = count_complete_matchings(right, left, _TOL)
    assert c1 == c2
    if len(left) != len(right):
        assert c1 == 0
    if not left and not right:
        assert c1 == 1
