"""STAGE3-0006C-D-A3 §10 — RED tests for the discretisation-stability amendment.

Pins CROSS_MARKET_COHERENCE_DISCRETISATION_STABILITY_AMENDMENT_V1 (append-only registration in
specs/programme/): the frozen scan-variant vocabulary (G0 baseline + registered validation
variants G1/G2, exact A2 lattice rules, artifact-digest pinned, no G3 at runtime), the immutable
VariantSolveSnapshot, the exact stability contract (status / root-count / unique-complete-
matching / boundary / mirror agreement; all-NON_IDENTIFIABLE stable; NO_ROOT mixtures unstable;
operational failures propagate), and the final policy (stable -> G0 byte-identical with retained
agreement evidence; unstable -> existing public NON_IDENTIFIABLE with INTERNAL reason
DISCRETISATION_UNSTABLE_ROOT_SET, snapshots retained, no fallback, no runtime switch).

Committed RED before any production change (§10). Wired fixtures 10.1-10.4/10.10 run the real
identify(); disagreement fixtures 10.5-10.9/10.11 exercise the pure comparator at snapshot level.
"""
from __future__ import annotations

import inspect
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from sport_tennis.coherence import solver as S
from sport_tennis.coherence.discretisation_stability import (
    StabilityDecision,
    StabilityReason,
    VariantSolveSnapshot,
    compare_registered_variants,
    count_complete_matchings,
)
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.rootset import MirrorRelation, classify_mirror_relation
from sport_tennis.coherence.scan_variants import (
    A2_ARTIFACT_SHA256,
    G0_NODE_COUNT,
    LATTICE_RULES,
    REGISTERED_VARIANT_ORDER,
    ScanVariant,
    ScanVariantDefinition,
    axis_digest,
    variant_axis,
    variant_definition,
)
from sport_tennis.coherence.solver_contracts import ParameterDomain, SolverStatus
from sport_tennis.coherence.solver_scan import build_scan_axis

from .degeneracy_harness import lattice_g0, lattice_g1, lattice_g2

_REPO = Path(__file__).parents[3]
_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_LINE = Decimal("22.5")
_LO, _HI = 0.35, 0.90
_DOM = (_LO, _HI)
_GOLDEN_V2 = json.loads((Path(__file__).parent / "golden"
                         / "SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED.json").read_text())
_AMENDMENT_YAML = _REPO / "specs" / "programme" \
    / "cross-market-coherence-discretisation-stability-amendment-v1.yaml"
_A2_DIR = _REPO / "docs" / "evidence" / "stage3-cross-market-audit"


def _rnd(x: float | None) -> float | None:
    return None if x is None else round(float(x), 9)


def _golden_case(tw: float, to: float) -> dict[str, Any]:
    for case in _GOLDEN_V2["identify"]:
        if case["tw"] == tw and case["to"] == to:
            return dict(case)
    raise AssertionError(f"golden case not found: {tw}, {to}")


def _got_dict(r: S.IdentificationResult) -> dict[str, object]:
    """The exact V2-golden comparison shape (test_solver_golden convention, round-9)."""
    return {
        "status": r.status,
        "roots": sorted([[_rnd(rt.p_a), _rnd(rt.p_b), rt.a_serves_first, _rnd(rt.residual),
                          _rnd(rt.jacobian_det), rt.on_boundary] for rt in r.roots]),
        "per_server": [[s.a_serves_first, s.status,
                        sorted([[_rnd(x.p_a), _rnd(x.p_b)] for x in s.roots])]
                       for s in r.per_server],
        "domain": list(r.domain), "line": str(r.line),
    }


# ---------------------------------------------------------------- §5 frozen variant vocabulary
def test_scan_variant_vocabulary_frozen() -> None:
    assert [v.name for v in ScanVariant] == [
        "G0_BASELINE", "G1_REGISTERED_VALIDATION", "G2_REGISTERED_VALIDATION"]
    assert REGISTERED_VARIANT_ORDER == (
        ScanVariant.G0_BASELINE, ScanVariant.G1_REGISTERED_VALIDATION,
        ScanVariant.G2_REGISTERED_VALIDATION)
    assert LATTICE_RULES == {
        ScanVariant.G0_BASELINE: "FROZEN_PRODUCTION",
        ScanVariant.G1_REGISTERED_VALIDATION: "NESTED_DOUBLE_DENSITY",
        ScanVariant.G2_REGISTERED_VALIDATION: "HALF_CELL_PHASE_SHIFT",
    }


