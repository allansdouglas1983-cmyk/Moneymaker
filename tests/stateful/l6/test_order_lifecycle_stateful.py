"""Stateful (model-based) test for the order lifecycle state machine (SPEC-070).

Required by the spec text itself ("Stateful model-based test required"). Drives a long
random walk of legal and illegal transition attempts against a single ``Order`` and
checks the invariants ``LEGAL_TRANSITIONS`` is supposed to guarantee: an illegal attempt
always raises and never mutates anything; a legal attempt always grows history by
exactly one entry; ``matched_stake_minor`` never decreases; and ``SETTLED``/``RESETTLED``
behave as the absorbing states the table says they are. RED by construction:
``l6_broker`` does not exist yet.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from hypothesis import settings as hyp_settings

from l5_decision.execution import PersistenceType, Side
from l6_broker.orders import IllegalTransitionError, LEGAL_TRANSITIONS, Order, OrderState

pytestmark = pytest.mark.spec("SPEC-070")

_STAKE = 10_000
_BASE_TIME = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)


def _matched_target_for(to_state: OrderState, stake: int, current_matched: int) -> int | None:
    if to_state is OrderState.PARTIALLY_MATCHED:
        # only ever attempted (legally) from a state with matched == 0 -- see the DAG
        # shape of LEGAL_TRANSITIONS, which never re-enters PARTIALLY_MATCHED.
        return max(current_matched, 1) if current_matched < stake else stake - 1
    if to_state is OrderState.MATCHED:
        return stake
    return None


@hyp_settings(max_examples=60, stateful_step_count=40)
class OrderLifecycleMachine(RuleBasedStateMachine):
    """Model: one taker-v1 ``Order``, driven through random transition attempts."""

    def __init__(self) -> None:
        super().__init__()
        self.order = Order(
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
        self._tick = 0

    def _clock(self) -> tuple[datetime, int]:
        self._tick += 1
        return _BASE_TIME + timedelta(seconds=self._tick), self._tick

    @rule(to_state=st.sampled_from(list(OrderState)))
    def attempt_transition(self, to_state: OrderState) -> None:
        legal_targets = LEGAL_TRANSITIONS.get(self.order.state, frozenset())
        at_utc, monotonic_ns = self._clock()
        matched_target = _matched_target_for(to_state, self.order.stake_minor, self.order.matched_stake_minor)
        state_before = self.order.state
        history_before = self.order.history
        matched_before = self.order.matched_stake_minor

        if to_state not in legal_targets:
            with pytest.raises(IllegalTransitionError):
                self.order.transition(
                    to_state,
                    at_utc=at_utc,
                    monotonic_ns=monotonic_ns,
                    reason="stateful-illegal-attempt",
                    matched_stake_minor=matched_target,
                )
            # a rejected attempt must leave the model completely untouched.
            assert self.order.state is state_before
            assert self.order.history == history_before
            assert self.order.matched_stake_minor == matched_before
            return

        updated = self.order.transition(
            to_state,
            at_utc=at_utc,
            monotonic_ns=monotonic_ns,
            reason="stateful-legal-transition",
            matched_stake_minor=matched_target,
        )
        assert updated.state is to_state
        assert len(updated.history) == len(history_before) + 1
        assert updated.history[-1].from_state is state_before
        assert updated.history[-1].to_state is to_state
        assert updated.matched_stake_minor >= matched_before
        # the prior instance is never mutated -- Order is immutable.
        assert self.order.state is state_before
        assert self.order.history == history_before
        self.order = updated

    @invariant()
    def matched_stays_within_stake_bounds(self) -> None:
        assert 0 <= self.order.matched_stake_minor <= self.order.stake_minor

    @invariant()
    def settled_is_absorbing_except_resettled(self) -> None:
        if self.order.state is OrderState.SETTLED:
            assert LEGAL_TRANSITIONS[OrderState.SETTLED] == frozenset({OrderState.RESETTLED})

    @invariant()
    def resettled_is_a_pure_self_loop(self) -> None:
        if self.order.state is OrderState.RESETTLED:
            assert LEGAL_TRANSITIONS[OrderState.RESETTLED] == frozenset({OrderState.RESETTLED})

    @invariant()
    def taker_v1_incident_flag_matches_partially_matched(self) -> None:
        assert self.order.is_taker_v1_incident() == (self.order.state is OrderState.PARTIALLY_MATCHED)


TestOrderLifecycle = OrderLifecycleMachine.TestCase
