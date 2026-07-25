"""STAGE3-0006 §4/§7/§12 — pin the holdout diagnostic arithmetic (kill, don't hand-wave).

The prior holdout mutation run left the raw-metric helpers (`_nearest_tick_index`,
`_tick_distance`, `_interval_violation`, `_model_prob_at`) and the metric assembly in
``evaluate_holdout`` almost entirely unpinned — the suite asserted statuses and structure but never
the metric VALUES, so every arithmetic/comparison mutant in those pure helpers survived. These are
behavioural, not equivalent: this module pins the exact values and the exact refusal boundaries so
each mutant is killed. Nothing here is a threshold or a coherence verdict — the metrics stay raw
diagnostics.
"""
from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest

from sport_tennis.coherence import holdout as H
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver import (IDENTIFIED, IdentificationResult, Root,
                                           ServerSolve)

_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS


# ----------------------------------------------------------------- _nearest_tick_index
@pytest.mark.parametrize("odds,idx", [
    ("1.01", 0), ("1.50", 49), ("2.00", 99), ("3.00", 149), ("6.00", 189), ("1000", 349),
])
def test_nearest_tick_index_exact(odds: str, idx: int) -> None:
    # exact index pins kill the abs(price-odds) Sub mutants, the `d < best_d` comparison mutants,
    # and the ZeroIterationForLoop mutant (which would return the initial 0 for every odds).
    assert H._nearest_tick_index(Decimal(odds)) == idx


def test_nearest_tick_index_tie_resolves_to_lower() -> None:
    # 1.015 is equidistant from tick 0 (1.01) and tick 1 (1.02); strict `<` keeps the earlier index.
    # A `<`->`<=` mutant would take the later index (1); a `<`->`>`/`>=` would take the farthest.
    assert H._nearest_tick_index(Decimal("1.015")) == 0
    assert H._nearest_tick_index(Decimal("1.02")) == 1


# ----------------------------------------------------------------- _tick_distance
def test_tick_distance_exact() -> None:
    # exact tick gaps kill the index subtraction (L111) and the 1/p odds division (L109/L110) mutants.
    assert H._tick_distance(0.5, 0.4) == 25
    assert H._tick_distance(0.25, 0.8) == 145
    assert H._tick_distance(0.5, 0.5) == 0


@pytest.mark.parametrize("model_mid,observed_mid", [
    (0.0, 0.5), (1.0, 0.5), (0.5, 0.0), (0.5, 1.0), (-0.1, 0.5), (0.5, 1.1),
    (0.5, -0.1), (0.5, 2.0), (-0.2, 0.5), (2.0, 0.5),  # negative/over-1 on BOTH sides kill the
])                                                     # chained-comparison `<`->`!=` mutants
def test_tick_distance_refuses_out_of_range(model_mid: float, observed_mid: float) -> None:
    # the (0,1) guard: each boundary/out-of-range probe kills a distinct bound-comparison mutant
    # (Lt->LtE/Eq/NotEq/Gt/GtE, the 0.0/1.0 NumberReplacer variants) and the `and`->`or` mutant
    # (which stops refusing when only one side is invalid).
    with pytest.raises(CoherenceMathError):
        H._tick_distance(model_mid, observed_mid)


# ----------------------------------------------------------------- _interval_violation
def test_interval_violation_below_interval() -> None:
    # model range entirely BELOW the observed interval: positive gap obs_lo - hi.
    assert H._interval_violation(0.30, 0.40, 0.60, 0.70) == pytest.approx(0.20, abs=1e-9)


def test_interval_violation_above_interval() -> None:
    # model range entirely ABOVE: negative gap obs_hi - lo.
    assert H._interval_violation(0.60, 0.70, 0.30, 0.40) == pytest.approx(-0.20, abs=1e-9)


def test_interval_violation_intersecting_is_zero() -> None:
    assert H._interval_violation(0.40, 0.60, 0.50, 0.55) == 0.0


def test_interval_violation_far_below_distinguishes_sub_from_mod() -> None:
    # obs_lo (0.9) >= 2*hi (0.4): obs_lo - hi = 0.5 but obs_lo % hi = 0.1, so this input
    # distinguishes the `obs_lo - hi` subtraction from a Sub->Mod mutant (the earlier
    # below-interval case 0.6/0.4 collides because 0.6-0.4 == 0.6%0.4).
    assert H._interval_violation(0.10, 0.40, 0.90, 0.95) == pytest.approx(0.50, abs=1e-9)