def test_no_g3_variant_registered() -> None:
    # G3 (NESTED_DOUBLE_DENSITY_PHASE_SHIFT) is diagnostic-only and MUST NOT be runtime-reachable.
    assert not any("G3" in v.name for v in ScanVariant)
    assert len(REGISTERED_VARIANT_ORDER) == 3


def test_g0_axis_is_the_production_axis() -> None:
    assert G0_NODE_COUNT == S._COARSE_N == 13
    assert variant_axis(ScanVariant.G0_BASELINE, _LO, _HI) \
        == build_scan_axis(_LO, _HI, S._COARSE_N)


def test_variant_axes_reproduce_a2_frozen_rules_exactly() -> None:
    """Production transcription must equal the A2 test-only generators FLOAT-EXACTLY."""
    g0 = lattice_g0(_LO, _HI)
    assert variant_axis(ScanVariant.G0_BASELINE, _LO, _HI) == g0
    assert variant_axis(ScanVariant.G1_REGISTERED_VALIDATION, _LO, _HI) == lattice_g1(g0)
    assert variant_axis(ScanVariant.G2_REGISTERED_VALIDATION, _LO, _HI) == lattice_g2(g0)


def test_variant_axes_reproduce_a2_artifact_axes_exactly() -> None:
    for variant, artifact in [
        (ScanVariant.G0_BASELINE, "SOLVER_DEGENERACY_GRID_G0_V1.json"),
        (ScanVariant.G1_REGISTERED_VALIDATION, "SOLVER_DEGENERACY_GRID_G1_V1.json"),
        (ScanVariant.G2_REGISTERED_VALIDATION, "SOLVER_DEGENERACY_GRID_G2_V1.json"),
    ]:
        frozen = json.loads((_A2_DIR / artifact).read_text())
        assert variant_axis(variant, _LO, _HI) == frozen["axis"], variant


def test_g2_dedup_guard_boundary_and_duplicate_semantics() -> None:
    """§15 hardening round 1 (scan_variants gate): the A2 G2 rule's deterministic duplicate
    guard — `shifted not in out and shifted != g0[-1]` — is inert on well-spaced odd-length
    production axes, so its mutants survive the axis-equality pins. These direct unit fixtures
    make every branch observable: boundary collision, duplicate midpoint, interior duplicate,
    unsorted overshoot, midpoint colliding with a non-terminal node."""
    from sport_tennis.coherence.scan_variants import _g2_axis

    # boundary collision: the shifted value equals the terminal node and must be dropped
    # (kills !=-><=, is-not identity, g0[0]-anchor mutants)
    assert _g2_axis([0.0, 1.0, 1.0]) == [0.0, 1.0]
    # midpoint equal to g0[1] but not the terminal node stays (kills the g0[+1] anchor mutant)
    assert _g2_axis([0.0, 0.25, 1.0, 1.0]) == [0.0, 0.625, 1.0]
    # interior duplicate cell: shifted equals g0[-2], NOT the terminal node — must stay
    # (kills the g0[~1]/g0[-2] anchor mutants)
    assert _g2_axis([0.2, 0.6, 0.6, 1.0]) == [0.2, 0.6, 0.8, 1.0]
    # duplicate midpoint already in out: dropped by the membership clause alone
    # (kills the and->or mutant, which would append the duplicate)
    assert _g2_axis([0.0, 1.0, 0.5, 1.0]) == [0.0, 0.75, 1.0]
    # unsorted overshoot: shifted greater than the terminal node still kept when unequal
    # (kills the !=->< ordering mutant)
    assert _g2_axis([0.0, 0.8, 1.2, 0.5]) == [0.0, 1.0, 0.85, 0.5]


def test_g2_interior_range_is_length_arithmetic_not_parity_trick() -> None:
    """§15 hardening round 1: `range(1, len(g0) - 1)` — the ^1 mutant coincides with -1 only
    for odd lengths (every production axis is 13 nodes); an even-length direct fixture makes
    them diverge (the mutant reads past the end)."""
    from sport_tennis.coherence.scan_variants import _g2_axis

    assert _g2_axis([0.0, 0.25, 0.5, 1.0]) == [0.0, 0.375, 0.75, 1.0]


