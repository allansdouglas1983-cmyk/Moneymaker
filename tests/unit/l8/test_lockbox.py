"""SPEC-092: lockbox integrity — one holdout period, never inspected during development.

``docs/SPECIFICATION.md`` §9.7: "Maintain one lockbox period that is never inspected during
feature development. Not once. If you look at it, it is burned and a new one must be defined."
GATE-1's ``lockbox_uncontaminated`` checklist item (``specs/gates/v1.yaml``) reads
:meth:`~l8_evidence.lockbox.LockboxRegistry.is_uncontaminated` as its deterministic input.
"""
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone

import pytest

from l8_evidence.lockbox import (
    GATE_1_ID,
    BurnReason,
    LockboxAccessGrant,
    LockboxBurnedError,
    LockboxDefinition,
    LockboxDefinitionError,
    LockboxEvent,
    LockboxEventKind,
    LockboxNotFoundError,
    LockboxRegistry,
    LockboxState,
    LockboxValidationError,
    derive_state,
)
from l8_evidence.prediction_snapshots import DualClockTimestamp

pytestmark = pytest.mark.spec("SPEC-092")


def _clock(ns: int = 1) -> DualClockTimestamp:
    return DualClockTimestamp(wall_utc=datetime(2026, 7, 16, 9, 0, 0, tzinfo=timezone.utc), monotonic_ns=ns)


def _definition(
    *,
    lockbox_id: str = "lockbox-2026a",
    start: date = date(2026, 1, 1),
    end: date = date(2026, 3, 31),
    defined_by: str = "reviewer@research",
) -> LockboxDefinition:
    return LockboxDefinition(
        lockbox_id=lockbox_id,
        period_start=start,
        period_end=end,
        defined_at=_clock(),
        defined_by=defined_by,
    )


# --- LockboxDefinition validation -------------------------------------------------------


def test_definition_rejects_empty_lockbox_id() -> None:
    with pytest.raises(LockboxValidationError):
        _definition(lockbox_id="")


def test_definition_rejects_whitespace_only_lockbox_id() -> None:
    with pytest.raises(LockboxValidationError):
        _definition(lockbox_id="   ")


def test_definition_rejects_start_after_end() -> None:
    with pytest.raises(LockboxValidationError):
        _definition(start=date(2026, 4, 1), end=date(2026, 1, 1))


def test_definition_accepts_start_equal_to_end() -> None:
    _definition(start=date(2026, 1, 1), end=date(2026, 1, 1))


def test_definition_rejects_empty_defined_by() -> None:
    with pytest.raises(LockboxValidationError):
        _definition(defined_by="")


def test_definition_accepts_valid_fields() -> None:
    definition = _definition()
    assert definition.lockbox_id == "lockbox-2026a"


# --- define() -----------------------------------------------------------------------------


def test_define_seals_a_new_lockbox() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    assert registry.state("lockbox-2026a") is LockboxState.SEALED


def test_define_refuses_duplicate_lockbox_id() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    with pytest.raises(LockboxDefinitionError):
        registry.define(_definition())


def test_define_refuses_a_second_concurrently_sealed_lockbox() -> None:
    registry = LockboxRegistry()
    registry.define(_definition(lockbox_id="lockbox-a"))
    with pytest.raises(LockboxDefinitionError):
        registry.define(_definition(lockbox_id="lockbox-b"))


def test_define_permits_a_replacement_once_the_prior_lockbox_is_burned() -> None:
    registry = LockboxRegistry()
    registry.define(_definition(lockbox_id="lockbox-a"))
    registry.access(
        "lockbox-a", accessor="gate1-runner", purpose="GATE-1 evaluation", gate_id=GATE_1_ID, at=_clock(2)
    )
    assert registry.state("lockbox-a") is LockboxState.BURNED
    registry.define(_definition(lockbox_id="lockbox-b"))
    assert registry.state("lockbox-b") is LockboxState.SEALED


def test_define_refuses_a_lockbox_id_that_was_previously_burned_even_for_a_new_seal() -> None:
    registry = LockboxRegistry()
    registry.define(_definition(lockbox_id="lockbox-a"))
    registry.access(
        "lockbox-a", accessor="gate1-runner", purpose="GATE-1 evaluation", gate_id=GATE_1_ID, at=_clock(2)
    )
    with pytest.raises(LockboxDefinitionError):
        registry.define(_definition(lockbox_id="lockbox-a"))


# --- access(): unknown lockbox --------------------------------------------------------------


