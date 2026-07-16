"""SPEC-071 property: exposure invariance under duplicated commands.

"Duplicate commands MUST NOT create duplicate economic exposure" -- tested here as a
Hypothesis property over generated command sequences containing injected duplicates
(including differing-fields duplicates), rather than as a fixed example: applying a
sequence with duplicate ``customer_order_ref`` replays must produce EXACTLY the same
``Exposure`` per market as applying only the first command seen for each reference, in
any shuffled order. A second property proves the companion guard: a genuinely distinct
reference on an already-reserved market is refused, never silently merged, regardless of
its stake/tick. RED by construction: ``l6_broker`` does not exist yet.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l5_decision.execution import PersistenceType, Side
from l6_broker.orders import MarketReservedError, OrderBook, PlaceCommand
from price_contracts.ladder import TICK_COUNT

pytestmark = pytest.mark.spec("SPEC-071")

_NOW = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
_STAKE = st.integers(min_value=1, max_value=1_000_000)
_TICK = st.integers(min_value=0, max_value=TICK_COUNT - 1)
_VERSION = st.integers(min_value=1, max_value=100)
_SELECTION = st.integers(min_value=1, max_value=40)
_N_INTENTS = st.integers(min_value=1, max_value=4)
_N_DUPES = st.integers(min_value=0, max_value=3)


def _command(ref: str, market_id: str, *, stake: int, tick: int, version: int, selection: int) -> PlaceCommand:
    return PlaceCommand(
        customer_order_ref=ref,
        market_id=market_id,
        selection_id=selection,
        side=Side.BACK,
        price_tick=tick,
        stake_minor=stake,
        market_version=version,
        persistence=PersistenceType.LAPSE,
    )


def _first_occurrence_dedup(sequence: list[PlaceCommand]) -> list[PlaceCommand]:
    seen: set[str] = set()
    deduped: list[PlaceCommand] = []
    for command in sequence:
        if command.customer_order_ref in seen:
            continue
        seen.add(command.customer_order_ref)
        deduped.append(command)
    return deduped


def _apply(commands: list[PlaceCommand]) -> OrderBook:
    book = OrderBook()
    for i, command in enumerate(commands):
        book.place(command, at_utc=_NOW, monotonic_ns=i + 1)
    return book


@given(n_intents=_N_INTENTS, data=st.data())
@settings(max_examples=150)
def test_duplicate_commands_never_change_exposure(n_intents: int, data: st.DataObject) -> None:
    # Each logical intent gets its OWN market, so this property isolates duplicate-
    # exposure invariance from the market-reservation guard (tested separately below).
    sequence: list[PlaceCommand] = []
    for i in range(n_intents):
        ref = f"ref-{i}"
        market_id = f"1.{1_000 + i}"
        canonical = _command(
            ref,
            market_id,
            stake=data.draw(_STAKE, label=f"stake-{i}"),
            tick=data.draw(_TICK, label=f"tick-{i}"),
            version=data.draw(_VERSION, label=f"version-{i}"),
            selection=data.draw(_SELECTION, label=f"selection-{i}"),
        )
        sequence.append(canonical)
        for d in range(data.draw(_N_DUPES, label=f"n_dupes-{i}")):
            # A differing-fields duplicate: same ref/market, everything else re-drawn --
            # per SPEC-071 this must still add zero exposure.
            variant = _command(
                ref,
                market_id,
                stake=data.draw(_STAKE, label=f"variant-stake-{i}-{d}"),
                tick=data.draw(_TICK, label=f"variant-tick-{i}-{d}"),
                version=data.draw(_VERSION, label=f"variant-version-{i}-{d}"),
                selection=data.draw(_SELECTION, label=f"variant-selection-{i}-{d}"),
            )
            sequence.append(variant)

    shuffled = data.draw(st.permutations(sequence), label="shuffled")

    full_book = _apply(list(shuffled))
    deduped_book = _apply(_first_occurrence_dedup(list(shuffled)))

    assert len(full_book.orders()) == n_intents
    assert len(deduped_book.orders()) == n_intents

    markets = {command.market_id for command in sequence}
    for market_id in markets:
        assert full_book.exposure_minor(market_id) == deduped_book.exposure_minor(market_id)


@settings(max_examples=100)
@given(
    stake_first=_STAKE,
    stake_second=_STAKE,
    tick_first=_TICK,
    tick_second=_TICK,
    version=_VERSION,
    selection_first=_SELECTION,
    selection_second=_SELECTION,
)
def test_distinct_ref_same_market_always_refused_never_merged(
    stake_first: int,
    stake_second: int,
    tick_first: int,
    tick_second: int,
    version: int,
    selection_first: int,
    selection_second: int,
) -> None:
    book = OrderBook()
    market_id = "1.999999"
    first = _command(
        "ref-a", market_id, stake=stake_first, tick=tick_first, version=version, selection=selection_first
    )
    second = _command(
        "ref-b", market_id, stake=stake_second, tick=tick_second, version=version, selection=selection_second
    )
    placed_first = book.place(first, at_utc=_NOW, monotonic_ns=1)
    with pytest.raises(MarketReservedError):
        book.place(second, at_utc=_NOW, monotonic_ns=2)

    # the rejected attempt must not silently merge into the book or change exposure.
    assert book.orders() == (placed_first,)
    exposure = book.exposure_minor(market_id)
    assert exposure.potential_exposure_minor == stake_first
    assert exposure.matched_exposure_minor == 0
