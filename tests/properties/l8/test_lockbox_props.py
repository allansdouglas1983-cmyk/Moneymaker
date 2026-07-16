"""SPEC-092 properties: burned is absorbing, replay is derivable, digests are deterministic."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l8_evidence.lockbox import (
    GATE_1_ID,
    BurnReason,
    LockboxBurnedError,
    LockboxDefinition,
    LockboxEvent,
    LockboxEventKind,
    LockboxRegistry,
    LockboxState,
    derive_state,
)
from l8_evidence.prediction_snapshots import DualClockTimestamp

pytestmark = pytest.mark.spec("SPEC-092")

_GATE_IDS = st.sampled_from([GATE_1_ID, "GATE-2", "GATE--1A", "GATE-3"])


def _clock(ns: int) -> DualClockTimestamp:
    return DualClockTimestamp(wall_utc=datetime(2026, 7, 16, 9, 0, 0, tzinfo=timezone.utc), monotonic_ns=ns)


def _definition(lockbox_id: str = "lockbox-2026a") -> LockboxDefinition:
    return LockboxDefinition(
        lockbox_id=lockbox_id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        defined_at=_clock(0),
        defined_by="reviewer@research",
    )


def _defined_event(lockbox_id: str = "x") -> LockboxEvent:
    return LockboxEvent(
        lockbox_id=lockbox_id,
        kind=LockboxEventKind.DEFINED,
        at=_clock(0),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        defined_by="reviewer@research",
        accessor=None,
        purpose=None,
        gate_id=None,
        burn_reason=None,
    )


def _accessed_event(lockbox_id: str = "x", *, ns: int, gate_id: str) -> LockboxEvent:
    return LockboxEvent(
        lockbox_id=lockbox_id,
        kind=LockboxEventKind.ACCESSED,
        at=_clock(ns),
        period_start=None,
        period_end=None,
        defined_by=None,
        accessor="someone",
        purpose="a purpose",
        gate_id=gate_id,
        burn_reason=None,
    )


def _burned_event(lockbox_id: str = "x", *, ns: int, reason: BurnReason) -> LockboxEvent:
    return LockboxEvent(
        lockbox_id=lockbox_id,
        kind=LockboxEventKind.BURNED,
        at=_clock(ns),
        period_start=None,
        period_end=None,
        defined_by=None,
        accessor=None,
        purpose=None,
        gate_id=None,
        burn_reason=reason,
    )


# --- burned is an absorbing state ----------------------------------------------------------


@given(gate_ids=st.lists(_GATE_IDS, min_size=1, max_size=8))
@settings(max_examples=100)
def test_every_access_after_the_first_always_raises_burned(gate_ids: list[str]) -> None:
    """Once a lockbox is burned by any access, EVERY subsequent access raises, regardless of
    gate_id — this is the property test for the burned-absorbing requirement: a constant
    "always succeeds" implementation of access() would fail this on the second call."""
    registry = LockboxRegistry()
    registry.define(_definition())
    outcomes = []
    for i, gate_id in enumerate(gate_ids):
        try:
            registry.access(
                "lockbox-2026a", accessor="a", purpose="p", gate_id=gate_id, at=_clock(i + 1)
            )
            outcomes.append("granted")
        except LockboxBurnedError:
            outcomes.append("refused")
    # exactly the first access may be granted (only if it was GATE-1); every later one, on an
    # already-burned lockbox, must be refused.
    for outcome in outcomes[1:]:
        assert outcome == "refused"
    assert registry.state("lockbox-2026a") is LockboxState.BURNED


@given(gate_id=_GATE_IDS)
@settings(max_examples=25)
def test_first_access_always_burns_the_lockbox_regardless_of_gate_id(gate_id: str) -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    try:
        registry.access("lockbox-2026a", accessor="a", purpose="p", gate_id=gate_id, at=_clock(1))
    except LockboxBurnedError:
        pass
    assert registry.state("lockbox-2026a") is LockboxState.BURNED


@given(gate_id=_GATE_IDS)
@settings(max_examples=25)
def test_burn_reason_matches_whether_the_access_was_gate1(gate_id: str) -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    try:
        registry.access("lockbox-2026a", accessor="a", purpose="p", gate_id=gate_id, at=_clock(1))
    except LockboxBurnedError:
        pass
    burn_events = [e for e in registry.access_log("lockbox-2026a") if e.kind is LockboxEventKind.BURNED]
    assert len(burn_events) == 1
    expected = BurnReason.GATE1_EVALUATION_CONSUMED if gate_id == GATE_1_ID else BurnReason.UNAUTHORIZED_ACCESS
    assert burn_events[0].burn_reason is expected


# --- replay determinism: state is derivable purely from the event tuple --------------------


@given(
    accesses=st.lists(_GATE_IDS, min_size=0, max_size=6),
)
@settings(max_examples=100)
def test_replaying_the_event_log_reproduces_identical_state(accesses: list[str]) -> None:
    """Rebuilding state from the event tuple alone (derive_state) must always agree with the
    registry's own state() — the log is the single source of truth, nothing is cached."""
    registry = LockboxRegistry()
    registry.define(_definition())
    for i, gate_id in enumerate(accesses):
        try:
            registry.access("lockbox-2026a", accessor="a", purpose="p", gate_id=gate_id, at=_clock(i + 1))
        except LockboxBurnedError:
            pass

    log = registry.access_log("lockbox-2026a")
    replayed_state = derive_state(log)
    assert replayed_state is registry.state("lockbox-2026a")
    # Replaying the exact same tuple twice must be pure and produce the same answer again.
    assert derive_state(log) is replayed_state