def test_access_to_unknown_lockbox_raises_not_found() -> None:
    registry = LockboxRegistry()
    with pytest.raises(LockboxNotFoundError):
        registry.access(
            "does-not-exist", accessor="someone", purpose="curiosity", gate_id=GATE_1_ID, at=_clock()
        )


def test_state_of_unknown_lockbox_raises_not_found() -> None:
    registry = LockboxRegistry()
    with pytest.raises(LockboxNotFoundError):
        registry.state("does-not-exist")


def test_is_uncontaminated_of_unknown_lockbox_raises_not_found() -> None:
    registry = LockboxRegistry()
    with pytest.raises(LockboxNotFoundError):
        registry.is_uncontaminated("does-not-exist")


def test_access_log_of_unknown_lockbox_raises_not_found() -> None:
    registry = LockboxRegistry()
    with pytest.raises(LockboxNotFoundError):
        registry.access_log("does-not-exist")


# --- access() validation -------------------------------------------------------------------


def test_access_rejects_empty_accessor() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    with pytest.raises(LockboxValidationError):
        registry.access("lockbox-2026a", accessor="", purpose="p", gate_id=GATE_1_ID, at=_clock())


def test_access_rejects_empty_purpose() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    with pytest.raises(LockboxValidationError):
        registry.access("lockbox-2026a", accessor="a", purpose="", gate_id=GATE_1_ID, at=_clock())


def test_access_rejects_empty_gate_id() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    with pytest.raises(LockboxValidationError):
        registry.access("lockbox-2026a", accessor="a", purpose="p", gate_id="", at=_clock())


# --- the core access semantics ---------------------------------------------------------------


def test_gate1_access_on_sealed_lockbox_returns_a_grant() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    grant = registry.access(
        "lockbox-2026a", accessor="gate1-runner", purpose="GATE-1 evaluation", gate_id=GATE_1_ID, at=_clock(2)
    )
    assert isinstance(grant, LockboxAccessGrant)
    assert grant.lockbox_id == "lockbox-2026a"
    assert grant.period_start == date(2026, 1, 1)
    assert grant.period_end == date(2026, 3, 31)
    assert grant.accessor == "gate1-runner"
    assert grant.gate_id == GATE_1_ID


def test_gate1_access_on_sealed_lockbox_burns_it_with_gate1_evaluation_consumed_reason() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    registry.access(
        "lockbox-2026a", accessor="gate1-runner", purpose="GATE-1 evaluation", gate_id=GATE_1_ID, at=_clock(2)
    )
    assert registry.state("lockbox-2026a") is LockboxState.BURNED
    burn_events = [
        e for e in registry.access_log("lockbox-2026a") if e.kind is LockboxEventKind.BURNED
    ]
    assert len(burn_events) == 1
    assert burn_events[0].burn_reason is BurnReason.GATE1_EVALUATION_CONSUMED


def test_non_gate1_access_on_sealed_lockbox_raises_and_returns_no_grant() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    with pytest.raises(LockboxBurnedError):
        registry.access(
            "lockbox-2026a", accessor="curious-dev", purpose="peeking", gate_id="GATE-2", at=_clock(2)
        )


def test_non_gate1_access_on_sealed_lockbox_burns_it_with_unauthorized_access_reason() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    with pytest.raises(LockboxBurnedError):
        registry.access(
            "lockbox-2026a", accessor="curious-dev", purpose="peeking", gate_id="GATE-2", at=_clock(2)
        )
    assert registry.state("lockbox-2026a") is LockboxState.BURNED
    burn_events = [
        e for e in registry.access_log("lockbox-2026a") if e.kind is LockboxEventKind.BURNED
    ]
    assert len(burn_events) == 1
    assert burn_events[0].burn_reason is BurnReason.UNAUTHORIZED_ACCESS


def test_unauthorized_access_is_present_in_the_log_even_though_it_raised() -> None:
    """Log-then-grant: the ACCESSED event must exist even on the raising branch."""
    registry = LockboxRegistry()
    registry.define(_definition())
    with pytest.raises(LockboxBurnedError):
        registry.access(
            "lockbox-2026a", accessor="curious-dev", purpose="peeking", gate_id="GATE-2", at=_clock(2)
        )
    accessed_events = [
        e for e in registry.access_log("lockbox-2026a") if e.kind is LockboxEventKind.ACCESSED
    ]
    assert len(accessed_events) == 1
    assert accessed_events[0].accessor == "curious-dev"
    assert accessed_events[0].purpose == "peeking"
    assert accessed_events[0].gate_id == "GATE-2"


