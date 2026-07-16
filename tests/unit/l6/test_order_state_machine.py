"""Order state machine (SPEC-070): exhaustive illegal-transition matrix, matched-amount
invariants, immutability, and the taker-v1 partial-fill incident flag.

RED by construction: ``l6_broker`` does not exist yet in the repo (Phase 3A OFFLINE
construction, ADR 0014). These tests import ``l6_broker.orders`` and are expected to fail
with ``ModuleNotFoundError`` until the implementation lands.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from l5_decision.execution import PersistenceType, Side
from l6_broker.orders import (
    LEGAL_TRANSITIONS,
    IllegalTransitionError,
    Order,
    OrderState,
    TransitionRecord,
)

pytestmark = pytest.mark.spec("SPEC-070")

_ALL_STATES = tuple(OrderState)
_NOW = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
_STAKE = 10_000


def _order(*, state: OrderState = OrderState.CREATED, matched: int = 0, stake: int = _STAKE) -> Order:
    return Order(
        order_id="ord-1",
        customer_order_ref="ref-1",
        market_id="1.23456",
        selection_id=111,
        side=Side.BACK,
        price_tick=50,
        stake_minor=stake,
        market_version=1,
        persistence=PersistenceType.LAPSE,
        state=state,
        matched_stake_minor=matched,
    )


def _matched_resident_in(state: OrderState, stake: int) -> int:
    """The matched amount an order genuinely at ``state`` would carry, respecting the
    PARTIALLY_MATCHED/MATCHED invariants; 0 for every other state."""
    if state is OrderState.PARTIALLY_MATCHED:
        return stake // 2
    if state is OrderState.MATCHED:
        return stake
    return 0


def _matched_target_for(to_state: OrderState, stake: int) -> int | None:
    """The ``matched_stake_minor`` to request when transitioning TO ``to_state``; ``None``
    means "leave unchanged", which is the only sane default for states with no matched
    invariant of their own."""
    if to_state is OrderState.PARTIALLY_MATCHED:
        return stake // 2
    if to_state is OrderState.MATCHED:
        return stake
    return None


# ---------------------------------------------------------------------------
# SPEC-070: exhaustive matrix over ALL (from_state, to_state) pairs.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("from_state", _ALL_STATES, ids=lambda s: s.name)
@pytest.mark.parametrize("to_state", _ALL_STATES, ids=lambda s: s.name)
def test_exhaustive_transition_matrix(from_state: OrderState, to_state: OrderState) -> None:
    legal_targets = LEGAL_TRANSITIONS.get(from_state, frozenset())
    starting = _order(state=from_state, matched=_matched_resident_in(from_state, _STAKE))
    target_matched = _matched_target_for(to_state, _STAKE)

    if to_state in legal_targets:
        updated = starting.transition(
            to_state, at_utc=_NOW, monotonic_ns=1, reason="matrix", matched_stake_minor=target_matched
        )
        assert updated.state is to_state
        assert len(updated.history) == len(starting.history) + 1
        last = updated.history[-1]
        assert last.from_state is from_state
        assert last.to_state is to_state
        # the prior instance is untouched -- Order is immutable.
        assert starting.state is from_state
        assert starting.history == ()
    else:
        with pytest.raises(IllegalTransitionError) as excinfo:
            starting.transition(
                to_state, at_utc=_NOW, monotonic_ns=1, reason="matrix", matched_stake_minor=target_matched
            )
        message = str(excinfo.value)
        assert from_state.name in message
        assert to_state.name in message
        # a rejected attempt must not mutate the starting order at all.
        assert starting.state is from_state
        assert starting.history == ()


def test_legal_transitions_table_matches_spec_text() -> None:
    # SPEC-070's literal chain, reproduced as an independent check on the table shape.
    assert LEGAL_TRANSITIONS[OrderState.CREATED] == frozenset({OrderState.SUBMITTED})
    assert LEGAL_TRANSITIONS[OrderState.SUBMITTED] == frozenset({OrderState.ACKNOWLEDGED, OrderState.LAPSED})
    assert LEGAL_TRANSITIONS[OrderState.ACKNOWLEDGED] == frozenset(
        {OrderState.EXECUTABLE, OrderState.LAPSED, OrderState.VOIDED}
    )
    assert LEGAL_TRANSITIONS[OrderState.EXECUTABLE] == frozenset(
        {
            OrderState.PARTIALLY_MATCHED,
            OrderState.MATCHED,
            OrderState.CANCELLED,
            OrderState.LAPSED,
            OrderState.VOIDED,
        }
    )
    assert LEGAL_TRANSITIONS[OrderState.PARTIALLY_MATCHED] == frozenset(
        {OrderState.MATCHED, OrderState.CANCELLED, OrderState.LAPSED, OrderState.VOIDED}
    )
    assert LEGAL_TRANSITIONS[OrderState.MATCHED] == frozenset({OrderState.SETTLED})
    assert LEGAL_TRANSITIONS[OrderState.CANCELLED] == frozenset({OrderState.SETTLED})
    assert LEGAL_TRANSITIONS[OrderState.LAPSED] == frozenset({OrderState.SETTLED})
    assert LEGAL_TRANSITIONS[OrderState.VOIDED] == frozenset({OrderState.SETTLED})
    assert LEGAL_TRANSITIONS[OrderState.SETTLED] == frozenset({OrderState.RESETTLED})
    assert LEGAL_TRANSITIONS[OrderState.RESETTLED] == frozenset({OrderState.RESETTLED})


def test_settled_is_absorbing_except_resettled() -> None:
    for to_state in _ALL_STATES:
        if to_state is OrderState.RESETTLED:
            continue
        assert to_state not in LEGAL_TRANSITIONS[OrderState.SETTLED]


def test_resettled_is_a_pure_self_loop() -> None:
    assert LEGAL_TRANSITIONS[OrderState.RESETTLED] == frozenset({OrderState.RESETTLED})


# ---------------------------------------------------------------------------
# Matched-amount invariants.
# ---------------------------------------------------------------------------


def test_partially_matched_requires_matched_strictly_between_zero_and_stake() -> None:
    with pytest.raises(ValueError):
        _order(state=OrderState.PARTIALLY_MATCHED, matched=0)
    with pytest.raises(ValueError):
        _order(state=OrderState.PARTIALLY_MATCHED, matched=_STAKE)
    _order(state=OrderState.PARTIALLY_MATCHED, matched=1)  # does not raise


def test_matched_requires_matched_equals_stake() -> None:
    with pytest.raises(ValueError):
        _order(state=OrderState.MATCHED, matched=_STAKE - 1)
    _order(state=OrderState.MATCHED, matched=_STAKE)  # does not raise


def test_matched_cannot_exceed_stake_at_construction() -> None:
    with pytest.raises(ValueError):
        _order(matched=_STAKE + 1)


def test_matched_stake_minor_must_be_non_negative() -> None:
    with pytest.raises(ValueError):
        _order(matched=-1)


def test_transition_rejects_a_matched_decrease() -> None:
    order = _order(state=OrderState.EXECUTABLE, matched=0).transition(
        OrderState.PARTIALLY_MATCHED, at_utc=_NOW, monotonic_ns=1, reason="partial", matched_stake_minor=5_000
    )
    with pytest.raises(ValueError):
        order.transition(
            OrderState.CANCELLED, at_utc=_NOW, monotonic_ns=2, reason="oops", matched_stake_minor=1_000
        )


def test_cancel_after_partial_match_preserves_matched_portion() -> None:
    # "A lapse after partial match leaves the matched portion standing" -- CANCELLED here,
    # LAPSED covered in test_lapse_after_partial_match_preserves_matched_portion.
    partial = _order(state=OrderState.EXECUTABLE, matched=0).transition(
        OrderState.PARTIALLY_MATCHED, at_utc=_NOW, monotonic_ns=1, reason="partial", matched_stake_minor=4_000
    )
    cancelled = partial.transition(OrderState.CANCELLED, at_utc=_NOW, monotonic_ns=2, reason="cancel")
    assert cancelled.matched_stake_minor == 4_000


def test_lapse_after_partial_match_preserves_matched_portion() -> None:
    partial = _order(state=OrderState.EXECUTABLE, matched=0).transition(
        OrderState.PARTIALLY_MATCHED, at_utc=_NOW, monotonic_ns=1, reason="partial", matched_stake_minor=3_000
    )
    lapsed = partial.transition(OrderState.LAPSED, at_utc=_NOW, monotonic_ns=2, reason="lapse")
    assert lapsed.matched_stake_minor == 3_000


def test_transition_rejects_non_int_matched() -> None:
    order = _order(state=OrderState.EXECUTABLE)
    with pytest.raises(TypeError):
        order.transition(
            OrderState.PARTIALLY_MATCHED,
            at_utc=_NOW,
            monotonic_ns=1,
            reason="bad",
            matched_stake_minor=5_000.0,  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Construction-time hard prohibitions and money-type discipline.
# ---------------------------------------------------------------------------


def test_lay_side_refused_at_construction() -> None:
    with pytest.raises(ValueError):
        Order(
            order_id="ord-1",
            customer_order_ref="ref-1",
            market_id="1.23456",
            selection_id=111,
            side=Side.LAY,
            price_tick=50,
            stake_minor=_STAKE,
            market_version=1,
            persistence=PersistenceType.LAPSE,
        )


@pytest.mark.parametrize("persistence", [PersistenceType.PERSIST, PersistenceType.MARKET_ON_CLOSE])
def test_non_lapse_persistence_refused(persistence: PersistenceType) -> None:
    with pytest.raises(ValueError):
        Order(
            order_id="ord-1",
            customer_order_ref="ref-1",
            market_id="1.23456",
            selection_id=111,
            side=Side.BACK,
            price_tick=50,
            stake_minor=_STAKE,
            market_version=1,
            persistence=persistence,
        )


@pytest.mark.parametrize("bad_stake", [100.5, Decimal("100"), True])
def test_float_decimal_bool_stake_refused_typeerror(bad_stake: object) -> None:
    with pytest.raises(TypeError):
        Order(
            order_id="ord-1",
            customer_order_ref="ref-1",
            market_id="1.23456",
            selection_id=111,
            side=Side.BACK,
            price_tick=50,
            stake_minor=bad_stake,  # type: ignore[arg-type]
            market_version=1,
            persistence=PersistenceType.LAPSE,
        )


@pytest.mark.parametrize("bad_stake", [0, -1])
def test_non_positive_stake_refused_valueerror(bad_stake: int) -> None:
    with pytest.raises(ValueError):
        _order(stake=bad_stake)


@pytest.mark.parametrize("bad_tick", [-1, 999_999])
def test_invalid_price_tick_refused(bad_tick: int) -> None:
    with pytest.raises(ValueError):
        Order(
            order_id="ord-1",
            customer_order_ref="ref-1",
            market_id="1.23456",
            selection_id=111,
            side=Side.BACK,
            price_tick=bad_tick,
            stake_minor=_STAKE,
            market_version=1,
            persistence=PersistenceType.LAPSE,
        )


@pytest.mark.parametrize("bad_selection", [0, -1])
def test_non_positive_selection_id_refused(bad_selection: int) -> None:
    with pytest.raises(ValueError):
        Order(
            order_id="ord-1",
            customer_order_ref="ref-1",
            market_id="1.23456",
            selection_id=bad_selection,
            side=Side.BACK,
            price_tick=50,
            stake_minor=_STAKE,
            market_version=1,
            persistence=PersistenceType.LAPSE,
        )


@pytest.mark.parametrize("bad_version", [0, -1])
def test_non_positive_market_version_refused(bad_version: int) -> None:
    with pytest.raises(ValueError):
        Order(
            order_id="ord-1",
            customer_order_ref="ref-1",
            market_id="1.23456",
            selection_id=111,
            side=Side.BACK,
            price_tick=50,
            stake_minor=_STAKE,
            market_version=bad_version,
            persistence=PersistenceType.LAPSE,
        )


def test_empty_customer_order_ref_refused() -> None:
    with pytest.raises(ValueError):
        Order(
            order_id="ord-1",
            customer_order_ref="",
            market_id="1.23456",
            selection_id=111,
            side=Side.BACK,
            price_tick=50,
            stake_minor=_STAKE,
            market_version=1,
            persistence=PersistenceType.LAPSE,
        )


# ---------------------------------------------------------------------------
# taker-v1 partial-fill incident flag and the unknown-state hook.
# ---------------------------------------------------------------------------


def test_partially_matched_is_flagged_a_taker_v1_incident() -> None:
    order = _order(state=OrderState.PARTIALLY_MATCHED, matched=1)
    assert order.is_taker_v1_incident() is True


@pytest.mark.parametrize("state", [s for s in _ALL_STATES if s is not OrderState.PARTIALLY_MATCHED])
def test_only_partially_matched_is_a_taker_v1_incident(state: OrderState) -> None:
    order = _order(state=state, matched=_matched_resident_in(state, _STAKE))
    assert order.is_taker_v1_incident() is False


def test_marked_unknown_preserves_state_and_history() -> None:
    order = _order(state=OrderState.EXECUTABLE)
    unknown_order = order.marked_unknown()
    assert unknown_order.unknown is True
    assert unknown_order.state is order.state
    assert unknown_order.history == order.history
    assert order.unknown is False  # the original is untouched


# ---------------------------------------------------------------------------
# TransitionRecord dual-clock discipline (SPEC-004).
# ---------------------------------------------------------------------------


def test_transition_record_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        TransitionRecord(
            from_state=OrderState.CREATED,
            to_state=OrderState.SUBMITTED,
            at_utc=datetime(2026, 7, 16, 12, 0, 0),  # naive
            monotonic_ns=1,
            reason="x",
        )


def test_transition_record_rejects_non_utc_offset() -> None:
    non_utc = timezone(timedelta(hours=1))
    with pytest.raises(ValueError):
        TransitionRecord(
            from_state=OrderState.CREATED,
            to_state=OrderState.SUBMITTED,
            at_utc=datetime(2026, 7, 16, 12, 0, 0, tzinfo=non_utc),
            monotonic_ns=1,
            reason="x",
        )


def test_transition_record_rejects_empty_reason() -> None:
    with pytest.raises(ValueError):
        TransitionRecord(
            from_state=OrderState.CREATED, to_state=OrderState.SUBMITTED, at_utc=_NOW, monotonic_ns=1, reason=""
        )


@pytest.mark.parametrize("bad_monotonic", [1.5, True])
def test_transition_record_rejects_non_int_monotonic(bad_monotonic: object) -> None:
    with pytest.raises(TypeError):
        TransitionRecord(
            from_state=OrderState.CREATED,
            to_state=OrderState.SUBMITTED,
            at_utc=_NOW,
            monotonic_ns=bad_monotonic,  # type: ignore[arg-type]
            reason="x",
        )