def test_g2_cell_width_is_subtraction_not_modulo() -> None:
    """§15 hardening round 1: on every equally spaced lo>0 axis the float modulo
    g0[i+1] % g0[i] coincides with subtraction (g0[i+1] < 2*g0[i] throughout), so the Sub->Mod
    mutant survives the axis pins; a direct fixture with g0[i+1] >= 2*g0[i] separates them."""
    from sport_tennis.coherence.scan_variants import _g2_axis

    # subtraction: 0.2 + (0.9-0.2)/2 = 0.55; the modulo mutant gives 0.2 + (0.9%0.2)/2 = 0.25
    assert _g2_axis([0.1, 0.2, 0.9]) == [0.1, 0.55, 0.9]


def test_variant_definitions_pin_the_registration() -> None:
    reg = yaml.safe_load(_AMENDMENT_YAML.read_text())["registered_scan_variants"]
    by_name = {v["name"]: v for v in reg["validation"]}
    for variant in REGISTERED_VARIANT_ORDER:
        d = variant_definition(variant, _LO, _HI)
        assert isinstance(d, ScanVariantDefinition)
        assert d.variant is variant
        assert d.lattice_rule == LATTICE_RULES[variant]
        assert d.axis == tuple(variant_axis(variant, _LO, _HI))
        assert d.axis_digest == axis_digest(d.axis)
        assert d.a2_artifact_sha256 == A2_ARTIFACT_SHA256[variant]
        if variant is not ScanVariant.G0_BASELINE:
            assert d.a2_artifact_sha256 == by_name[variant.name]["a2_artifact_sha256"]
    with pytest.raises(Exception):
        d.axis_digest = "x"  # type: ignore[misc,unused-ignore]  # frozen


# ---------------------------------------------------------------- §7 immutable snapshots
def _root(pa: float, pb: float, a_first: bool = True, res: float = 1e-5, jd: float = 1.0,
          boundary: bool = False) -> S.Root:
    return S.Root(p_a=pa, p_b=pb, a_serves_first=a_first, residual=res, jacobian_det=jd,
                  on_boundary=boundary)


def _snap(variant: ScanVariant, status: str, roots: list[S.Root],
          a_first: bool = True) -> VariantSolveSnapshot:
    return VariantSolveSnapshot(
        variant=variant, a_serves_first=a_first, status=status, roots=tuple(roots),
        axis_digest=axis_digest(tuple(variant_axis(variant, _LO, _HI))))


def test_variant_solve_snapshot_immutable_and_digested() -> None:
    snap = _snap(ScanVariant.G0_BASELINE, S.IDENTIFIED, [_root(0.6, 0.55)])
    with pytest.raises(Exception):
        snap.status = S.NO_ROOT  # type: ignore[misc]
    ser = snap.serialize()
    assert ser == snap.serialize()                       # deterministic
    dig = snap.digest()
    assert isinstance(dig, str) and len(dig) == 64
    other = _snap(ScanVariant.G0_BASELINE, S.NO_ROOT, [])
    assert other.digest() != dig                         # content-sensitive


def _pd() -> ParameterDomain:
    return ParameterDomain.from_symmetric(_LO, _HI)


def _compare(snaps: list[VariantSolveSnapshot]) -> StabilityDecision:
    return compare_registered_variants(tuple(snaps), domain=_pd(), tolerance=S._DEDUP_TOL)


def _trio(g0: tuple[str, list[S.Root]], g1: tuple[str, list[S.Root]],
          g2: tuple[str, list[S.Root]]) -> list[VariantSolveSnapshot]:
    return [_snap(ScanVariant.G0_BASELINE, *g0),
            _snap(ScanVariant.G1_REGISTERED_VALIDATION, *g1),
            _snap(ScanVariant.G2_REGISTERED_VALIDATION, *g2)]


# ---------------------------------------------------------------- §8 comparator (snapshot level)
def test_10_5_root_count_disagreement_is_unstable() -> None:
    two = [_root(0.40, 0.40), _root(0.60, 0.60)]
    three = [_root(0.40, 0.40), _root(0.50, 0.50), _root(0.60, 0.60)]
    d = _compare(_trio((S.MULTIPLE_ROOTS, two), (S.MULTIPLE_ROOTS, three),
                       (S.MULTIPLE_ROOTS, two)))
    assert d.stable is False
    assert d.reason is StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET
    assert any("ROOT_COUNT" in x for x in d.disagreements)
    assert len(d.snapshots) == 3                         # evidence retained