def test_access_on_an_already_burned_lockbox_is_logged_and_refused() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    registry.access(
        "lockbox-2026a", accessor="gate1-runner", purpose="GATE-1 evaluation", gate_id=GATE_1_ID, at=_clock(2)
    )
    with pytest.raises(LockboxBurnedError):
        registry.access(
            "lockbox-2026a", accessor="someone-else", purpose="another look", gate_id=GATE_1_ID, at=_clock(3)
        )
    accessed_events = [
        e for e in registry.access_log("lockbox-2026a") if e.kind is LockboxEventKind.ACCESSED
    ]
    assert len(accessed_events) == 2


def test_access_on_an_already_burned_lockbox_causes_no_further_state_change() -> None:
    """Only ONE BURNED event ever exists — burned-by-use is not re-burned by later attempts."""
    registry = LockboxRegistry()
    registry.define(_definition())
    registry.access(
        "lockbox-2026a", accessor="gate1-runner", purpose="GATE-1 evaluation", gate_id=GATE_1_ID, at=_clock(2)
    )
    with pytest.raises(LockboxBurnedError):
        registry.access(
            "lockbox-2026a", accessor="someone-else", purpose="another look", gate_id="GATE-2", at=_clock(3)
        )
    burn_events = [
        e for e in registry.access_log("lockbox-2026a") if e.kind is LockboxEventKind.BURNED
    ]
    assert len(burn_events) == 1
    assert burn_events[0].burn_reason is BurnReason.GATE1_EVALUATION_CONSUMED


# --- is_uncontaminated ------------------------------------------------------------------------


def test_is_uncontaminated_true_for_a_freshly_sealed_never_accessed_lockbox() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    assert registry.is_uncontaminated("lockbox-2026a") is True


def test_is_uncontaminated_false_after_gate1_access() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    registry.access(
        "lockbox-2026a", accessor="gate1-runner", purpose="GATE-1 evaluation", gate_id=GATE_1_ID, at=_clock(2)
    )
    assert registry.is_uncontaminated("lockbox-2026a") is False


def test_is_uncontaminated_false_after_unauthorized_access() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    with pytest.raises(LockboxBurnedError):
        registry.access(
            "lockbox-2026a", accessor="curious-dev", purpose="peeking", gate_id="GATE-2", at=_clock(2)
        )
    assert registry.is_uncontaminated("lockbox-2026a") is False


# --- access_log immutability / shape ------------------------------------------------------------


def test_access_log_returns_a_tuple() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    log = registry.access_log("lockbox-2026a")
    assert isinstance(log, tuple)
    assert len(log) == 1
    assert log[0].kind is LockboxEventKind.DEFINED


def test_lockbox_event_is_frozen() -> None:
    registry = LockboxRegistry()
    registry.define(_definition())
    event = registry.access_log("lockbox-2026a")[0]
    with pytest.raises(Exception):  # noqa: B017 - frozen dataclass raises FrozenInstanceError
        event.lockbox_id = "other"  # type: ignore[misc]


# --- derive_state -----------------------------------------------------------------------------


def test_derive_state_raises_on_empty_event_sequence() -> None:
    with pytest.raises(LockboxValidationError):
        derive_state(())


def test_derive_state_raises_when_no_defined_event_present() -> None:
    accessed = LockboxEvent(
        lockbox_id="x",
        kind=LockboxEventKind.ACCESSED,
        at=_clock(),
        period_start=None,
        period_end=None,
        defined_by=None,
        accessor="a",
        purpose="p",
        gate_id=GATE_1_ID,
        burn_reason=None,
    )
    with pytest.raises(LockboxValidationError):
        derive_state((accessed,))


# --- no update/delete API surface --------------------------------------------------------------


def test_registry_has_no_update_or_delete_api() -> None:
    public_methods = {
        name
        for name, _ in inspect.getmembers(LockboxRegistry, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    assert public_methods == {"define", "access", "state", "is_uncontaminated", "access_log"}


# --- LockboxAccessGrant validation --------------------------------------------------------------


def test_grant_rejects_a_non_gate1_gate_id_directly_constructed() -> None:
    with pytest.raises(LockboxValidationError):
        LockboxAccessGrant(
            lockbox_id="lockbox-2026a",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            accessor="a",
            purpose="p",
            gate_id="GATE-2",
            at=_clock(),
        )
