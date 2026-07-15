"""SPEC-050 metamorphic properties (declared in the manifest).

relevant_inputs: win_probability, odds_exec, commission_rate
metamorphic_properties:
  - increasing win_probability at fixed odds must not decrease EV
  - increasing commission_rate must not increase EV
  - p_close must never reach this function
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from l5_decision.ev import CommissionRate, WinProbabilityLowerBound, expected_value
from l5_decision.ladder import LADDER
from l5_decision.prices import ClosePrice, OddsExec

pytestmark = pytest.mark.spec("SPEC-050")

# Exact Decimal domains — never float.
_PROB = st.integers(min_value=0, max_value=100).map(lambda n: Decimal(n) / Decimal(100))
_COMM = st.integers(min_value=0, max_value=99).map(lambda n: Decimal(n) / Decimal(100))
_TICK = st.integers(min_value=0, max_value=len(LADDER) - 1)


@given(p1=_PROB, p2=_PROB, tick=_TICK, comm=_COMM)
def test_ev_non_decreasing_in_probability(p1: Decimal, p2: Decimal, tick: int, comm: Decimal) -> None:
    odds = OddsExec(tick_index=tick)
    c = CommissionRate(rate=comm)
    lo, hi = sorted((p1, p2))
    ev_lo = expected_value(WinProbabilityLowerBound(value=lo), odds, c)
    ev_hi = expected_value(WinProbabilityLowerBound(value=hi), odds, c)
    assert ev_hi >= ev_lo


@given(prob=_PROB, tick=_TICK, c1=_COMM, c2=_COMM)
def test_ev_non_increasing_in_commission(prob: Decimal, tick: int, c1: Decimal, c2: Decimal) -> None:
    odds = OddsExec(tick_index=tick)
    p = WinProbabilityLowerBound(value=prob)
    lo, hi = sorted((c1, c2))
    ev_lo_comm = expected_value(p, odds, CommissionRate(rate=lo))
    ev_hi_comm = expected_value(p, odds, CommissionRate(rate=hi))
    assert ev_hi_comm <= ev_lo_comm


@given(prob=_PROB, tick=_TICK, comm=_COMM)
def test_p_close_never_reaches_ev(prob: Decimal, tick: int, comm: Decimal) -> None:
    with pytest.raises(TypeError):
        expected_value(
            WinProbabilityLowerBound(value=prob),
            ClosePrice(tick_index=tick),  # type: ignore[arg-type]
            CommissionRate(rate=comm),
        )


@given(prob=_PROB, comm=_COMM)
def test_ev_matches_closed_form(prob: Decimal, comm: Decimal) -> None:
    odds = OddsExec.from_decimal(Decimal("4"))
    ev = expected_value(WinProbabilityLowerBound(value=prob), odds, CommissionRate(rate=comm))
    o = Decimal("4")
    assert ev == prob * (o - 1) * (1 - comm) - (1 - prob)