def test_10_6_status_disagreement_and_no_root_mixture_are_unstable() -> None:
    d = _compare(_trio((S.IDENTIFIED, [_root(0.62, 0.62)]), (S.NO_ROOT, []),
                       (S.IDENTIFIED, [_root(0.62, 0.62)])))
    assert d.stable is False
    assert d.reason is StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET
    assert any("STATUS" in x for x in d.disagreements)
    # a NO_ROOT mixture is NEVER stable, whatever the rooted statuses are
    d2 = _compare(_trio((S.MULTIPLE_ROOTS, [_root(0.4, 0.4), _root(0.6, 0.6)]),
                        (S.NO_ROOT, []), (S.NO_ROOT, [])))
    assert d2.stable is False


def test_10_7_location_mismatch_no_or_ambiguous_matching_is_unstable() -> None:
    # no complete matching: one representative moved >= the strict tolerance
    base = [_root(0.40, 0.40), _root(0.60, 0.60)]
    moved = [_root(0.40, 0.40), _root(0.61, 0.61)]
    d = _compare(_trio((S.MULTIPLE_ROOTS, base), (S.MULTIPLE_ROOTS, moved),
                       (S.MULTIPLE_ROOTS, base)))
    assert d.stable is False
    assert d.reason is StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET
    # AMBIGUOUS correspondence (two complete matchings) is ALSO disagreement — set-defined,
    # never resolved by a greedy matcher
    left = [_root(0.5000, 0.5000), _root(0.5005, 0.5005)]
    right = [_root(0.50025, 0.50025), _root(0.50075, 0.50075)]
    d2 = _compare(_trio((S.MULTIPLE_ROOTS, left), (S.MULTIPLE_ROOTS, right),
                        (S.MULTIPLE_ROOTS, left)))
    assert d2.stable is False


def test_count_complete_matchings_is_set_defined() -> None:
    tol = S._DEDUP_TOL
    a, b = _root(0.40, 0.40), _root(0.60, 0.60)
    assert count_complete_matchings((a, b), (_root(0.4002, 0.4002), _root(0.5998, 0.5998)),
                                    tol) == 1
    assert count_complete_matchings((a, b), (_root(0.4002, 0.4002), _root(0.61, 0.61)),
                                    tol) == 0
    left = (_root(0.5000, 0.5000), _root(0.5005, 0.5005))
    right = (_root(0.50025, 0.50025), _root(0.50075, 0.50075))
    assert count_complete_matchings(left, right, tol) == 2
    assert count_complete_matchings((), (), tol) == 1    # empty sets match uniquely


def test_10_8_boundary_flag_mismatch_is_unstable() -> None:
    plain = [_root(0.62, 0.62, boundary=False)]
    flagged = [_root(0.62, 0.62, boundary=True)]
    d = _compare(_trio((S.IDENTIFIED, plain), (S.IDENTIFIED, flagged), (S.IDENTIFIED, plain)))
    assert d.stable is False
    assert d.reason is StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET
    assert any("BOUNDARY" in x for x in d.disagreements)


def test_10_9_mirror_relation_mismatch_is_unstable() -> None:
    # exact mirror pair vs a pairable-but-no-longer-mirror pair (triangle-inequality gap:
    # pairing distances 8e-4 < 1e-3 while the internal mirror distance grows to 1.6e-3)
    mirror = [_root(0.40, 0.40), _root(0.60, 0.60)]
    drifted = [_root(0.4008, 0.4008), _root(0.6008, 0.6008)]
    assert classify_mirror_relation(tuple(mirror), _pd(), S._DEDUP_TOL) \
        is MirrorRelation.ADMISSIBLE_MIRROR_PAIR
    assert classify_mirror_relation(tuple(drifted), _pd(), S._DEDUP_TOL) \
        is MirrorRelation.UNRELATED_MULTIPLE_ROOTS
    d = _compare(_trio((S.MULTIPLE_ROOTS, mirror), (S.MULTIPLE_ROOTS, drifted),
                       (S.MULTIPLE_ROOTS, mirror)))
    assert d.stable is False
    assert any("MIRROR" in x for x in d.disagreements)


def test_all_non_identifiable_is_stable_refusal_agreement() -> None:
    d = _compare(_trio((S.NON_IDENTIFIABLE, [_root(0.78, 0.50, jd=1e-4)]),
                       (S.NON_IDENTIFIABLE, []),
                       (S.NON_IDENTIFIABLE, [_root(0.7805, 0.5002, jd=1e-4)])))
    assert d.stable is True
    assert d.reason is None
    assert d.disagreements == ()
    assert len(d.snapshots) == 3


