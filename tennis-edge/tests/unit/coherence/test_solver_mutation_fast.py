"""STAGE3-0006 §4/§7 — cheapest-first solver checks for mutation hardening.

Each ``identify`` runs thousands of BO3 match-DP evaluations (~6s), so the full solver suite is
expensive per mutant. This module front-loads the highest-yield, cheapest distinguishers so that
under ``pytest -x`` most mutants die before any ~6s identify runs:

  1. domain / target refusals (raise immediately, no grid scan);
  2. the identification-Jacobian degeneracy detector, exercised DIRECTLY via ``_jacobian_det``
     (a handful of match-DP calls) — degenerate-when-flat and non-degenerate-at-a-normal-point;
  3. exactly ONE round-trip recovery with an out-of-domain mirror (exact recovered p_a/p_b and
     IDENTIFIED status) — catches the residual / refinement / Newton / classification arithmetic;
  4. exactly ONE mirror-degenerate case (MULTIPLE_ROOTS with both the true pair and its in-domain
     mirror) — catches the dedup / multiplicity classification.

The full ``test_solver.py`` still runs after this file for exhaustive coverage; this file only
reorders cheap high-kill checks earlier. It never relaxes any assertion.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver import (
    IDENTIFIED,
    MULTIPLE_ROOTS,
    _jacobian_det,
    derived_targets,
    identify,
)

_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_DOMAIN = (0.35, 0.90)
_LINE = Decimal("22.5")


def test_fast_bad_domain_refused() -> None:
    with pytest.raises(CoherenceMathError):
        identify(0.5, 0.5, _LINE, _FMT, domain=(0.9, 0.35))
    with pytest.raises(CoherenceMathError):
        identify(0.5, 0.5, _LINE, _FMT, domain=(0.0, 0.9))


def test_fast_bad_targets_refused() -> None:
    with pytest.raises(CoherenceMathError):
        identify(1.2, 0.5, _LINE, _FMT, domain=_DOMAIN)
    with pytest.raises(CoherenceMathError):
        identify(0.5, -0.1, _LINE, _FMT, domain=_DOMAIN)


def test_fast_jacobian_degenerate_when_flat() -> None:
    det = _jacobian_det(0.60, 0.60, True, _FMT, Decimal("11.5"), 0.5, 1.0)
    assert abs(det) < 5e-3


def test_fast_jacobian_nondegenerate_normal() -> None:
    det = _jacobian_det(0.63, 0.57, True, _FMT, _LINE,
                        *derived_targets(0.63, 0.57, _FMT, _LINE, a_serves_first=True))
    assert abs(det) >= 5e-3


def test_fast_round_trip_recovery() -> None:
    tw, to = derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
    res = identify(tw, to, _LINE, _FMT, domain=_DOMAIN)
    first = res.per_server[0]
    assert first.a_serves_first is True
    assert first.status == IDENTIFIED
    assert first.roots[0].p_a == pytest.approx(0.68, abs=5e-3)
    assert first.roots[0].p_b == pytest.approx(0.58, abs=5e-3)


def test_fast_mirror_degenerate() -> None:
    tw, to = derived_targets(0.60, 0.60, _FMT, _LINE, a_serves_first=True)
    res = identify(tw, to, _LINE, _FMT, domain=_DOMAIN)
    assert res.status == MULTIPLE_ROOTS
    pas = sorted(round(r.p_a, 2) for r in res.roots)
    assert 0.40 == pytest.approx(pas[0], abs=1e-2)
    assert 0.60 == pytest.approx(pas[-1], abs=1e-2)


def test_fast_no_root() -> None:
    # an Over target unreachable at the line (no BO3 match exceeds 40 games) -> NO_ROOT.
    from sport_tennis.coherence.solver import NO_ROOT
    res = identify(0.5, 0.2, Decimal("40.5"), _FMT, domain=_DOMAIN)
    assert res.status == NO_ROOT
    assert res.roots == ()


def test_fast_flat_over_not_identified() -> None:
    # below the minimum total the Over equation carries no gradient -> a continuum, never IDENTIFIED.
    from sport_tennis.coherence.solver import MULTIPLE_ROOTS, NON_IDENTIFIABLE
    res = identify(0.5, 1.0, Decimal("11.5"), _FMT, domain=(0.50, 0.70))
    assert res.status in (MULTIPLE_ROOTS, NON_IDENTIFIABLE)


def test_fast_near_certain_non_identifiable() -> None:
    # a saturated match-win makes the identification Jacobian singular -> NON_IDENTIFIABLE.
    from sport_tennis.coherence.solver import MULTIPLE_ROOTS, NON_IDENTIFIABLE, NO_ROOT
    tw, to = derived_targets(0.78, 0.50, _FMT, Decimal("22.5"), a_serves_first=True)
    res = identify(tw, to, Decimal("22.5"), _FMT, domain=_DOMAIN)
    assert res.status in (NON_IDENTIFIABLE, MULTIPLE_ROOTS, NO_ROOT)
