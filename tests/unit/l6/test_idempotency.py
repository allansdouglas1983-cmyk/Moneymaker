"""Idempotent placement and the order book of record (SPEC-071).

"Duplicate commands MUST NOT create duplicate economic exposure." Keyed on
``customer_order_ref``. Covers: duplicate-ref short-circuit (identity, no exposure
change), differing-fields duplicates recorded as anomalies (never changing exposure),
market reservation (SPEC-054 extension, ADR 0014), and the SPEC-062 forward
unknown-state placement block. RED by construction: ``l6_broker`` does not exist yet.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

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

pytestmark = pytest.mark.spec("SPEC-071")

_NOW = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)


def _command(
    ref: str,
    *,
    market_id: str = "1.11111",
    selection_id: int = 111,
    stake_minor: int = 1_000,
    price_tick: int = 50,
    market_version: int = 1,
    side: Side = Side.BACK,
    persistence: PersistenceType = PersistenceType.LAPSE,
) -> PlaceCommand:
    return PlaceCommand(
        customer_order_ref=ref,
        market_id=market_id,
        selection_id=selection_id,
        side=side,
        price_tick=price_tick,
        stake_minor=stake_minor,
        market_version=market_version,
        persistence=persistence,
    )


def _place(book: OrderBook, command: PlaceCommand, *, mono: int = 1) -> Order:
    return book.place(command, at_utc=_NOW, monotonic_ns=mono)


# ---------------------------------------------------------------------------
# Duplicate-ref idempotency.
# ---------------------------------------------------------------------------


def test_duplicate_ref_identical_fields_returns_same_object() -> None:
    book = OrderBook()
    first = _place(book, _command("ref-1"))
    second = _place(book, _command("ref-1"), mono=2)
    assert first is second
    assert len(book.orders()) == 1
    assert book.anomalies == ()


def test_duplicate_ref_identical_fields_adds_no_exposure() -> None:
    book = OrderBook()
    _place(book, _command("ref-1", stake_minor=5_000))
    before = book.exposure_minor("1.11111")
    _place(book, _command("ref-1", stake_minor=5_000), mono=2)
    after = book.exposure_minor("1.11111")
    assert after == before


def test_differing_fields_duplicate_returns_existing_unchanged() -> None:
    book = OrderBook()
    first = _place(book, _command("ref-1", stake_minor=1_000, price_tick=50))
    second = _place(book, _command("ref-1", stake_minor=9_000, price_tick=100), mono=2)
    assert second is first
    assert second.stake_minor == 1_000
    assert second.price_tick == 50


def test_differing_fields_duplicate_adds_no_exposure_regardless_of_size() -> None:
    book = OrderBook()
    _place(book, _command("ref-1", stake_minor=1_000))
    before = book.exposure_minor("1.11111")
    # The duplicate claims a MUCH larger stake -- must still add zero exposure.
    _place(book, _command("ref-1", stake_minor=1_000_000), mono=2)
    after = book.exposure_minor("1.11111")
    assert after == before


def test_differing_fields_duplicate_records_anomaly() -> None:
    book = OrderBook()
    _place(book, _command("ref-1", stake_minor=1_000, price_tick=50))
    _place(book, _command("ref-1", stake_minor=9_000, price_tick=50), mono=2)
    assert len(book.anomalies) == 1
    anomaly = book.anomalies[0]
    assert anomaly.customer_order_ref == "ref-1"
    assert "stake_minor" in anomaly.differing_fields
    assert "price_tick" not in anomaly.differing_fields


def test_duplicate_replay_reflects_current_lifecycle_state_not_stale_created() -> None:
    book = OrderBook()
    placed = _place(book, _command("ref-1"))
    acknowledged = placed.transition(
        OrderState.SUBMITTED, at_utc=_NOW, monotonic_ns=2, reason="sent"
    ).transition(OrderState.ACKNOWLEDGED, at_utc=_NOW, monotonic_ns=3, reason="acked")
    book.update(acknowledged)
    replayed = _place(book, _command("ref-1"), mono=4)
    assert replayed.state is OrderState.ACKNOWLEDGED


def test_update_unknown_ref_raises_keyerror() -> None:
    book = OrderBook()
    _place(book, _command("ref-1"))
    never_placed = Order(
        order_id="ord-999",
        customer_order_ref="ref-never-placed",
        market_id="1.11111",
        selection_id=111,
        side=Side.BACK,
        price_tick=50,
        stake_minor=1_000,
        market_version=1,
        persistence=PersistenceType.LAPSE,
    )
    with pytest.raises(KeyError):
        book.update(never_placed)


# ---------------------------------------------------------------------------
# Market reservation (SPEC-054 extension, ADR 0014).
# ---------------------------------------------------------------------------


def test_second_distinct_ref_same_market_refused() -> None:
    book = OrderBook()
    _place(book, _command("ref-1", market_id="1.500"))
    with pytest.raises(MarketReservedError):
        _place(book, _command("ref-2", market_id="1.500"), mono=2)


def test_second_distinct_ref_same_market_same_selection_also_refused() -> None:
    book = OrderBook()
    _place(book, _command("ref-1", market_id="1.500", selection_id=111))
    with pytest.raises(MarketReservedError):
        _place(book, _command("ref-2", market_id="1.500", selection_id=111), mono=2)


def test_rejected_reservation_attempt_creates_no_second_order() -> None:
    book = OrderBook()
    first = _place(book, _command("ref-1", market_id="1.500"))
    with pytest.raises(MarketReservedError):
        _place(book, _command("ref-2", market_id="1.500"), mono=2)
    assert book.orders() == (first,)


def test_reservation_released_after_settlement() -> None:
    book = OrderBook()
    placed = _place(book, _command("ref-1", market_id="1.500"))
    settled = (
        placed.transition(OrderState.SUBMITTED, at_utc=_NOW, monotonic_ns=2, reason="a")
        .transition(OrderState.ACKNOWLEDGED, at_utc=_NOW, monotonic_ns=3, reason="b")
        .transition(OrderState.EXECUTABLE, at_utc=_NOW, monotonic_ns=4, reason="c")
        .transition(OrderState.MATCHED, at_utc=_NOW, monotonic_ns=5, reason="d", matched_stake_minor=1_000)
        .transition(OrderState.SETTLED, at_utc=_NOW, monotonic_ns=6, reason="e")
    )
    book.update(settled)
    # the market is now free for a new logical intent.
    second = _place(book, _command("ref-2", market_id="1.500"), mono=7)
    assert second.customer_order_ref == "ref-2"


def test_duplicate_of_reservation_holder_still_short_circuits() -> None:
    book = OrderBook()
    first = _place(book, _command("ref-1", market_id="1.500"))
    replay = _place(book, _command("ref-1", market_id="1.500"), mono=2)
    assert replay is first


# ---------------------------------------------------------------------------
# Unknown-state fail-closed hook (SPEC-062 forward dependency).
# ---------------------------------------------------------------------------


def test_unknown_flagged_order_blocks_all_further_placement() -> None:
    book = OrderBook()
    placed = _place(book, _command("ref-1", market_id="1.500"))
    book.update(placed.marked_unknown())
    with pytest.raises(PlacementBlockedError):
        _place(book, _command("ref-2", market_id="1.999"), mono=2)


def test_unknown_flag_blocks_even_a_pure_duplicate_replay() -> None:
    book = OrderBook()
    placed = _place(book, _command("ref-1", market_id="1.500"))
    book.update(placed.marked_unknown())
    with pytest.raises(PlacementBlockedError):
        _place(book, _command("ref-1", market_id="1.500"), mono=2)


# ---------------------------------------------------------------------------
# Money-type / hard-prohibition discipline at the placement boundary.
# ---------------------------------------------------------------------------


def test_lay_side_refused_for_a_new_ref() -> None:
    book = OrderBook()
    with pytest.raises(ValueError):
        _place(book, _command("ref-1", side=Side.LAY))


def test_non_lapse_persistence_refused_for_a_new_ref() -> None:
    book = OrderBook()
    with pytest.raises(ValueError):
        _place(book, _command("ref-1", persistence=PersistenceType.PERSIST))


@pytest.mark.parametrize("bad_tick", [-1, 100_000])
def test_invalid_tick_refused_for_a_new_ref(bad_tick: int) -> None:
    book = OrderBook()
    with pytest.raises(ValueError):
        _place(book, _command("ref-1", price_tick=bad_tick))


def test_float_stake_refused_typeerror_for_a_new_ref() -> None:
    book = OrderBook()
    with pytest.raises(TypeError):
        _place(book, _command("ref-1", stake_minor=100.5))  # type: ignore[arg-type]


def test_decimal_stake_refused_typeerror_for_a_new_ref() -> None:
    book = OrderBook()
    with pytest.raises(TypeError):
        _place(book, _command("ref-1", stake_minor=Decimal("100")))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Exposure definitions.
# ---------------------------------------------------------------------------


def test_potential_exposure_counts_full_stake_while_live() -> None:
    book = OrderBook()
    _place(book, _command("ref-1", market_id="1.700", stake_minor=2_500))
    exposure = book.exposure_minor("1.700")
    assert exposure.potential_exposure_minor == 2_500
    assert exposure.matched_exposure_minor == 0


def test_matched_exposure_reflects_partial_match() -> None:
    book = OrderBook()
    placed = _place(book, _command("ref-1", market_id="1.700", stake_minor=10_000))
    partial = (
        placed.transition(OrderState.SUBMITTED, at_utc=_NOW, monotonic_ns=2, reason="a")
        .transition(OrderState.ACKNOWLEDGED, at_utc=_NOW, monotonic_ns=3, reason="b")
        .transition(OrderState.EXECUTABLE, at_utc=_NOW, monotonic_ns=4, reason="c")
        .transition(OrderState.PARTIALLY_MATCHED, at_utc=_NOW, monotonic_ns=5, reason="d", matched_stake_minor=4_000)
    )
    book.update(partial)
    exposure = book.exposure_minor("1.700")
    assert exposure.potential_exposure_minor == 10_000
    assert exposure.matched_exposure_minor == 4_000


def test_voided_order_excluded_from_matched_exposure() -> None:
    book = OrderBook()
    placed = _place(book, _command("ref-1", market_id="1.700", stake_minor=10_000))
    voided = (
        placed.transition(OrderState.SUBMITTED, at_utc=_NOW, monotonic_ns=2, reason="a")
        .transition(OrderState.ACKNOWLEDGED, at_utc=_NOW, monotonic_ns=3, reason="b")
        .transition(OrderState.EXECUTABLE, at_utc=_NOW, monotonic_ns=4, reason="c")
        .transition(OrderState.PARTIALLY_MATCHED, at_utc=_NOW, monotonic_ns=5, reason="d", matched_stake_minor=4_000)
        .transition(OrderState.VOIDED, at_utc=_NOW, monotonic_ns=6, reason="e")
    )
    book.update(voided)
    exposure = book.exposure_minor("1.700")
    assert exposure.potential_exposure_minor == 0
    assert exposure.matched_exposure_minor == 0
