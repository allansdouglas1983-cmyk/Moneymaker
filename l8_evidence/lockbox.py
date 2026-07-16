"""SPEC-092: lockbox integrity — the audit/permission layer for the one holdout period.

``docs/SPECIFICATION.md`` §9.7: "Maintain one lockbox period that is never inspected during
feature development. Not once. If you look at it, it is burned and a new one must be defined."
GATE-1's ``lockbox_uncontaminated`` checklist item (``specs/gates/v1.yaml``) reads this
module's :meth:`LockboxRegistry.is_uncontaminated` as its deterministic input.

This module does NOT hold, join or return the lockbox's actual race/market data — it is the
authoritative permission-and-audit record of who touched the holdout period and when. Blocking
the corresponding data access at the storage layer is a separate, later concern; every
legitimate data-layer reader is expected to call :meth:`LockboxRegistry.access` first and
refuse to read anything without a returned :class:`LockboxAccessGrant`.

Design, event-sourced (mirrors :mod:`l8_evidence.prediction_snapshots`'s ``SnapshotStore`):
a lockbox's :class:`LockboxState` is never stored as a mutable field anywhere in this module.
It is DERIVED, every call, by folding :func:`derive_state` over that lockbox's own append-only
event tuple. The only mutable state a :class:`LockboxRegistry` instance owns is the event log
itself, and the log only ever grows — there is no update or delete method anywhere in this
module's public surface.

The core rule this module exists to enforce (SPEC-092): every access is appended to the
immutable log BEFORE any grant or refusal is decided — log-then-grant, never grant-then-log —
so an unauthorized inspection is captured in the audit trail even though it is refused and
burns the lockbox. Gate 1 evaluation (``gate_id == "GATE-1"``) is the ONE access kind that is
ever permitted on a SEALED lockbox; that permitted read still spends the lockbox (it can never
again serve as an untouched holdout), so it burns it too, under a distinct reason
(``GATE1_EVALUATION_CONSUMED``) from an outright violation (``UNAUTHORIZED_ACCESS``). Burned is
an absorbing state: every further access to an already-burned lockbox, on any ``gate_id``, is
logged and refused with no additional state change.

No LLM computes, infers or approves any part of this module's state transitions or digests —
every value here is deterministic arithmetic and enum-closed vocabulary over caller-supplied
facts (SPECIFICATION.md §0 Rule 3).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from typing import Any, Mapping, Sequence

from l8_evidence.prediction_snapshots import DualClockTimestamp

__all__ = [
    "GATE_1_ID",
    "LockboxState",
    "LockboxEventKind",
    "BurnReason",
    "LockboxError",
    "LockboxValidationError",
    "LockboxDefinitionError",
    "LockboxNotFoundError",
    "LockboxBurnedError",
    "LockboxDefinition",
    "LockboxEvent",
    "LockboxAccessGrant",
    "LockboxRegistry",
    "derive_state",
]

#: The one gate permitted to read the lockbox (SPEC-092, §9.7, GATE-1's
#: ``lockbox_uncontaminated`` item in ``specs/gates/v1.yaml``). Any other ``gate_id`` value
#: passed to :meth:`LockboxRegistry.access` — including ``None``-like empty strings, which are
#: refused earlier as a validation error — is an unauthorized inspection.
GATE_1_ID = "GATE-1"


class LockboxError(ValueError):
    """Base error for this module (SPEC-092)."""


class LockboxValidationError(LockboxError):
    """A lockbox definition, event or grant's own fields are internally inconsistent."""


class LockboxDefinitionError(LockboxError):
    """``define`` refused: a duplicate ``lockbox_id``, or a second concurrent SEALED lockbox.

    Only one holdout period may be sealed at a time; a replacement may be defined once its
    predecessor is burned, but a ``lockbox_id`` is never reused, burned or not.
    """


class LockboxNotFoundError(LockboxError):
    """No lockbox has ever been defined with this id in this registry."""


class LockboxBurnedError(LockboxError):
    """Access refused: either the lockbox was already burned, or this very access burns it.

    Raised in both cases the requirement demands never be silent: an access to an
    already-burned lockbox, and an access with a ``gate_id`` other than :data:`GATE_1_ID` on a
    still-SEALED lockbox (which this call itself burns before raising).
    """


