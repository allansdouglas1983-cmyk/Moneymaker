"""SPEC-051 property: the three price types are never interchangeable and preserve value.

A structural/guard ID (no declared relevant_inputs/metamorphic_properties), but non-conflation
and value preservation are naturally properties over the tick domain.
"""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from l5_decision.ladder import LADDER, price_of
from l5_decision.prices import ClosePrice, OddsExec

pytestmark = pytest.mark.spec("SPEC-051")

_INDEX = st.integers(min_value=0, max_value=len(LADDER) - 1)


@given(i=_INDEX)
def test_odds_exec_preserves_ladder_price(i: int) -> None:
    assert OddsExec(tick_index=i).decimal_odds == price_of(i)


@given(i=_INDEX)
def test_odds_exec_and_close_price_never_equal(i: int) -> None:
    # Same underlying tick, but distinct types must not compare equal — that is the whole
    # point of keeping the three prices unconflated. object-typed so the runtime inequality is
    # asserted even though mypy already proves the types are non-overlapping.
    a: object = OddsExec(tick_index=i)
    b: object = ClosePrice(tick_index=i)
    assert a != b
    assert not isinstance(OddsExec(tick_index=i), ClosePrice)
