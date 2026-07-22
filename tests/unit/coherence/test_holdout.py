"""STAGE3-0005 §15 — holdout-coherence contract (raw metrics + structural statuses).

Synthetic-only. Projects an identified origin onto reserved holdout lines and reports RAW metrics
only — model-implied range, observed interval/midpoint, signed interval violation, ladder
tick-distance, first-server range. No categorical coherence verdict, no tip, no edge. Structural
statuses only: HOLDOUT_SURFACE_AVAILABLE / HOLDOUT_SURFACE_UNAVAILABLE / ORIGIN_UNRESOLVED.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.holdout import (
    COMBINED_TOTAL_OVER,
    HANDICAP_A,
    HOLDOUT_SURFACE_AVAILABLE,
    HOLDOUT_SURFACE_UNAVAILABLE,
    ORIGIN_UNRESOLVED,
    HoldoutObservation,
    evaluate_holdout,
)
from sport_tennis.coherence.match import match_distribution
from sport_tennis.coherence.pmf import over_under
from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver import (
    IDENTIFIED,
    MULTIPLE_ROOTS,
    NO_ROOT,
    IdentificationResult,
    Root,
    ServerSolve,
)

_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS


def _result(status: str, roots: tuple[Root, ...]) -> IdentificationResult:
    per = (ServerSolve(True, status, roots), ServerSolve(False, NO_ROOT, ()))
    return IdentificationResult(status=status, roots=roots, per_server=per,
                                domain=(0.35, 0.90), line=Decimal("22.5"), fmt=_FMT)


def _identified(p_a: float, p_b: float) -> IdentificationResult:
    root = Root(p_a, p_b, True, 1e-7, 3.0, False)
    return _result(IDENTIFIED, (root,))


def _model_over(p_a: float, p_b: float, line: Decimal) -> float:
    md = match_distribution(p_a, p_b, _FMT, a_serves_first_match=True)
    return over_under(md.total_games_pmf, line).over


# ------------------------------------------------------------------ structural statuses
def test_origin_unresolved_when_identification_did_not_resolve() -> None:
    for res in (_result(NO_ROOT, ()), _result(MULTIPLE_ROOTS, ())):
        surf = evaluate_holdout(res, (HoldoutObservation(COMBINED_TOTAL_OVER,
                                                         Decimal("24.5"), 0.4, 0.42),))
        assert surf.status == ORIGIN_UNRESOLVED
        assert surf.metrics == ()


def test_surface_unavailable_when_no_observations() -> None:
    surf = evaluate_holdout(_identified(0.68, 0.57), ())
    assert surf.status == HOLDOUT_SURFACE_UNAVAILABLE
    assert surf.metrics == ()


def test_surface_available_with_metrics() -> None:
    line = Decimal("24.5")
    surf = evaluate_holdout(_identified(0.68, 0.57),
                            (HoldoutObservation(COMBINED_TOTAL_OVER, line, 0.30, 0.34),))
    assert surf.status == HOLDOUT_SURFACE_AVAILABLE
    m = surf.metrics[0]
    expected = _model_over(0.68, 0.57, line)
    assert m.model_implied_low == pytest.approx(expected, abs=1e-12)
    assert m.model_implied_high == pytest.approx(expected, abs=1e-12)
    assert m.first_server_range == pytest.approx(0.0, abs=1e-12)  # single root
    assert m.observed_midpoint == pytest.approx(0.32, abs=1e-12)
    assert m.tick_distance >= 0


# ------------------------------------------------------------------ raw metrics semantics
def test_interval_violation_sign_and_zero() -> None:
    line = Decimal("24.5")
    model = _model_over(0.68, 0.57, line)
    # interval strictly ABOVE the model point -> model sits below -> positive gap
    below = evaluate_holdout(_identified(0.68, 0.57),
                             (HoldoutObservation(COMBINED_TOTAL_OVER, line,
                                                 model + 0.10, model + 0.14),)).metrics[0]
    assert below.interval_violation > 0
    # interval strictly BELOW the model point -> model sits above -> negative gap
    above = evaluate_holdout(_identified(0.68, 0.57),
                             (HoldoutObservation(COMBINED_TOTAL_OVER, line,
                                                 model - 0.14, model - 0.10),)).metrics[0]
    assert above.interval_violation < 0
    # interval straddling the model point -> no violation
    inside = evaluate_holdout(_identified(0.68, 0.57),
                              (HoldoutObservation(COMBINED_TOTAL_OVER, line,
                                                  model - 0.05, model + 0.05),)).metrics[0]
    assert inside.interval_violation == 0.0


def test_first_server_range_spans_two_roots() -> None:
    line = Decimal("24.5")
    r1 = Root(0.68, 0.57, True, 1e-7, 3.0, False)
    r2 = Root(0.57, 0.68, False, 1e-7, 3.0, False)  # different serve assignment / params
    res = _result(IDENTIFIED, (r1, r2))
    surf = evaluate_holdout(res, (HoldoutObservation(COMBINED_TOTAL_OVER, line, 0.3, 0.34),))
    m = surf.metrics[0]
    assert m.model_implied_low <= m.model_implied_high
    assert m.first_server_range == pytest.approx(m.model_implied_high - m.model_implied_low,
                                                 abs=1e-12)


def test_handicap_market_type_projects_margin() -> None:
    surf = evaluate_holdout(_identified(0.70, 0.55),
                            (HoldoutObservation(HANDICAP_A, Decimal("-3.5"), 0.45, 0.49),))
    m = surf.metrics[0]
    assert 0.0 <= m.model_implied_low <= 1.0


def test_unknown_market_type_refused() -> None:
    with pytest.raises(CoherenceMathError):
        evaluate_holdout(_identified(0.68, 0.57),
                         (HoldoutObservation("SET_BETTING", Decimal("1.5"), 0.4, 0.5),))