class LockboxState(Enum):
    """A lockbox is SEALED at definition; BURNED is a terminal, absorbing state (SPEC-092)."""

    SEALED = "SEALED"
    BURNED = "BURNED"


class LockboxEventKind(Enum):
    """The closed vocabulary of events in a lockbox's append-only history."""

    DEFINED = "DEFINED"
    ACCESSED = "ACCESSED"
    BURNED = "BURNED"


class BurnReason(Enum):
    """Why a lockbox transitioned to BURNED — distinct in the log from the very first event.

    ``GATE1_EVALUATION_CONSUMED``: the one permitted read (Gate 1 evaluation) spent it.
    ``UNAUTHORIZED_ACCESS``: any other access attempt — burned-by-violation, not burned-by-use.
    """

    GATE1_EVALUATION_CONSUMED = "GATE1_EVALUATION_CONSUMED"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"


def _require_nonempty(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise LockboxValidationError(f"{field_name} must be non-empty")


def _jsonable(value: Any) -> Any:
    """Recursively convert a value into a JSON-serialisable, canonically-ordered form.

    House style shared with :mod:`l8_evidence.prediction_snapshots`'s helper of the same name:
    ``Decimal`` (unused here) would render via ``str``, enums render via ``.value``, datetimes
    via ``.isoformat()``, mappings/dataclasses recurse with sorted keys so the same logical
    content always serialises byte-identically regardless of dict insertion order.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    return value


@dataclass(frozen=True)
class LockboxDefinition:
    """The declaration of one lockbox holdout period (SPEC-092, §9.7 ``lockbox_window``)."""

    lockbox_id: str
    period_start: date
    period_end: date
    defined_at: DualClockTimestamp
    defined_by: str

    def __post_init__(self) -> None:
        _require_nonempty(self.lockbox_id, "lockbox_id")
        _require_nonempty(self.defined_by, "defined_by")
        if self.period_start > self.period_end:
            raise LockboxValidationError(
                f"period_start {self.period_start.isoformat()} must not be after "
                f"period_end {self.period_end.isoformat()}"
            )


@dataclass(frozen=True)
class LockboxEvent:
    """One immutable entry in a lockbox's append-only history.

    Only the fields relevant to ``kind`` are populated; the rest are ``None``. This keeps the
    event log the SOLE source of truth for both the definition (period, definer) and every
    access attempt — there is no second, separately-mutated store of "the current definition"
    anywhere in this module.
    """

    lockbox_id: str
    kind: LockboxEventKind
    at: DualClockTimestamp
    period_start: date | None
    period_end: date | None
    defined_by: str | None
    accessor: str | None
    purpose: str | None
    gate_id: str | None
    burn_reason: BurnReason | None

    def __post_init__(self) -> None:
        _require_nonempty(self.lockbox_id, "lockbox_id")
        definition_fields = (self.period_start, self.period_end, self.defined_by)
        access_fields = (self.accessor, self.purpose, self.gate_id)
        if self.kind is LockboxEventKind.DEFINED:
            if any(f is None for f in definition_fields):
                raise LockboxValidationError("a DEFINED event must carry period_start/period_end/defined_by")
            if any(f is not None for f in access_fields) or self.burn_reason is not None:
                raise LockboxValidationError("a DEFINED event must not carry access or burn fields")
            assert (
                self.period_start is not None
                and self.period_end is not None
                and self.defined_by is not None
            )  # narrowed above
            if self.period_start > self.period_end:
                raise LockboxValidationError("period_start must not be after period_end")
            _require_nonempty(self.defined_by, "defined_by")
        elif self.kind is LockboxEventKind.ACCESSED:
            if any(f is None for f in access_fields):
                raise LockboxValidationError("an ACCESSED event must carry accessor/purpose/gate_id")
            if any(f is not None for f in definition_fields) or self.burn_reason is not None:
                raise LockboxValidationError("an ACCESSED event must not carry definition or burn fields")
            assert self.accessor is not None and self.purpose is not None and self.gate_id is not None
            _require_nonempty(self.accessor, "accessor")
            _require_nonempty(self.purpose, "purpose")
            _require_nonempty(self.gate_id, "gate_id")
        else:  # LockboxEventKind.BURNED
            if self.burn_reason is None:
                raise LockboxValidationError("a BURNED event must carry burn_reason")
            if any(f is not None for f in definition_fields) or any(f is not None for f in access_fields):
                raise LockboxValidationError("a BURNED event must not carry definition or access fields")

    def content_digest(self) -> str:
        """Deterministic ``sha256:<hex>`` over every field, canonically serialised.

        Identical field values always produce an identical digest; any single field change
        (including ``at.monotonic_ns``) produces a different one.
        """
        payload = _jsonable(asdict(self))
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LockboxAccessGrant:
    """Proof that one specific access was logged and permitted (SPEC-092).

    Returned ONLY by a GATE-1 access on a SEALED lockbox. This record itself carries no actual
    lockbox data — the data-layer enforcement that reads this grant to decide what may be
    unsealed is a downstream concern; this type is the authoritative permission marker for it.
    """

    lockbox_id: str
    period_start: date
    period_end: date
    accessor: str
    purpose: str
    gate_id: str
    at: DualClockTimestamp

    def __post_init__(self) -> None:
        _require_nonempty(self.lockbox_id, "lockbox_id")
        _require_nonempty(self.accessor, "accessor")
        _require_nonempty(self.purpose, "purpose")
        _require_nonempty(self.gate_id, "gate_id")
        if self.gate_id != GATE_1_ID:
            raise LockboxValidationError(
                f"a grant may only ever be issued for {GATE_1_ID!r}, got {self.gate_id!r}"
            )
        if self.period_start > self.period_end:
            raise LockboxValidationError("period_start must not be after period_end")


def derive_state(events: Sequence[LockboxEvent]) -> LockboxState:
    """Fold a lockbox's event history into its current :class:`LockboxState`.

    Pure and order-insensitive over its inputs: presence of any ``BURNED`` event anywhere in
    the history means BURNED (an absorbing state — nothing ever removes a ``BURNED`` event or
    reverses its effect); otherwise a ``DEFINED`` event means SEALED. An empty sequence, or one
    with no ``DEFINED`` event at all, is not a valid lockbox history.
    """
    if not events:
        raise LockboxValidationError("cannot derive a lockbox state from an empty event log")
    if not any(event.kind is LockboxEventKind.DEFINED for event in events):
        raise LockboxValidationError("event log has no DEFINED event; not a valid lockbox history")
    if any(event.kind is LockboxEventKind.BURNED for event in events):
        return LockboxState.BURNED
    return LockboxState.SEALED


class LockboxRegistry:
    """Append-only permission-and-audit registry for lockbox holdout periods (SPEC-092).

    Public surface is deliberately five read/append methods and nothing else: :meth:`define`,
    :meth:`access`, :meth:`state`, :meth:`is_uncontaminated`, :meth:`access_log`. There is no
    update or delete method — a burned lockbox stays burned, and a defined lockbox's period can
    never be edited, only superseded by defining a fresh ``lockbox_id`` once the old one is
    burned.
    """

    def __init__(self) -> None:
        # The only mutable state this registry holds: each lockbox's own append-only event
        # list. Every other fact (state, contamination, period) is derived from this log on
        # every call, never cached or written back.
        self._log: dict[str, list[LockboxEvent]] = {}

    def define(self, definition: LockboxDefinition) -> None:
        """Seal a new lockbox. Refuses a duplicate id or a second concurrently-SEALED one."""
        if definition.lockbox_id in self._log:
            raise LockboxDefinitionError(
                f"lockbox_id {definition.lockbox_id!r} has already been defined in this "
                "registry (burned or not); a lockbox_id is never reused"
            )
        for other_id, other_events in self._log.items():
            if derive_state(tuple(other_events)) is LockboxState.SEALED:
                raise LockboxDefinitionError(
                    f"cannot define {definition.lockbox_id!r}: {other_id!r} is currently "
                    "SEALED; only one holdout period may be sealed at a time"
                )
        defined_event = LockboxEvent(
            lockbox_id=definition.lockbox_id,
            kind=LockboxEventKind.DEFINED,
            at=definition.defined_at,
            period_start=definition.period_start,
            period_end=definition.period_end,
            defined_by=definition.defined_by,
            accessor=None,
            purpose=None,
            gate_id=None,
            burn_reason=None,
        )
        self._log[definition.lockbox_id] = [defined_event]

    def access(
        self,
        lockbox_id: str,
        *,
        accessor: str,
        purpose: str,
        gate_id: str,
        at: DualClockTimestamp,
    ) -> LockboxAccessGrant:
        """Request access to a lockbox. Log-then-grant: the attempt is always recorded first.

        Returns a :class:`LockboxAccessGrant` ONLY when ``gate_id`` is :data:`GATE_1_ID` and the
        lockbox was SEALED at the moment of this call — and that permitted read still burns the
        lockbox (``GATE1_EVALUATION_CONSUMED``), because Gate 1 evaluation is the one and only
        permitted read (SPEC-092, §9.7). Every other outcome — a non-GATE-1 ``gate_id`` on a
        SEALED lockbox (burns it as ``UNAUTHORIZED_ACCESS`` and raises), or any access at all on
        an already-BURNED lockbox (logged, refused, no further state change) — raises
        :class:`LockboxBurnedError` after the access has already been appended to the log.
        """
        _require_nonempty(accessor, "accessor")
        _require_nonempty(purpose, "purpose")
        _require_nonempty(gate_id, "gate_id")
        events = self._log.get(lockbox_id)
        if events is None:
            raise LockboxNotFoundError(f"no lockbox has been defined with id {lockbox_id!r}")

        # Log-then-grant (SPEC-092's core ordering requirement): this ACCESSED event is
        # appended before any grant/refusal decision below, so it is present in the audit
        # trail even on the branch that raises.
        events.append(
            LockboxEvent(
                lockbox_id=lockbox_id,
                kind=LockboxEventKind.ACCESSED,
                at=at,
                period_start=None,
                period_end=None,
                defined_by=None,
                accessor=accessor,
                purpose=purpose,
                gate_id=gate_id,
                burn_reason=None,
            )
        )

        if derive_state(tuple(events)) is LockboxState.BURNED:
            raise LockboxBurnedError(
                f"lockbox {lockbox_id!r} is already burned; access is logged and refused"
            )

        defined_event = events[0]
        assert defined_event.period_start is not None and defined_event.period_end is not None

        if gate_id == GATE_1_ID:
            events.append(
                LockboxEvent(
                    lockbox_id=lockbox_id,
                    kind=LockboxEventKind.BURNED,
                    at=at,
                    period_start=None,
                    period_end=None,
                    defined_by=None,
                    accessor=None,
                    purpose=None,
                    gate_id=None,
                    burn_reason=BurnReason.GATE1_EVALUATION_CONSUMED,
                )
            )
            return LockboxAccessGrant(
                lockbox_id=lockbox_id,
                period_start=defined_event.period_start,
                period_end=defined_event.period_end,
                accessor=accessor,
                purpose=purpose,
                gate_id=gate_id,
                at=at,
            )

        events.append(
            LockboxEvent(
                lockbox_id=lockbox_id,
                kind=LockboxEventKind.BURNED,
                at=at,
                period_start=None,
                period_end=None,
                defined_by=None,
                accessor=None,
                purpose=None,
                gate_id=None,
                burn_reason=BurnReason.UNAUTHORIZED_ACCESS,
            )
        )
        raise LockboxBurnedError(
            f"lockbox {lockbox_id!r} accessed with gate_id {gate_id!r} != {GATE_1_ID!r}; "
            "an unauthorized inspection is logged, refused, and burns the lockbox"
        )

    def state(self, lockbox_id: str) -> LockboxState:
        """The lockbox's current state, derived fresh from its event log every call."""
        return derive_state(self.access_log(lockbox_id))

    def is_uncontaminated(self, lockbox_id: str) -> bool:
        """True iff SEALED with zero prior access events — GATE-1's deterministic input.

        This is the exact fact ``specs/gates/v1.yaml``'s ``GATE-1.lockbox_uncontaminated``
        checklist item attests: a lockbox that has ever been accessed (granted, refused, or
        burned) is never uncontaminated again, even if somehow still SEALED (which cannot
        actually happen in this module — every access burns — but the check is written against
        the access history directly, not against the state, so it stays correct even if the
        state-transition rule were ever revised).
        """
        events = self.access_log(lockbox_id)
        never_accessed = not any(event.kind is LockboxEventKind.ACCESSED for event in events)
        return derive_state(events) is LockboxState.SEALED and never_accessed

    def access_log(self, lockbox_id: str) -> tuple[LockboxEvent, ...]:
        """The full immutable event history for one lockbox, in append order."""
        events = self._log.get(lockbox_id)
        if events is None:
            raise LockboxNotFoundError(f"no lockbox has been defined with id {lockbox_id!r}")
        return tuple(events)