def test_interval_violation_reversed_back_lay_orders_observed() -> None:
    # back > lay must be sorted to (obs_lo, obs_hi) = (lay, back). A `<=`->`!=`/`is not` mutant on
    # the ordering picks the wrong tuple and returns 0.30 instead of 0.20 here.
    assert H._interval_violation(0.30, 0.40, 0.70, 0.60) == pytest.approx(0.20, abs=1e-9)


# ----------------------------------------------------------------- _model_prob_at routing
def test_model_prob_at_routes_handicap_to_a_covers_not_over() -> None:
    # market_type ∈ {COMBINED_TOTAL_OVER, HANDICAP_A}. COMBINED_TOTAL_OVER is the lexicographic
    # MINIMUM, so `market_type == COMBINED_TOTAL_OVER` mutated to `>=` matches BOTH and would route a
    # HANDICAP observation into the Over path. Pin the handicap value so that misroute is killed.
    root = Root(0.63, 0.57, True, 0.0, 1.0, False)
    over = H.HoldoutObservation("COMBINED_TOTAL_OVER", Decimal("22.5"), 0.5, 0.5)
    hcap = H.HoldoutObservation("HANDICAP_A", Decimal("-2.5"), 0.5, 0.5)
    assert H._model_prob_at(root, over, _FMT) == pytest.approx(0.4952207629577335, abs=1e-9)
    assert H._model_prob_at(root, hcap, _FMT) == pytest.approx(0.6828062975402316, abs=1e-9)
    # the misrouted Over(-2.5) would be 1.0 (all totals exceed -2.5); the true a_covers is not 1.0.
    assert H._model_prob_at(root, hcap, _FMT) != pytest.approx(1.0, abs=1e-6)


# ----------------------------------------------------------------- evaluate_holdout assembly
def _ident(*roots: Root) -> IdentificationResult:
    # per_server is deliberately empty: evaluate_holdout must not consult it. The cast keeps
    # the runtime value exactly () while satisfying the declared pair type.
    empty = cast("tuple[ServerSolve, ServerSolve]", ())
    return IdentificationResult(status=IDENTIFIED, roots=tuple(roots), per_server=empty,
                                domain=(0.35, 0.90), line=Decimal("22.5"), fmt=_FMT)


def test_evaluate_holdout_metric_values_pinned() -> None:
    # two distinct roots -> a non-degenerate first-server range and a mid used by tick_distance,
    # pinning the (low+high)/2 midpoint (L145), the high-low range (L152) and the per-line metrics.
    ident = _ident(Root(0.63, 0.57, True, 0.0, 1.0, False),
                   Root(0.70, 0.55, True, 0.0, 1.0, False))
    over = H.HoldoutObservation("COMBINED_TOTAL_OVER", Decimal("22.5"), 0.5, 0.5)
    hcap = H.HoldoutObservation("HANDICAP_A", Decimal("-2.5"), 0.5, 0.5)
    surf = H.evaluate_holdout(ident, (over, hcap))
    assert surf.status == H.HOLDOUT_SURFACE_AVAILABLE
    m_over, m_hcap = surf.metrics
    # range is exactly high - low (kills the Sub->Mod mutant on L152).
    assert m_over.first_server_range == pytest.approx(m_over.model_implied_high
                                                      - m_over.model_implied_low, abs=1e-12)
    assert m_over.first_server_range == pytest.approx(0.263264, abs=1e-6)
    assert m_hcap.first_server_range == pytest.approx(0.256309, abs=1e-6)
    # tick_distance depends on the midpoint (kills the (low+high)/2 mutants on L145).
    assert m_over.tick_distance == 38
    assert m_hcap.tick_distance == 77
    assert m_over.interval_violation == pytest.approx(0.004779, abs=1e-6)
    assert m_hcap.interval_violation == pytest.approx(-0.182806, abs=1e-6)


def test_evaluate_holdout_valid_status_but_no_roots_is_unresolved() -> None:
    # status is projectable (IDENTIFIED) but roots is empty -> ORIGIN_UNRESOLVED. The guard is
    # `status not in _ORIGIN_STATUSES OR not roots`; an `or`->`and` mutant would fall through to
    # min([]) on an empty projection and crash instead of returning the status.
    over = H.HoldoutObservation("COMBINED_TOTAL_OVER", Decimal("22.5"), 0.5, 0.5)
    surf = H.evaluate_holdout(_ident(), (over,))
    assert surf.status == H.ORIGIN_UNRESOLVED
    assert surf.metrics == ()
