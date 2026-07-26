"""STAGE3-0005 §13/§14/§15 — deterministic bounded identification solver.

Synthetic-only. Round-trip recovery (targets built from known parameters are recovered), the
first-server nuisance dual-evaluation, and the structural refusals — plus determinism.

Structural finding (not a defect): identification from Match-Odds + ONE Total-Games line has a
MIRROR ambiguity. Replacing (p_a, p_b) by (1-p_a, 1-p_b) leaves the total-games distribution
unchanged and complements the match-win probability, so a match is point-identified only when its
mirror parameter pair falls OUTSIDE the parameter domain. Symmetric / near-symmetric matches are
therefore NON-identified (MULTIPLE_ROOTS). Only the permitted §15 status vocabulary is emitted.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver import (
    FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD,
    IDENTIFIED,
    MULTIPLE_ROOTS,
    NON_IDENTIFIABLE,
    NO_ROOT,
    _jacobian_det,
    derived_targets,
    identify,
)

_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_DOMAIN = (0.35, 0.90)
_LINE = Decimal("22.5")
_IDENTIFIABLE = (IDENTIFIED, FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD)


def _recovered(res: object) -> tuple[float, float]:
    # The generating (a_serves_first=True) solve always carries the physical truth.
    a_first = res.per_server[0]  # type: ignore[attr-defined]
    assert a_first.a_serves_first is True
    assert a_first.status == IDENTIFIED
    return a_first.roots[0].p_a, a_first.roots[0].p_b


# ------------------------------------------------------------------ round-trip recovery
def test_identify_recovers_asymmetric_truth_when_mirror_out_of_domain() -> None:
    # (0.68, 0.58) mirror is (0.32, 0.42): 0.32 < 0.35, so the mirror is excluded and the match
    # is uniquely identified. (match_win ~0.90 is well below saturation, so it is well-posed.)
    tw, to = derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
    res = identify(tw, to, _LINE, _FMT, domain=_DOMAIN)
    assert res.status in _IDENTIFIABLE
    pa, pb = _recovered(res)
    assert pa == pytest.approx(0.68, abs=5e-3)
    assert pb == pytest.approx(0.58, abs=5e-3)


def test_recovered_pa_preserves_truth_ordering() -> None:
    # Two well-posed matches with mirrors out of domain ((0.32,0.42) and (0.26,0.44)) are each
    # recovered; the recovered p_a preserve the true ordering (recovery fidelity).
    lo_t = derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
    hi_t = derived_targets(0.74, 0.56, _FMT, _LINE, a_serves_first=True)
    lo = identify(lo_t[0], lo_t[1], _LINE, _FMT, domain=_DOMAIN)
    hi = identify(hi_t[0], hi_t[1], _LINE, _FMT, domain=_DOMAIN)
    assert _recovered(hi)[0] > _recovered(lo)[0]


def test_near_certain_match_is_not_point_identified() -> None:
    # A near-certain match (match_win ~0.9997) saturates match-win: the identification Jacobian is
    # singular and the solver honestly refuses point identification rather than over-claiming.
    tw, to = derived_targets(0.78, 0.50, _FMT, _LINE, a_serves_first=True)
    res = identify(tw, to, _LINE, _FMT, domain=_DOMAIN)
    assert res.status in (NON_IDENTIFIABLE, MULTIPLE_ROOTS, NO_ROOT)


# ---------------------------------------------------- mirror degeneracy (structural finding)
def test_symmetric_match_is_mirror_degenerate() -> None:
    tw, to = derived_targets(0.60, 0.60, _FMT, _LINE, a_serves_first=True)
    res = identify(tw, to, _LINE, _FMT, domain=_DOMAIN)
    assert res.status == MULTIPLE_ROOTS
    pas = sorted(round(r.p_a, 2) for r in res.roots)
    # the true pair (0.60,0.60) and its in-domain mirror (0.40,0.40)
    assert 0.40 == pytest.approx(pas[0], abs=1e-2)
    assert 0.60 == pytest.approx(pas[-1], abs=1e-2)


# ------------------------------------------------------------------ structural refusals
def test_unreachable_over_target_is_no_root() -> None:
    # No BO3 match reaches > 40 games; Over(40.5) is 0 for every parameter, so an Over target of
    # 0.2 is unreachable.
    res = identify(0.5, 0.2, Decimal("40.5"), _FMT, domain=_DOMAIN)
    assert res.status == NO_ROOT
    assert res.roots == ()


def test_flat_over_line_is_not_identified() -> None:
    # Below the minimum total (12 games) Over is 1.0 everywhere: the Over equation carries no
    # gradient, so the configuration is not point-identified (a continuum), never IDENTIFIED.
    res = identify(0.5, 1.0, Decimal("11.5"), _FMT, domain=(0.50, 0.70))
    assert res.status in (MULTIPLE_ROOTS, NON_IDENTIFIABLE)


def test_jacobian_degenerate_when_over_is_flat() -> None:
    # Over(11.5) is constant (1.0) across the domain -> both Over partials are ~0 -> singular
    # identification Jacobian (the NON_IDENTIFIABLE detector).
    det = _jacobian_det(0.60, 0.60, True, _FMT, Decimal("11.5"), 0.5, 1.0)
    assert abs(det) < 5e-3


def test_jacobian_nondegenerate_at_normal_point() -> None:
    det = _jacobian_det(0.63, 0.57, True, _FMT, _LINE,
                        *derived_targets(0.63, 0.57, _FMT, _LINE, a_serves_first=True))
    assert abs(det) >= 5e-3


# ------------------------------------------------------------------ determinism / validation
def test_identify_is_deterministic() -> None:
    tw, to = derived_targets(0.74, 0.52, _FMT, _LINE, a_serves_first=True)
    a = identify(tw, to, _LINE, _FMT, domain=_DOMAIN)
    b = identify(tw, to, _LINE, _FMT, domain=_DOMAIN)
    assert a == b


def test_bad_domain_refused() -> None:
    with pytest.raises(CoherenceMathError):
        identify(0.5, 0.5, _LINE, _FMT, domain=(0.9, 0.35))
    with pytest.raises(CoherenceMathError):
        identify(0.5, 0.5, _LINE, _FMT, domain=(0.0, 0.9))


def test_bad_targets_refused() -> None:
    with pytest.raises(CoherenceMathError):
        identify(1.2, 0.5, _LINE, _FMT, domain=_DOMAIN)
    with pytest.raises(CoherenceMathError):
        identify(0.5, -0.1, _LINE, _FMT, domain=_DOMAIN)
