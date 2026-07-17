"""F-13 stateful test: reservation invariant under arbitrary interleavings (SPEC-054/071).

Random walks of place / transition / unknown-marking / stale-update attempts on one
market. Invariants after every step: the market is reserved iff some order on it is in
a retained condition; a placement succeeds iff the market is unreserved and no order is
unknown; a stale (out-of-order) broker update is always refused and never regresses the
book.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from l5_decision.execution import PersistenceType, Side
from l6_broker.orders import (
    LEGAL_TRANSITIONS,
    MarketReservedError,
    Order,
    OrderBook,
    OrderState,
    PlaceCommand,
    StaleOrderUpdateError,
    UnknownOrderStateError,
)

pytestmark = [pytest.mark.spec("SPEC-054"), pytest.mark.spec("SPEC-071")]

_AT = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
_MARKET = "1.555"
_STAKE = 300

_RELEASED_TERMINAL = {OrderState.LAPSED, OrderState.CANCELLED}
_SETTLEMENT_RELEASED = {OrderState.SETTLED, OrderState.RESETTLED, OrderState.VOIDED}


def _released(order: Order) -> bool:
    if order.state in _SETTLEMENT_RELEASED:
        return True
    return order.state in _RELEASED_TERMINAL and order.matched_stake_minor == 0 and not order.unknown


class ReservationMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.book = OrderBook()
        self.counter = 0
        self.tick = 0
        self.snapshots: dict[str, list[Order]] = {}

    def _next_ref(self) -> str:
        self.counter += 1
        return f"sm-ref-{self.counter}"

    def _command(self, ref: str) -> PlaceCommand:
        return PlaceCommand(
            customer_order_ref=ref,
            market_id=_MARKET,
            selection_id=3,
            side=Side.BACK,
            price_tick=25,
            stake_minor=_STAKE,
            market_version=1,
            persistence=PersistenceType.LAPSE,
        )

    @rule()
    def place_new_intent(self) -> None:
        any_unknown = any(o.unknown for o in self.book.orders())
        reserved = self.book.is_market_reserved(_MARKET)
        ref = self._next_ref()
        try:
            placed = self.book.place(self._command(ref), at_utc=_AT, monotonic_ns=self.counter)
            self.snapshots[ref] = [placed]
            assert not reserved and not any_unknown
        except UnknownOrderStateError:
            assert any_unknown
        except MarketReservedError:
            assert reserved

    @rule(choice=st.integers(min_value=0, max_value=7))
    def advance_some_order(self, choice: int) -> None:
        orders = [o for o in self.book.orders() if LEGAL_TRANSITIONS[o.state] and not o.unknown]
        if not orders:
            return
        order = orders[choice % len(orders)]
        targets = sorted(LEGAL_TRANSITIONS[order.state], key=lambda s: s.value)
        to_state = targets[choice % len(targets)]
        matched = None
        if to_state is OrderState.PARTIALLY_MATCHED:
            matched = max(order.matched_stake_minor, 1)
        elif to_state is OrderState.MATCHED:
            matched = order.stake_minor
        self.tick += 1
        advanced = order.transition(
            to_state,
            at_utc=_AT,
            monotonic_ns=10_000 + self.tick,
            reason="stateful walk",
            matched_stake_minor=matched,
        )
        self.book.update(advanced)
        self.snapshots.setdefault(order.customer_order_ref, []).append(advanced)

    @rule(choice=st.integers(min_value=0, max_value=7))
    def replay_stale_update(self, choice: int) -> None:
        # An out-of-order / duplicate broker event: re-sending an EARLIER order
        # snapshot must be refused (stale) or be an idempotent no-op (identical),
        # and must never regress the stored order.
        refs = list(self.snapshots)
        if not refs:
            return
        ref = refs[choice % len(refs)]
        history = self.snapshots[ref]
        stale = history[choice % len(history)]
        stored = self.book.get(ref)
        assert stored is not None
        stored_history_len = len(stored.history)
        try:
            self.book.update(stale)
            assert len(stale.history) == stored_history_len  # identical -> no-op
        except StaleOrderUpdateError:
            assert len(stale.history) < stored_history_len
        refreshed = self.book.get(ref)
        assert refreshed is not None
        assert len(refreshed.history) >= stored_history_len

    @rule(choice=st.integers(min_value=0, max_value=7))
    def mark_some_order_unknown(self, choice: int) -> None:
        orders = [o for o in self.book.orders() if not o.unknown]
        if not orders:
            return
        order = orders[choice % len(orders)]
        flagged = order.marked_unknown()
        self.book.update(flagged)
        self.snapshots.setdefault(order.customer_order_ref, []).append(flagged)

    @invariant()
    def reservation_matches_predicate(self) -> None:
        expected = any(not _released(o) for o in self.book.orders() if o.market_id == _MARKET)
        assert self.book.is_market_reserved(_MARKET) == expected


ReservationStatefulTest = ReservationMachine.TestCase
ReservationStatefulTest.settings = hyp_settings(max_examples=40, stateful_step_count=30)
