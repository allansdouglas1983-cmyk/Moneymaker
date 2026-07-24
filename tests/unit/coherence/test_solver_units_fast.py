"""STAGE3-0006 §4/§7 — DIRECT unit pins on the solver helpers (fast mutation surface).

A full ``identify`` runs thousands of BO3 match-DP evaluations (~6s), so pinning solver numerics
only through ``identify`` makes mutation testing take hours. Almost every solver mutant lives in a
pure helper — ``_validate_domain``, ``_clamp``, ``_r2``, ``_residual``, ``_jacobian``,
``_jacobian_det``, ``_canonical_roots``, ``_refine`` — each callable directly with a handful of match-DP
evaluations (sub-millisecond to ~0.1s). Pinning their exact outputs here kills the residual/
refinement/Jacobian/dedup arithmetic in milliseconds; only the ``_solve_one``/``identify``
orchestration then needs the expensive identify (covered by test_solver_mutation_fast.py and
test_solver.py). Values are characterised from the real functions; the tolerances are tight.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver import (
    Root,
    _canonical_roots,
    _clamp,
    _jacobian,
    _jacobian_det,
    _r2,
    _refine,
    _residual,
    _validate_domain,
    derived_targets,
)

_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_LINE = Decimal("22.5")
_TOL = 1e-9


# ----------------------------------------------------------------- _validate_domain
@pytest.mark.parametrize("dom", [(0.9, 0.35), (0.0, 0.9), (0.35, 1.0), (0.35, 0.35), (-0.1, 0.9)])
def test_validate_domain_refuses_bad(dom: tuple[float, float]) -> None:
    with pytest.raises(CoherenceMathError):
        _validate_domain(dom)


def test_validate_domain_accepts_good() -> None:
    _validate_domain((0.35, 0.90))   # must not raise


# ----------------------------------------------------------------- _clamp
def test_clamp_exact() -> None:
    assert _clamp(0.5, 0.35, 0.9) == 0.5      # within
    assert _clamp(0.1, 0.35, 0.9) == 0.35     # below -> lo
    assert _clamp(0.99, 0.35, 0.9) == 0.9     # above -> hi
    assert _clamp(0.35, 0.35, 0.9) == 0.35    # on lower edge
    assert _clamp(0.9, 0.35, 0.9) == 0.9      # on upper edge


# ----------------------------------------------------------------- _r2
def test_r2_is_sum_of_squares() -> None:
    assert _r2((0.3, 0.4)) == pytest.approx(0.25, abs=_TOL)
    assert _r2((0.0, 0.0)) == 0.0
    assert _r2((1.0, 2.0)) == pytest.approx(5.0, abs=_TOL)


# ----------------------------------------------------------------- _residual
def test_residual_zero_at_truth_and_exact_off() -> None:
    tw, to = derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
    # at the generating point the residual is exactly (0, 0)
    f = _residual(0.68, 0.58, True, _FMT, _LINE, tw, to)
    assert f[0] == pytest.approx(0.0, abs=1e-9)
    assert f[1] == pytest.approx(0.0, abs=1e-9)
    # at an offset the residual is a pinned non-zero pair (kills the two subtractions)
    g = _residual(0.60, 0.60, True, _FMT, _LINE, tw, to)
    assert g[0] == pytest.approx(-0.39555872705363715, abs=1e-9)
    assert g[1] == pytest.approx(0.18349133194834705, abs=1e-9)


# ----------------------------------------------------------------- _jacobian / _jacobian_det
def test_jacobian_exact() -> None:
    tw, to = derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
    d11, d21, d12, d22 = _jacobian(0.63, 0.57, True, _FMT, _LINE, tw, to)
    assert d11 == pytest.approx(3.720173788325284, abs=1e-6)
    assert d21 == pytest.approx(-2.329043114986271, abs=1e-6)
    assert d12 == pytest.approx(-3.8957015756573807, abs=1e-6)
    assert d22 == pytest.approx(3.074023670509765, abs=1e-6)


def test_jacobian_det_is_cross_product() -> None:
    tw, to = derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
    assert _jacobian_det(0.63, 0.57, True, _FMT, _LINE, tw, to) == pytest.approx(
        2.3626453508959155, abs=1e-6)


# ----------------------------------------------------------------- _canonical_roots
# GOVERNED TEST REPLACEMENT (STAGE3-0006C-D-A1, specs/programme/
# cross-market-coherence-root-dedup-amendment-v1.yaml): the previous test here pinned the removed
# sequence-defined greedy first-seen _dedup (kept[0] is r1 by DISCOVERY order) — the exact defect
# the founder amendment corrects. It is replaced, under the amendment's authority, by the
# set-defined canonical pin: same merge/keep expectations, canonical (p_a-ascending) output order
# and a canonical-key representative instead of first-seen.
def test_canonical_roots_merges_within_tol_keeps_distinct() -> None:
    r1 = Root(0.68, 0.58, True, 0.0, 1.0, False)
    r2 = Root(0.6801, 0.5801, True, 0.0, 1.0, False)   # within _DEDUP_TOL of r1
    r3 = Root(0.40, 0.42, True, 0.0, 1.0, False)       # a distinct basin
    kept, ambiguous = _canonical_roots([r1, r2, r3])
    assert not ambiguous
    assert len(kept) == 2
    # canonical order (p_a ascending): r3 first; the r1/r2 cluster's representative is r1
    # (residual tie 0.0 -> lower p_a wins), independent of input order.
    assert kept == (r3, r1)
    assert _canonical_roots([r2, r3, r1])[0] == (r3, r1)   # permutation-invariant


# ----------------------------------------------------------------- _refine
def test_refine_converges_to_truth() -> None:
    tw, to = derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
    pa, pb, r2 = _refine(0.66, 0.60, (0.90 - 0.35) / 12, True, _FMT, _LINE, tw, to, 0.35, 0.90)
    assert pa == pytest.approx(0.68, abs=5e-3)
    assert pb == pytest.approx(0.58, abs=5e-3)
    assert r2 <= 1e-4 * 1e-4       # converged inside the root tolerance
