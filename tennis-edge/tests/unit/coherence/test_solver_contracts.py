"""STAGE3-0006C Milestone A — closed solver contracts + input validation (tests-first).

Exhaustively pins the immutable contracts and pure validators so the Milestone A micro-gate kills
every mutation of a bound, its openness, finiteness, component order, determinant orientation, enum
identity, serialization or digest. Boundaries use ``math.nextafter`` around every open edge.
"""
from __future__ import annotations

import dataclasses
import math

import pytest

from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver_contracts import (
    Jacobian2x2,
    ParameterDomain,
    ResidualVector2,
    SolverStatus,
    validate_domain,
    validate_targets,
)

_UP = math.nextafter(0.0, 1.0)          # smallest float above 0
_BELOW1 = math.nextafter(1.0, 0.0)      # largest float below 1
_ABOVE1 = math.nextafter(1.0, 2.0)      # smallest float above 1
_BELOW0 = math.nextafter(0.0, -1.0)     # largest float below 0
_NAN = float("nan")
_INF = float("inf")


# ------------------------------------------------------------------ SolverStatus
def test_solver_status_values_are_the_governed_strings() -> None:
    assert SolverStatus.IDENTIFIED.value == "IDENTIFIED"
    assert SolverStatus.NO_ROOT.value == "NO_ROOT"
    assert SolverStatus.MULTIPLE_ROOTS.value == "MULTIPLE_ROOTS"
    assert SolverStatus.NON_IDENTIFIABLE.value == "NON_IDENTIFIABLE"
    assert SolverStatus.BOUNDARY_SOLUTION.value == "BOUNDARY_SOLUTION"
    assert SolverStatus.FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD.value \
        == "FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD"
    assert SolverStatus.NON_CONVERGED.value == "NON_CONVERGED"
    assert SolverStatus.INVALID_TARGET.value == "INVALID_TARGET"
    assert SolverStatus.INVALID_DOMAIN.value == "INVALID_DOMAIN"
    assert SolverStatus.NONFINITE_ARITHMETIC.value == "NONFINITE_ARITHMETIC"


def test_solver_status_members_are_distinct_singletons() -> None:
    members = list(SolverStatus)
    assert len({m.value for m in members}) == len(members)   # all values distinct


# ------------------------------------------------------------------ validate_domain
def test_validate_domain_accepts_open_interior() -> None:
    validate_domain(0.35, 0.90)
    validate_domain(_UP, _BELOW1)          # tightest admissible open bounds


@pytest.mark.parametrize("lo,hi", [
    (0.0, 0.9),          # lower == 0 (0 < 0 is False)
    (_BELOW0, 0.9),      # lower below 0
    (0.1, 1.0),          # upper == 1
    (0.1, _ABOVE1),      # upper above 1
    (0.5, 0.5),          # lower == upper
    (0.9, 0.35),         # lower > upper
    (_NAN, 0.9), (0.1, _NAN),
    (-_INF, 0.9), (0.1, _INF),
])
def test_validate_domain_refuses(lo: float, hi: float) -> None:
    with pytest.raises(CoherenceMathError):
        validate_domain(lo, hi)


# ------------------------------------------------------------------ validate_targets
def test_validate_targets_accepts_closed_unit_interval() -> None:
    validate_targets(0.0, 1.0)             # both inclusive edges admissible
    validate_targets(1.0, 0.0)
    validate_targets(0.5, 0.5)


@pytest.mark.parametrize("tw,to", [
    (_BELOW0, 0.5), (0.5, _BELOW0),        # just below 0
    (_ABOVE1, 0.5), (0.5, _ABOVE1),        # just above 1
    (_NAN, 0.5), (0.5, _NAN),
    (-_INF, 0.5), (0.5, _INF),
])
def test_validate_targets_refuses(tw: float, to: float) -> None:
    with pytest.raises(CoherenceMathError):
        validate_targets(tw, to)


# ------------------------------------------------------------------ ParameterDomain
def test_parameter_domain_from_symmetric_and_validate() -> None:
    d = ParameterDomain.from_symmetric(0.35, 0.90)
    assert (d.lower_a, d.upper_a, d.lower_b, d.upper_b) == (0.35, 0.90, 0.35, 0.90)
    d.validate()


@pytest.mark.parametrize("dom", [
    ParameterDomain(_NAN, 0.9, 0.35, 0.9), ParameterDomain(0.35, _INF, 0.35, 0.9),
    ParameterDomain(0.35, 0.9, 0.9, 0.35),      # b axis reversed
    ParameterDomain(0.9, 0.35, 0.35, 0.9),      # a axis reversed
    ParameterDomain(0.5, 0.5, 0.35, 0.9),       # a axis zero-width
    ParameterDomain(0.35, 0.9, 0.5, 0.5),       # b axis zero-width
])
def test_parameter_domain_validate_refuses(dom: ParameterDomain) -> None:
    with pytest.raises(CoherenceMathError):
        dom.validate()