def test_all_no_root_is_stable() -> None:
    d = _compare(_trio((S.NO_ROOT, []), (S.NO_ROOT, []), (S.NO_ROOT, [])))
    assert d.stable is True and d.reason is None


def test_10_11_root_order_permutation_invariance() -> None:
    stable = _trio((S.MULTIPLE_ROOTS, [_root(0.40, 0.40), _root(0.60, 0.60)]),
                   (S.MULTIPLE_ROOTS, [_root(0.3999, 0.3999), _root(0.5999, 0.5999)]),
                   (S.MULTIPLE_ROOTS, [_root(0.4001, 0.4001), _root(0.6001, 0.6001)]))
    permuted = [VariantSolveSnapshot(variant=s.variant, a_serves_first=s.a_serves_first,
                                     status=s.status, roots=tuple(reversed(s.roots)),
                                     axis_digest=s.axis_digest) for s in stable]
    d1, d2 = _compare(stable), _compare(permuted)
    assert (d1.stable, d1.reason, d1.disagreements) == (d2.stable, d2.reason, d2.disagreements)
    assert d1.stable is True
    unstable = _trio((S.MULTIPLE_ROOTS, [_root(0.40, 0.40), _root(0.60, 0.60)]),
                     (S.MULTIPLE_ROOTS, [_root(0.40, 0.40), _root(0.61, 0.61)]),
                     (S.MULTIPLE_ROOTS, [_root(0.40, 0.40), _root(0.60, 0.60)]))
    permuted_u = [VariantSolveSnapshot(variant=s.variant, a_serves_first=s.a_serves_first,
                                       status=s.status, roots=tuple(reversed(s.roots)),
                                       axis_digest=s.axis_digest) for s in unstable]
    u1, u2 = _compare(unstable), _compare(permuted_u)
    assert (u1.stable, u1.reason, u1.disagreements) == (u2.stable, u2.reason, u2.disagreements)
    assert u1.stable is False


def test_comparator_refuses_malformed_input_rather_than_hiding_it() -> None:
    """Operational failures PROPAGATE — never converted into the internal instability reason."""
    ok = _trio((S.NO_ROOT, []), (S.NO_ROOT, []), (S.NO_ROOT, []))
    with pytest.raises(ValueError):
        _compare(ok[:2])                                  # wrong snapshot count
    with pytest.raises(ValueError):
        _compare([ok[1], ok[0], ok[2]])                   # wrong registered order
    mixed = [ok[0],
             VariantSolveSnapshot(variant=ok[1].variant, a_serves_first=False,
                                  status=ok[1].status, roots=ok[1].roots,
                                  axis_digest=ok[1].axis_digest),
             ok[2]]
    with pytest.raises(ValueError):
        _compare(mixed)                                   # mixed first-server assignment


