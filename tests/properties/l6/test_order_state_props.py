"""SPEC-070 properties: the transition table dominates every other field, history is
append-only, and matched stake is monotone (the declared metamorphic properties)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l5_decision.execution import PersistenceType, Side
from l6_broker.orders import (
    LEGAL_TRANSITIONS,
    IllegalTransitionError,
    Order,
    OrderState,
)

pytestmark = pytest.mark.spec("SPEC-070")

_STAKE = 200
_AT = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)


def _order() -> Order:
    return Order(
        order_id="ord-1",
        customer_order_ref="ref-1",
        market_id="1.23456",
        selection_id=111,
        side=Side.BACK,
        price_tick=50,
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


def _walk(order: Order, path: list[int]) -> Order:
    """Drive the order along LEGAL edges chosen by the Hypothesis-provided indices."""
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
    return order


@given(path=st.lists(st.integers(min_value=0, max_value=7), min_size=0, max_size=12))
@settings(max_examples=200)
def test_history_append_only_and_matched_monotone_along_any_legal_path(
    path: list[int],
) -> None:
    order = _order()
    seen_matched = order.matched_stake_minor
    seen_history = len(order.history)
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
        assert len(order.history) == seen_history + 1  # +1 per legal transition, never more
        seen_history = len(order.history)
        assert order.matched_stake_minor >= seen_matched  # monotone non-decreasing
        seen_matched = order.matched_stake_minor
        assert order.matched_stake_minor <= order.stake_minor


@given(
    path=st.lists(st.integers(min_value=0, max_value=7), min_size=0, max_size=12),
    target_index=st.integers(min_value=0, max_value=10),
    matched_noise=st.integers(min_value=0, max_value=_STAKE),
)
@settings(max_examples=200)
def test_illegal_transition_always_raises_regardless_of_other_fields(
    path: list[int], target_index: int, matched_noise: int
) -> None:
    # From ANY legally reachable state, attempting any NON-legal target raises,
    # regardless of the matched_stake_minor supplied (guard dominance, moneycritical.md).
    order = _walk(_order(), path)
    all_states = sorted(OrderState, key=lambda s: s.value)
    illegal = [s for s in all_states if s not in LEGAL_TRANSITIONS[order.state]]
    if not illegal:
        return  # every state is reachable from here; nothing illegal to attempt
    to_state = illegal[target_index % len(illegal)]
    with pytest.raises(IllegalTransitionError):
        order.transition(
            to_state,
            at_utc=_AT,
            monotonic_ns=99_999,
            reason="illegal attempt",
            matched_stake_minor=matched_noise,
        )
