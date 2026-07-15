"""SPEC-052 properties: every taker-v1 order carries the policy; the no-remainder guard
dominates regardless of the other fields.
"""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from l5_decision.execution import (
    PersistenceType,
    Side,
    TakerV1Order,
    TimeInForce,
    taker_v1,
)

pytestmark = pytest.mark.spec("SPEC-052")

_STAKE = st.integers(min_value=1, max_value=1_000_000)
_TICK = st.integers(min_value=0, max_value=349)
_VERSION = st.integers(min_value=0, max_value=10_000_000)


@given(stake=_STAKE, tick=_TICK, version=_VERSION, selection=st.integers(min_value=1, max_value=1000))
def test_every_built_order_is_taker_v1(stake: int, tick: int, version: int, selection: int) -> None:
    o = taker_v1(
        market_id="1.100",
        selection_id=selection,
        stake_minor=stake,
        worst_acceptable_tick=tick,
        market_version=version,
    )
    assert o.time_in_force is TimeInForce.FILL_OR_KILL
    assert o.persistence_type is PersistenceType.LAPSE
    assert o.min_fill_size_minor == o.stake_minor == stake
    assert o.side is Side.BACK
    assert o.market_version == version  # marketVersion carried on every order


@given(stake=_STAKE, wrong_fill=_STAKE, tick=_TICK, version=_VERSION)
def test_min_fill_not_equal_stake_always_rejected(
    stake: int, wrong_fill: int, tick: int, version: int
) -> None:
    # minFillSize must equal the full stake; any other value (a partial that could rest, or an
    # over-fill) is refused regardless of the remaining fields.
    if wrong_fill == stake:
        wrong_fill = stake + 1
    with pytest.raises((ValueError, TypeError)):
        TakerV1Order(
            market_id="1.100",
            selection_id=11,
            side=Side.BACK,
            stake_minor=stake,
            min_fill_size_minor=wrong_fill,
            worst_acceptable_tick=tick,
            time_in_force=TimeInForce.FILL_OR_KILL,
            persistence_type=PersistenceType.LAPSE,
            market_version=version,
        )