@given(
    prefix_len=st.integers(min_value=0, max_value=4),
    reason=st.sampled_from(list(BurnReason)),
    trailing_accessed=st.integers(min_value=0, max_value=4),
)
@settings(max_examples=100)
def test_derive_state_is_burned_whenever_any_burned_event_is_present(
    prefix_len: int, reason: BurnReason, trailing_accessed: int
) -> None:
    events: list[LockboxEvent] = [_defined_event()]
    events += [_accessed_event(ns=i + 1, gate_id="GATE-2") for i in range(prefix_len)]
    events.append(_burned_event(ns=prefix_len + 1, reason=reason))
    events += [
        _accessed_event(ns=prefix_len + 2 + i, gate_id=GATE_1_ID) for i in range(trailing_accessed)
    ]
    assert derive_state(tuple(events)) is LockboxState.BURNED


@given(accessed_count=st.integers(min_value=0, max_value=6))
@settings(max_examples=50)
def test_derive_state_is_sealed_when_no_burned_event_is_present(accessed_count: int) -> None:
    # ACCESSED events with no BURNED event cannot actually arise from LockboxRegistry.access
    # (every access burns) but derive_state is a pure function tested directly against its own
    # contract: SEALED iff a DEFINED event exists and no BURNED event does, independent of how
    # many ACCESSED events sit alongside it.
    events: list[LockboxEvent] = [_defined_event()]
    events += [_accessed_event(ns=i + 1, gate_id=GATE_1_ID) for i in range(accessed_count)]
    assert derive_state(tuple(events)) is LockboxState.SEALED


# --- digest determinism -----------------------------------------------------------------------


@given(ns=st.integers(min_value=0, max_value=10_000))
@settings(max_examples=50)
def test_content_digest_is_deterministic_for_identical_events(ns: int) -> None:
    a = _accessed_event(ns=ns, gate_id=GATE_1_ID)
    b = _accessed_event(ns=ns, gate_id=GATE_1_ID)
    assert a.content_digest() == b.content_digest()


@given(ns_a=st.integers(min_value=0, max_value=10_000), ns_b=st.integers(min_value=0, max_value=10_000))
@settings(max_examples=50)
def test_content_digest_changes_when_monotonic_ns_differs(ns_a: int, ns_b: int) -> None:
    if ns_a == ns_b:
        ns_b = ns_a + 1
    a = _accessed_event(ns=ns_a, gate_id=GATE_1_ID)
    b = _accessed_event(ns=ns_b, gate_id=GATE_1_ID)
    assert a.content_digest() != b.content_digest()


@given(reason=st.sampled_from(list(BurnReason)))
@settings(max_examples=10)
def test_content_digest_changes_with_burn_reason(reason: BurnReason) -> None:
    other = [r for r in BurnReason if r is not reason][0]
    a = _burned_event(ns=1, reason=reason)
    b = _burned_event(ns=1, reason=other)
    assert a.content_digest() != b.content_digest()


@given(gate_id=_GATE_IDS)
@settings(max_examples=25)
def test_content_digest_changes_with_gate_id(gate_id: str) -> None:
    other_gate_id = "GATE-DIFFERENT"
    a = _accessed_event(ns=1, gate_id=gate_id)
    b = _accessed_event(ns=1, gate_id=other_gate_id)
    assert a.content_digest() != b.content_digest()
