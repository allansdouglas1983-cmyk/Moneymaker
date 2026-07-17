"""F-13 failure injection: crashes and hostile broker-event orderings (SPEC-054/071).

* A process that records a retry attempt and dies BEFORE acting must not enable a
  double-fire: the restarted governor sees the attempt (digest burned, budget spent).
* A restarted process must reconcile before any retry approval.
* Out-of-order and duplicate broker events never regress the book or release a
  reservation that the surviving immutable record says is retained.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from l0_raw.store import AppendOnlyLog
from l5_decision.execution import PersistenceType, Side
from l6_broker.orders import (
    OrderBook,
    OrderState,
    PlaceCommand,
    StaleOrderUpdateError,
)
from l6_broker.retry import RetryGovernor, RetryRefusal

pytestmark = [pytest.mark.spec("SPEC-054"), pytest.mark.spec("SPEC-071")]

_T0 = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
_AT = _T0


def _governor(tmp_path: Path) -> RetryGovernor:
    return RetryGovernor(
        log=AppendOnlyLog(tmp_path / "retry.l0"), cooldown_seconds=60, attempt_budget=1
    )


def test_crash_between_record_and_act_cannot_double_fire(tmp_path: Path) -> None:
    first = _governor(tmp_path)
    first.mark_reconciled()
    approval = first.evaluate(
        "1.777", "dec-a", "book-a", now_utc=_T0, exposure_confirmed_zero=True
    )
    assert approval.approved
    first.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
    del first  # process dies before the order is ever transmitted

    survivor = _governor(tmp_path)
    survivor.mark_reconciled()
    replay = survivor.evaluate(
        "1.777", "dec-a", "book-a", now_utc=_T0 + timedelta(hours=1), exposure_confirmed_zero=True
    )
    assert not replay.approved
    assert replay.refusal is RetryRefusal.DUPLICATE_DECISION_SNAPSHOT
    fresh_state = survivor.evaluate(
        "1.777", "dec-b", "book-b", now_utc=_T0 + timedelta(hours=1), exposure_confirmed_zero=True
    )
    assert not fresh_state.approved  # budget of 1 already spent by the dead process
    assert fresh_state.refusal is RetryRefusal.ATTEMPT_BUDGET_EXHAUSTED


def test_restarted_process_must_reconcile_before_retry(tmp_path: Path) -> None:
    governor = _governor(tmp_path)
    decision = governor.evaluate(
        "1.777", "dec-a", "book-a", now_utc=_T0, exposure_confirmed_zero=True
    )
    assert decision.refusal is RetryRefusal.NOT_RECONCILED_SINCE_RESTART


def _command(ref: str) -> PlaceCommand:
    return PlaceCommand(
        customer_order_ref=ref,
        market_id="1.777",
        selection_id=11,
        side=Side.BACK,
        price_tick=40,
        stake_minor=500,
        market_version=1,
        persistence=PersistenceType.LAPSE,
    )


def test_out_of_order_and_duplicate_broker_events_never_regress_the_book() -> None:
    book = OrderBook()
    placed = book.place(_command("ref-1"), at_utc=_AT, monotonic_ns=1)
    submitted = placed.transition(
        OrderState.SUBMITTED, at_utc=_AT, monotonic_ns=2, reason="submit"
    )
    book.update(submitted)
    acked = submitted.transition(
        OrderState.ACKNOWLEDGED, at_utc=_AT, monotonic_ns=3, reason="ack"
    )
    book.update(acked)

    # Duplicate delivery of the CURRENT snapshot: idempotent no-op.
    book.update(acked)
    stored = book.get("ref-1")
    assert stored is not None and stored.state is OrderState.ACKNOWLEDGED

    # Out-of-order delivery of an EARLIER snapshot: refused, book unregressed.
    with pytest.raises(StaleOrderUpdateError):
        book.update(submitted)
    stored = book.get("ref-1")
    assert stored is not None and stored.state is OrderState.ACKNOWLEDGED
    assert book.is_market_reserved("1.777") is True