def test_parameter_domain_contains_is_inclusive() -> None:
    d = ParameterDomain.from_symmetric(0.35, 0.90)
    assert d.contains(0.6, 0.6)
    # each of the four bounds is INCLUSIVE — exercise the equality point of every `<=` so a
    # `<=`->`<`/`!=`/`is not` mutant on any of the four comparisons is killed.
    assert d.contains(0.35, 0.6)      # p_a == lower_a
    assert d.contains(0.90, 0.6)      # p_a == upper_a
    assert d.contains(0.6, 0.35)      # p_b == lower_b
    assert d.contains(0.6, 0.90)      # p_b == upper_b
    # just outside each of the four bounds is excluded
    assert not d.contains(math.nextafter(0.35, 0.0), 0.6)
    assert not d.contains(math.nextafter(0.90, 1.0), 0.6)
    assert not d.contains(0.6, math.nextafter(0.35, 0.0))
    assert not d.contains(0.6, math.nextafter(0.90, 1.0))


def test_parameter_domain_is_frozen() -> None:
    d = ParameterDomain.from_symmetric(0.35, 0.90)
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.lower_a = 0.0  # type: ignore[misc]


def test_parameter_domain_digest_deterministic_and_sensitive() -> None:
    a = ParameterDomain.from_symmetric(0.35, 0.90).digest()
    assert a == ParameterDomain.from_symmetric(0.35, 0.90).digest()
    assert a != ParameterDomain.from_symmetric(0.35, 0.91).digest()


# ------------------------------------------------------------------ ResidualVector2
def test_residual_vector_inf_norm_and_sum_of_squares() -> None:
    r = ResidualVector2(match_odds_residual=-0.3, total_games_residual=0.4)
    assert r.inf_norm() == 0.4
    assert r.sum_of_squares() == pytest.approx(0.25, abs=1e-12)
    r.validate()


def test_residual_vector_refuses_nonfinite() -> None:
    with pytest.raises(CoherenceMathError):
        ResidualVector2(_NAN, 0.0).validate()
    with pytest.raises(CoherenceMathError):
        ResidualVector2(0.0, _INF).validate()


def test_residual_vector_component_order_in_serialization() -> None:
    r = ResidualVector2(match_odds_residual=0.1, total_games_residual=0.2)
    assert r.serialize() == {"match_odds_residual": 0.1, "total_games_residual": 0.2}


def test_residual_vector_is_frozen() -> None:
    r = ResidualVector2(0.1, 0.2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.match_odds_residual = 0.0  # type: ignore[misc]


# ------------------------------------------------------------------ digest golden pins
def test_contract_digests_are_golden_pinned() -> None:
    # golden digests kill the `sort_keys=True`->False mutant (the serialized field order is NOT
    # already alphabetical, so dropping sort_keys changes the hash).
    assert ParameterDomain.from_symmetric(0.35, 0.90).digest() == (
        "sha256:f7fced687071cda3235451ee47a3856d317b14f25300737bf5d4803c9875ea36")
    assert ResidualVector2(0.1, 0.2).digest() == (
        "sha256:7928f66a14798c5d651d77f2208872f72f2c76b3a0c6a9c0a75f1528b9b4c0b3")
    assert Jacobian2x2(1.0, 2.0, 3.0, 4.0).digest() == (
        "sha256:5e4b3be3b8a43425ee06281a0d68a88de5a8977f9792e2210bc4ab4314e46fb9")


# ------------------------------------------------------------------ Jacobian2x2
def test_jacobian_determinant_is_correctly_oriented() -> None:
    # distinct entries so a row/column swap changes the determinant value.
    j = Jacobian2x2(d_mo_d_a=2.0, d_mo_d_b=3.0, d_tg_d_a=5.0, d_tg_d_b=7.0)
    assert j.determinant() == pytest.approx(2.0 * 7.0 - 3.0 * 5.0, abs=1e-12)   # = -1.0
    assert j.condition_scale() == 7.0


def test_jacobian_refuses_nonfinite() -> None:
    with pytest.raises(CoherenceMathError):
        Jacobian2x2(_NAN, 1.0, 1.0, 1.0).validate()


def test_jacobian_is_frozen_and_serializes_by_role() -> None:
    j = Jacobian2x2(1.0, 2.0, 3.0, 4.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        j.d_mo_d_a = 0.0  # type: ignore[misc]
    assert j.serialize() == {"d_mo_d_a": 1.0, "d_mo_d_b": 2.0, "d_tg_d_a": 3.0, "d_tg_d_b": 4.0}
