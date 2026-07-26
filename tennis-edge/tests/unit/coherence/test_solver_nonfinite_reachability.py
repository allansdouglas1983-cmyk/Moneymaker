"""STAGE3-0006C-D-REV1 §1 — non-finite reachability injection tests.

Resolves NONFINITE_PASSTHROUGH_INCIDENTAL: proves that non-finite values are refused at the
validated public boundary, and that even INJECTED non-finite internals (test-only monkeypatch
dependency injection — production is never altered) are structurally contained by the root
acceptance gate: ``residual_norm2_within_tolerance(NaN, tol)`` is False and
``prefer_newton_candidate(NaN, x)`` is False, so no non-finite value can ever reach Root
construction, deduplication, final selection output, or the public result. Characterisation of
FROZEN behaviour — nothing here corrects anything.
"""
from __future__ import annotations

import math
from decimal import Decimal

import pytest

from sport_tennis.coherence import solver as S
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver_iteration import (
    prefer_newton_candidate,
    residual_norm2_within_tolerance,
)

_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_LINE = Decimal("22.5")
_NAN = float("nan")
_INF = float("inf")


# ------------------------------------------------- public boundary refusals (audit items 1-3)
@pytest.mark.parametrize("tw,to", [
    (_NAN, 0.5), (0.5, _NAN), (_INF, 0.5), (0.5, -_INF), (-_INF, _INF),
])
def test_identify_refuses_nonfinite_targets(tw: float, to: float) -> None:
    with pytest.raises(CoherenceMathError):
        S.identify(tw, to, _LINE, _FMT, domain=(0.35, 0.90))


@pytest.mark.parametrize("dom", [
    (_NAN, 0.9), (0.35, _NAN), (-_INF, 0.9), (0.35, _INF), (_NAN, _NAN),
])
def test_identify_refuses_nonfinite_domain(dom: tuple[float, float]) -> None:
    with pytest.raises(CoherenceMathError):
        S.identify(0.6, 0.5, _LINE, _FMT, domain=dom)


def test_identify_refuses_nan_line() -> None:
    # Decimal NaN fails the multiple-of-0.5 validation (NaN != NaN is True -> refusal raised at
    # the first over_under evaluation inside the residual).
    with pytest.raises(CoherenceMathError):
        S.identify(0.6, 0.5, Decimal("NaN"), _FMT, domain=(0.35, 0.90))


# --------------------------------------- injected non-finite residual (audit items 4, 9-14)
def test_injected_nan_residual_is_contained_no_root_no_nonfinite_output(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Even if EVERY residual evaluation returned NaN, the frozen root gate (inclusive <= against
    the tolerance; False for NaN) prevents any Root construction: the public result is NO_ROOT
    with an empty root tuple — no non-finite value reaches Root, dedup, selection or the result."""
    monkeypatch.setattr(S, "_residual", lambda *_a, **_k: (_NAN, _NAN))
    r = S.identify(0.6, 0.5, _LINE, _FMT, domain=(0.35, 0.90))
    assert r.status == S.NO_ROOT
    assert r.roots == ()
    for s in r.per_server:
        assert s.status == S.NO_ROOT and s.roots == ()


def test_injected_inf_residual_is_contained(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(S, "_residual", lambda *_a, **_k: (_INF, -_INF))
    r = S.identify(0.6, 0.5, _LINE, _FMT, domain=(0.35, 0.90))
    assert r.status == S.NO_ROOT and r.roots == ()


# ----------------------------- injected non-finite Jacobian / Newton step (audit items 5-8)
def test_injected_nan_jacobian_is_refused_by_the_math_layer(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A NaN Jacobian poisons the Newton step (NaN deltas -> NaN candidate via one clamp
    passthrough), and the FROZEN containment is refusal-by-exception: the residual generator's
    normalization guard (``check_normalized``, scoring.py — 'NaN and the infinities are refused
    EXPLICITLY') raises a typed CoherenceMathError the moment the NaN point is evaluated. A
    non-finite candidate cannot even be residual-evaluated, so it can never satisfy the root gate
    or reach Root construction."""
    from sport_tennis.coherence.solver_contracts import Jacobian2x2
    monkeypatch.setattr(S, "_jacobian_matrix",
                        lambda *_a, **_k: Jacobian2x2(_NAN, _NAN, _NAN, _NAN))
    tw, to = S.derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
    with pytest.raises(CoherenceMathError):
        S._refine(0.66, 0.60, (0.90 - 0.35) / 12, True, _FMT, _LINE, tw, to, 0.35, 0.90)


# --------------------------------------------- gate invariants (audit items 9, 11, 12, 13)
def test_root_gate_refuses_nonfinite_norms() -> None:
    # the ONLY path into Root construction is residual_norm2_within_tolerance(r2, _ROOT_TOL);
    # NaN/inf norms are refused (comparison False), so a non-finite candidate can never become
    # a Root, enter _dedup, or appear in the public root set.
    assert not residual_norm2_within_tolerance(_NAN, S._ROOT_TOL)
    assert not residual_norm2_within_tolerance(_INF, S._ROOT_TOL)


def test_final_selection_refuses_nonfinite_newton_norms() -> None:
    assert not prefer_newton_candidate(_NAN, 1e-9)
    assert not prefer_newton_candidate(_INF, 1e-9)


# --------------------------------------------------------- validated-path output finiteness
def test_validated_path_public_output_is_entirely_finite() -> None:
    tw, to = S.derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
    r = S.identify(tw, to, _LINE, _FMT, domain=(0.35, 0.90))
    for rt in r.roots:
        assert math.isfinite(rt.p_a) and math.isfinite(rt.p_b)
        assert math.isfinite(rt.residual) and math.isfinite(rt.jacobian_det)
    for s in r.per_server:
        for rt in s.roots:
            assert math.isfinite(rt.p_a) and math.isfinite(rt.p_b)
