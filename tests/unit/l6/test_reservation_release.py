"""F-13 (founder ruling, 2026-07-17): zero-fill FOK reservation release — full matrix.

A market reservation represents actual/potential exposure or unresolved order state.
A CONFIRMED TERMINAL full-size FOK attempt with ZERO matched stake, NO partial fill and
NO reconciliation ambiguity releases the reservation. Every other row of the founder's
matrix RETAINS it: any matched stake; partial fill; missing/non-terminal
acknowledgement; submission timeout; cancel/replace ambiguity; possible duplicate
exposure; conflicting broker/order-stream state; unresolved reconciliation; suspension
before terminal state is known.

Release is atomic-by-construction: reservation state is DERIVED from the immutable
order records (their append-only histories are the event log), never stored as separate
mutable state — so release and terminal-event persistence cannot diverge under a crash.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from l5_decision.execution import PersistenceType, Side
from l6_broker.orders import (
    MarketReservedError,
    Order,
    OrderBook,
    OrderState,
    PlaceCommand,
    PlacementBlockedError,
)

pytestmark = [pytest.mark.spec("SPEC-054"), pytest.mark.spec("SPEC-071")]

_AT = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)


def _command(ref: str, market_id: str = "1.777") -> PlaceCommand:
    return PlaceCommand(
        customer_order_ref=ref,
        market_id=market_id,
        selection_id=11,
        side=Side.BACK,
        price_tick=40,
        stake_minor=500,
        market_version=1,
        persistence=PersistenceType.LAPSE,
    )


def _walk(order: Order, *states: OrderState, matched: int = 0) -> Order:
    for i, to_state in enumerate(states):
        matched_target = None
        if to_state is OrderState.PARTIALLY_MATCHED:
            matched_target = max(matched, 1)
        elif to_state is OrderState.MATCHED:
            matched_target = order.stake_minor
        elif matched and to_state in (OrderState.LAPSED, OrderState.CANCELLED):
            matched_target = matched
        order = order.transition(
            to_state,
            at_utc=_AT,
            monotonic_ns=1000 + i,
            reason="matrix walk",
            matched_stake_minor=matched_target,
        )
    return order


def _book_with(ref: str, *states: OrderState, matched: int = 0) -> OrderBook:
    book = OrderBook()
    order = book.place(_command(ref), at_utc=_AT, monotonic_ns=1)
    if states:
        book.update(_walk(order, *states, matched=matched))
    return book


class TestReleaseRow:
    def test_confirmed_terminal_zero_fill_fok_lapse_releases(self) -> None:
        # The F-13 release row: SUBMITTED -> ACKNOWLEDGED -> EXECUTABLE -> LAPSED,
        # matched 0, not unknown — the reservation is gone and a NEW intent may reserve.
        book = _book_with(
            "ref-1",
            OrderState.SUBMITTED,
            OrderState.ACKNOWLEDGED,
            OrderState.EXECUTABLE,
            OrderState.LAPSED,
        )
        assert book.is_market_reserved("1.777") is False
        replacement = book.place(_command("ref-2"), at_utc=_AT, monotonic_ns=99)
        assert replacement.customer_order_ref == "ref-2"

    def test_confirmed_zero_fill_cancel_releases(self) -> None:
        book = _book_with(
            "ref-1",
            OrderState.SUBMITTED,
            OrderState.ACKNOWLEDGED,
            OrderState.EXECUTABLE,
            OrderState.CANCELLED,
        )
        assert book.is_market_reserved("1.777") is False


class TestRetainRows:
    @pytest.mark.parametrize(
        "states,matched",
        [
            # any matched stake, full fill: retained to the settlement horizon
            ((OrderState.SUBMITTED, OrderState.ACKNOWLEDGED, OrderState.EXECUTABLE, OrderState.MATCHED), 0),
            # partial fill then lapse: matched remainder retained
            (
                (
                    OrderState.SUBMITTED,
                    OrderState.ACKNOWLEDGED,
                    OrderState.EXECUTABLE,
                    OrderState.PARTIALLY_MATCHED,
                    OrderState.LAPSED,
                ),
                250,
            ),
            # missing / non-terminal acknowledgement
            ((OrderState.SUBMITTED,), 0),
            # submission timeout: still SUBMITTED, no terminal state observed
            ((OrderState.SUBMITTED,), 0),
            # suspension before terminal state is known: EXECUTABLE, market suspended
            ((OrderState.SUBMITTED, OrderState.ACKNOWLEDGED, OrderState.EXECUTABLE), 0),
        ],
    )
    def test_non_release_rows_retain(self, states: tuple[OrderState, ...], matched: int) -> None:
        book = _book_with("ref-1", *states, matched=matched)
        assert book.is_market_reserved("1.777") is True
        with pytest.raises(MarketReservedError):
            book.place(_command("ref-2"), at_utc=_AT, monotonic_ns=99)

    def test_reconciliation_ambiguity_retains_even_terminal_zero_fill(self) -> None:
        # cancel/replace ambiguity, conflicting stream state, unresolved reconciliation:
        # the unknown flag retains the reservation even on a LAPSED, zero-matched order,
        # and the global unknown-state block additionally refuses all placement.
        book = OrderBook()
        order = book.place(_command("ref-1"), at_utc=_AT, monotonic_ns=1)
        order = _walk(
            order,
            OrderState.SUBMITTED,
            OrderState.ACKNOWLEDGED,
            OrderState.EXECUTABLE,
            OrderState.LAPSED,
        )
        book.update(order.marked_unknown())
        assert book.is_market_reserved("1.777") is True
        with pytest.raises(PlacementBlockedError):
            book.place(_command("ref-2"), at_utc=_AT, monotonic_ns=99)

    def test_settlement_horizon_release_unchanged(self) -> None:
        # A matched order releases only at the settlement horizon, exactly as before.
        book = _book_with(
            "ref-1",
            OrderState.SUBMITTED,
            OrderState.ACKNOWLEDGED,
            OrderState.EXECUTABLE,
            OrderState.MATCHED,
            OrderState.SETTLED,
        )
        assert book.is_market_reserved("1.777") is False


class TestDerivedNotStored:
    def test_reservation_state_is_derived_from_immutable_order_records(self) -> None:
        # Atomicity: rebuild a fresh book from the surviving order records (the immutable
        # event log) — the reservation answer must be identical, with no separate
        # mutable reservation state to lose in a crash.
        book = _book_with(
            "ref-1",
            OrderState.SUBMITTED,
            OrderState.ACKNOWLEDGED,
            OrderState.EXECUTABLE,
            OrderState.LAPSED,
        )
        surviving = book.get("ref-1")
        assert surviving is not None
        rebuilt = OrderBook()
        rebuilt_order = rebuilt.place(_command("ref-1"), at_utc=_AT, monotonic_ns=1)
        assert rebuilt_order.state is OrderState.CREATED
        rebuilt.update(surviving)
        assert rebuilt.is_market_reserved("1.777") == book.is_market_reserved("1.777") == False  # noqa: E712


class TestMutationHardening:
    """Kills for the F-13-region orders.py survivors found by the scoped cosmic-ray runs."""

    def test_runtime_built_equal_market_id_is_still_reserved(self) -> None:
        # Kills Eq_Is on the market-id comparison: compile-time interning of test
        # literals masked it. A runtime-constructed equal string is a DIFFERENT object
        # and must still match — identity semantics here would report a reserved market
        # as free.
        book = _book_with("ref-1", OrderState.SUBMITTED)
        runtime_id = "".join(["1", ".", "7", "7", "7"])
        assert runtime_id is not "1.777"  # noqa: F632  # the point of the test
        assert book.is_market_reserved(runtime_id) is True
        with pytest.raises(MarketReservedError):
            book.place(_command("ref-2", market_id=runtime_id), at_utc=_AT, monotonic_ns=99)

    def test_same_length_field_mutation_without_transition_is_refused(self) -> None:
        # Kills Eq_Lt/Eq_LtE on the same-length branch guard: an order object whose
        # history is identical but whose FIELDS changed without a transition record is
        # conflicting stream state — refused, never absorbed.
        from dataclasses import replace

        from l6_broker.orders import StaleOrderUpdateError

        book = _book_with("ref-1", OrderState.SUBMITTED)
        stored = book.get("ref-1")
        assert stored is not None
        mutated = replace(stored, matched_stake_minor=stored.stake_minor)
        with pytest.raises(StaleOrderUpdateError):
            book.update(mutated)
        refreshed = book.get("ref-1")
        assert refreshed is not None and refreshed.matched_stake_minor == 0

    def test_diverged_history_is_refused_with_the_typed_error(self) -> None:
        # Kills NotEq_Lt/NotEq_Gt on the prefix check: a DIVERGED history (same or
        # longer, different past) must raise the typed StaleOrderUpdateError — under an
        # ordering mutant the unorderable TransitionRecord pair would raise TypeError
        # instead, which is not a refusal, it is a crash.
        from l6_broker.orders import StaleOrderUpdateError

        book = OrderBook()
        placed = book.place(_command("ref-1"), at_utc=_AT, monotonic_ns=1)
        book.update(placed.transition(OrderState.SUBMITTED, at_utc=_AT, monotonic_ns=2, reason="a"))
        diverged = placed.transition(OrderState.SUBMITTED, at_utc=_AT, monotonic_ns=3, reason="b")
        with pytest.raises(StaleOrderUpdateError):
            book.update(diverged)
        refreshed = book.get("ref-1")
        assert refreshed is not None and refreshed.history[-1].reason == "a"