# ------------------------------------------------- §15 hardening round 1 (stability gate)
def test_decision_serialize_digest_and_frozen() -> None:
    """Kills the serialize/digest survivors: the reason field serializes by exact value (None
    when stable, the enum value when unstable); both digests are the sha256 of the CANONICAL
    (sorted-key, compact) JSON of serialize(); StabilityDecision is frozen."""
    import hashlib
    import json

    stable = _compare(_trio((S.IDENTIFIED, [_root(0.62, 0.58)]),
                            (S.IDENTIFIED, [_root(0.62, 0.58)]),
                            (S.IDENTIFIED, [_root(0.62, 0.58)])))
    assert stable.serialize()["reason"] is None
    unstable = _compare(_trio((S.IDENTIFIED, [_root(0.62, 0.58)]), (S.NO_ROOT, []),
                              (S.IDENTIFIED, [_root(0.62, 0.58)])))
    assert unstable.serialize()["reason"] == "DISCRETISATION_UNSTABLE_ROOT_SET"
    for decision in (stable, unstable):
        canonical = json.dumps(decision.serialize(), sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        assert decision.digest() == hashlib.sha256(canonical).hexdigest()
    snap = stable.snapshots[0]
    canonical = json.dumps(snap.serialize(), sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    assert snap.digest() == hashlib.sha256(canonical).hexdigest()
    with pytest.raises(Exception):
        stable.stable = False  # type: ignore[misc]      # frozen dataclass


def test_matching_count_cap_and_length_mismatch_directions() -> None:
    """Kills the enumeration-cap and length-guard survivors: a 3x3 fully-adjacent cluster has
    six complete matchings and must report cap+1 == 3 exactly; BOTH length-mismatch directions
    return 0 (never an exception, never a vacuous match)."""
    cluster = tuple(_root(0.5 + i * 2.5e-4, 0.5 + i * 2.5e-4) for i in range(3))
    assert count_complete_matchings(cluster, cluster, S._DEDUP_TOL) == 3
    one = (_root(0.5, 0.5),)
    assert count_complete_matchings(one, (), S._DEDUP_TOL) == 0
    assert count_complete_matchings((), one, S._DEDUP_TOL) == 0


def test_comparator_refuses_surplus_snapshots_and_positional_calls() -> None:
    """Kills the input-guard survivors: FOUR snapshots raise (not only too few), and the
    domain/tolerance parameters are keyword-only by contract."""
    ok = _trio((S.NO_ROOT, []), (S.NO_ROOT, []), (S.NO_ROOT, []))
    with pytest.raises(ValueError):
        _compare(list(ok) + [ok[0]])
    with pytest.raises(TypeError):
        compare_registered_variants(tuple(ok), _pd(), S._DEDUP_TOL)  # type: ignore[misc,unused-ignore]


def test_comparison_base_is_g0_for_status_and_mirror() -> None:
    """Kills the base-anchor survivors (snapshots[0] -> [1]/[-1]): a trio where ONLY G0
    disagrees — in status (same count, same coordinates) and separately in mirror relation —
    must be unstable; a base anchored on G1/G2 would see agreement."""
    x = [_root(0.62, 0.58)]
    d = _compare(_trio((S.NON_IDENTIFIABLE, x), (S.IDENTIFIED, x), (S.IDENTIFIED, x)))
    assert d.stable is False
    assert d.disagreements == (
        "STATUS_DISAGREEMENT[G0_BASELINE=NON_IDENTIFIABLE,G1_REGISTERED_VALIDATION=IDENTIFIED]",
        "STATUS_DISAGREEMENT[G0_BASELINE=NON_IDENTIFIABLE,G2_REGISTERED_VALIDATION=IDENTIFIED]",
    )
    mirror = [_root(0.40, 0.40), _root(0.60, 0.60)]
    drifted = [_root(0.4008, 0.4008), _root(0.6008, 0.6008)]
    d2 = _compare(_trio((S.MULTIPLE_ROOTS, mirror), (S.MULTIPLE_ROOTS, drifted),
                        (S.MULTIPLE_ROOTS, drifted)))
    assert d2.stable is False
    assert d2.disagreements == (
        "MIRROR_RELATION_DISAGREEMENT[G0_BASELINE=ADMISSIBLE_MIRROR_PAIR,"
        "G1_REGISTERED_VALIDATION=UNRELATED_MULTIPLE_ROOTS]",
        "MIRROR_RELATION_DISAGREEMENT[G0_BASELINE=ADMISSIBLE_MIRROR_PAIR,"
        "G2_REGISTERED_VALIDATION=UNRELATED_MULTIPLE_ROOTS]",
    )


def test_status_comparison_is_value_equality_not_identity_or_ordering() -> None:
    """Kills the string-comparison survivors: equal-VALUE distinct-identity status strings are
    agreement (both for ordinary statuses and for the all-refusal rule), and a status pair that
    sorts lexicographically below the base is still a disagreement."""
    x = [_root(0.62, 0.58)]
    runtime_identified = "".join(["IDENT", "IFIED"])
    d = _compare(_trio((S.IDENTIFIED, x), (runtime_identified, x), (S.IDENTIFIED, x)))
    assert d.stable is True and d.disagreements == ()
    runtime_refusal = "".join(["NON_", "IDENTIFIABLE"])
    d2 = _compare(_trio((S.NON_IDENTIFIABLE, [_root(0.78, 0.50)]),
                        (runtime_refusal, []),
                        (S.NON_IDENTIFIABLE, [_root(0.7805, 0.5002)])))
    assert d2.stable is True and d2.disagreements == ()
    d3 = _compare(_trio((S.IDENTIFIED, x), (S.BOUNDARY_SOLUTION, x), (S.IDENTIFIED, x)))
    assert d3.stable is False
    assert d3.disagreements == (
        "STATUS_DISAGREEMENT[G0_BASELINE=IDENTIFIED,"
        "G1_REGISTERED_VALIDATION=BOUNDARY_SOLUTION]",)


def test_pairwise_disagreements_are_exhaustive_and_direction_blind() -> None:
    """Kills the pairwise-loop survivors (directional count comparisons, continue->break,
    boundary direction, ambiguity thresholds): the EXACT disagreement tuples are pinned for a
    both-direction count trio, an all-pairs-absent trio, a double-ambiguity trio away from the
    mirror line, and a two-pair boundary trio."""
    two = [_root(0.62, 0.58), _root(0.70, 0.66)]
    three = two + [_root(0.55, 0.45)]
    d = _compare(_trio((S.MULTIPLE_ROOTS, two), (S.MULTIPLE_ROOTS, three),
                       (S.MULTIPLE_ROOTS, two)))
    assert d.disagreements == (
        "ROOT_COUNT_DISAGREEMENT[G0_BASELINE=2,G1_REGISTERED_VALIDATION=3]",
        "ROOT_COUNT_DISAGREEMENT[G1_REGISTERED_VALIDATION=3,G2_REGISTERED_VALIDATION=2]",
    )
    d2 = _compare(_trio((S.IDENTIFIED, [_root(0.40, 0.40)]),
                        (S.IDENTIFIED, [_root(0.55, 0.55)]),
                        (S.IDENTIFIED, [_root(0.62, 0.58)])))
    assert d2.disagreements == (
        "LOCATION_MATCHING_ABSENT[G0_BASELINE,G1_REGISTERED_VALIDATION]",
        "LOCATION_MATCHING_ABSENT[G0_BASELINE,G2_REGISTERED_VALIDATION]",
        "LOCATION_MATCHING_ABSENT[G1_REGISTERED_VALIDATION,G2_REGISTERED_VALIDATION]",
    )
    g0 = [_root(0.7, 0.6), _root(0.7005, 0.6005)]
    g1 = [_root(0.70025, 0.60025), _root(0.70075, 0.60075)]
    d3 = _compare(_trio((S.MULTIPLE_ROOTS, g0), (S.MULTIPLE_ROOTS, g1),
                        (S.MULTIPLE_ROOTS, g0)))
    assert d3.disagreements == (
        "LOCATION_MATCHING_AMBIGUOUS[G0_BASELINE,G1_REGISTERED_VALIDATION]",
        "LOCATION_MATCHING_AMBIGUOUS[G0_BASELINE,G2_REGISTERED_VALIDATION]",
        "LOCATION_MATCHING_AMBIGUOUS[G1_REGISTERED_VALIDATION,G2_REGISTERED_VALIDATION]",
    )
    plain = [_root(0.62, 0.58, boundary=False), _root(0.70, 0.66, boundary=False)]
    flagged = [_root(0.62, 0.58, boundary=True), _root(0.70, 0.66, boundary=True)]
    d4 = _compare(_trio((S.MULTIPLE_ROOTS, plain), (S.MULTIPLE_ROOTS, flagged),
                        (S.MULTIPLE_ROOTS, plain)))
    assert d4.disagreements == (
        "BOUNDARY_FLAG_DISAGREEMENT[G0_BASELINE,G1_REGISTERED_VALIDATION]",
        "BOUNDARY_FLAG_DISAGREEMENT[G1_REGISTERED_VALIDATION,G2_REGISTERED_VALIDATION]",
    )


# ---------------------------------------------------------------- §6/§9 wired identify fixtures
@pytest.fixture(scope="module")
def valley_result() -> S.IdentificationResult:
    tw, to = S.derived_targets(0.5, 0.5, _FMT, _LINE, a_serves_first=True)
    return S.identify(tw, to, _LINE, _FMT, domain=_DOM)


def test_10_1_a2_valley_refused_with_internal_reason(
        valley_result: S.IdentificationResult) -> None:
    r = valley_result
    assert r.status == S.NON_IDENTIFIABLE
    assert r.roots == ()                                  # no public root from any variant
    for solve in r.per_server:
        assert solve.status == S.NON_IDENTIFIABLE
        assert solve.roots == ()
        st = solve.stability
        assert st is not None and st.stable is False
        assert st.reason is StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET
        assert tuple(s.variant for s in st.snapshots) == REGISTERED_VARIANT_ORDER
        # the per-variant evidence is retained: the A2-frozen counts (G0=3, G1=4) are visible
        assert st.snapshots[0].status == S.MULTIPLE_ROOTS and len(st.snapshots[0].roots) == 3
        assert len(st.snapshots[1].roots) == 4


def test_10_2_stable_unique_root_is_byte_identical_to_v2(
) -> None:
    case = _golden_case(0.895558727, 0.399655852)
    r = S.identify(case["tw"], case["to"], Decimal(case["line"]), _FMT,
                   domain=tuple(case["domain"]))  # type: ignore[arg-type,unused-ignore]
    assert _got_dict(r) == case["out"]                    # G0 result retained byte-identically
    for solve in r.per_server:
        assert solve.stability is not None and solve.stability.stable is True
        assert solve.stability.reason is None
        assert len(solve.stability.snapshots) == 3        # agreement evidence retained


def test_10_3_stable_no_root_is_byte_identical_to_v2() -> None:
    case = _golden_case(0.5, 0.2)
    r = S.identify(case["tw"], case["to"], Decimal(case["line"]), _FMT,
                   domain=tuple(case["domain"]))  # type: ignore[arg-type,unused-ignore]
    assert _got_dict(r) == case["out"]
    assert r.status == S.NO_ROOT and r.roots == ()
    for solve in r.per_server:
        assert solve.stability is not None and solve.stability.stable is True


def test_10_4_stable_mirror_pair_is_byte_identical_to_v2() -> None:
    case = _golden_case(0.5, 0.583147184)
    r = S.identify(case["tw"], case["to"], Decimal(case["line"]), _FMT,
                   domain=tuple(case["domain"]))  # type: ignore[arg-type,unused-ignore]
    assert _got_dict(r) == case["out"]
    assert classify_mirror_relation(r.roots, _pd(), S._DEDUP_TOL) \
        is MirrorRelation.ADMISSIBLE_MIRROR_PAIR
    for solve in r.per_server:
        assert solve.stability is not None and solve.stability.stable is True


def test_10_10_first_server_isolation_refuses_before_union() -> None:
    """A-assignment stable (all three variants refuse identically -> stable refusal, G0 kept
    byte-identically); B-assignment unstable (G0 MULTIPLE_ROOTS vs G1/G2 NON_IDENTIFIABLE) ->
    refused with the internal reason BEFORE the union; only the stable assignment's G0 roots
    reach the public result."""
    case = _golden_case(0.999706441, 0.026266616)
    r = S.identify(case["tw"], case["to"], Decimal(case["line"]), _FMT,
                   domain=tuple(case["domain"]))  # type: ignore[arg-type,unused-ignore]
    sa, sb = r.per_server
    assert sa.a_serves_first is True and sb.a_serves_first is False
    # A: stable refusal agreement — the G0 solve retained byte-identically (V2 per_server pin)
    assert sa.stability is not None and sa.stability.stable is True
    assert sa.status == S.NON_IDENTIFIABLE
    assert sorted([[_rnd(x.p_a), _rnd(x.p_b)] for x in sa.roots]) == case["out"]["per_server"][0][2]
    # B: unstable — refused before the union, no roots contributed
    assert sb.stability is not None and sb.stability.stable is False
    assert sb.stability.reason is StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET
    assert sb.status == S.NON_IDENTIFIABLE
    assert sb.roots == ()
    assert sb.stability.snapshots[0].status == S.MULTIPLE_ROOTS
    assert len(sb.stability.snapshots[0].roots) == 2
    # public result: NON_IDENTIFIABLE dominance; ONLY the stable assignment's roots are public
    assert r.status == S.NON_IDENTIFIABLE
    assert sorted([[_rnd(x.p_a), _rnd(x.p_b)] for x in r.roots]) \
        == sorted([[_rnd(x.p_a), _rnd(x.p_b)] for x in sa.roots])


# ---------------------------------------------------------------- §9/§11 policy pins
def test_no_runtime_switch_and_unchanged_public_entrypoint() -> None:
    assert list(inspect.signature(S.identify).parameters) == [
        "target_match_win_a", "target_over", "line", "fmt", "domain"]
    for module in ("solver", "scan_variants", "discretisation_stability"):
        src = (_REPO / "sport_tennis" / "coherence" / f"{module}.py").read_text()
        assert "os.environ" not in src and "getenv" not in src


def test_internal_reason_is_not_a_public_status() -> None:
    assert StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET.value \
        not in {s.value for s in SolverStatus}
