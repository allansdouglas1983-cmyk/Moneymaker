"""SPEC-053 property tests: the tick-index round-trip is exact and order-preserving.

`relevant_inputs`/`metamorphic_properties` are not declared for SPEC-053 (a structural
arithmetic ID), but exactness and monotonicity are naturally properties.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from l5_decision.ladder import LADDER, index_of, price_of

pytestmark = pytest.mark.spec("SPEC-053")

_INDEX = st.integers(min_value=0, max_value=len(LADDER) - 1)


@given(i=_INDEX)
def test_index_decimal_index_roundtrip_is_exact(i: int) -> None:
    assert index_of(price_of(i)) == i


@given(i=_INDEX)
def test_decimal_index_decimal_roundtrip_is_exact(i: int) -> None:
    p = price_of(i)
    assert price_of(index_of(p)) == p
    assert isinstance(p, Decimal)


@given(i=_INDEX, j=_INDEX)
def test_order_preserving(i: int, j: int) -> None:
    # index order and price order agree (strict ladder monotonicity).
    if i < j:
        assert price_of(i) < price_of(j)
    elif i > j:
        assert price_of(i) > price_of(j)
    else:
        assert price_of(i) == price_of(j)


@given(i=st.integers(min_value=0, max_value=len(LADDER) - 2))
def test_adjacent_indices_differ_by_a_positive_step(i: int) -> None:
    assert price_of(i + 1) > price_of(i)
