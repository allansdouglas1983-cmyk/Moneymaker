"""F-13 properties: the release predicate dominates every path (SPEC-054/071).

Along ANY legal lifecycle path: the market is reserved iff the surviving order is not
in a released condition, where released means (terminal-zero-fill: LAPSED/CANCELLED
with matched == 0 and not unknown) or the settlement horizon (SETTLED/RESETTLED/
VOIDED). Guard dominance: any matched stake means no pre-settlement release,
whatever else the path did.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l5_decision.execution import PersistenceType, Side
from l6_broker.orders import LEGAL_TRANSITIONS, OrderBook, OrderState, PlaceCommand

pytestmark = [pytest.mark.spec("SPEC-054"), pytest.mark.spec("SPEC-071")]

_AT = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
_STAKE = 400

_RELEASED_TERMINAL = {OrderState.LAPSED, OrderState.CANCELLED}
_SETTLEMENT_RELEASED = {OrderState.SETTLED, OrderState.RESETTLED, OrderState.VOIDED}


def _command() -> PlaceCommand:
    return PlaceCommand(
        customer_order_ref="prop-ref",
        market_id="1.999",
        selection_id=5,
        side=Side.BACK,
        price_tick=30,
        stake_minor=_STAKE,
        market_version=1,
        persistence=PersistenceType.LAPSE,
    )


def _matched_for(state: OrderState, current: int) -> int | None:
    if state is OrderState.PARTIALLY_MATCHED:
        return max(current, 1)
    if state is OrderState.MATCHED:
        return _STAKE
    return None


@given(path=st.lists(st.integers(min_value=0, max_value=7), min_size=0, max_size=12))
@settings(max_examples=250)
def test_reservation_tracks_the_release_predicate_along_any_legal_path(
    path: list[int],
) -> None:
    book = OrderBook()
    order = book.place(_command(), at_utc=_AT, monotonic_ns=1)
    for i, choice in enumerate(path):
        targets = sorted(LEGAL_TRANSITIONS[order.state], key=lambda s: s.value)
        if not targets:
            break
        to_state = targets[choice % len(targets)]
        order = order.transition(
            to_state,
            at_utc=_AT,
            monotonic_ns=1000 + i,
            reason="property walk",
            matched_stake_minor=_matched_for(to_state, order.matched_stake_minor),
        )
        book.update(order)

    zero_fill_release = (
        order.state in _RELEASED_TERMINAL
        and order.matched_stake_minor == 0
        and not order.unknown
    )
    settlement_release = order.state in _SETTLEMENT_RELEASED
    expected_released = zero_fill_release or settlement_release
    assert book.is_market_reserved("1.999") == (not expected_released)
    # Guard dominance: matched stake never releases before the settlement horizon.
    if order.matched_stake_minor > 0 and order.state not in _SETTLEMENT_RELEASED:
        assert book.is_market_reserved("1.999") is True
