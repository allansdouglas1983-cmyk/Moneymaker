"""Structural pre-lockbox outcome-field guard (Stage-2A).

SPEC-092's lockbox (``l8_evidence.lockbox``) records WHO opened the holdout and WHEN, but
its docstring is explicit that **data-layer blocking is deferred** — nothing structurally
stops a pre-lockbox reader (a feature builder, a price reconstructor) from reading the
field that encodes the winner. This module supplies that missing structural block, on the
same discipline as the SPEC-021 BSP-leakage guard (``l3_features.leakage.assert_no_bsp``):

* a frozen, conservative classification of EVERY corpus field (the authoritative copy of
  ``specs/evidence/outcome-field-classification-v1.yaml``; a sync test pins them equal);
* ``assert_pre_lockbox_readable`` — raises ``OutcomeFieldAccessError`` for anything not
  provably safe, so accidental contamination is a hard error, not a silent read;
* value-level sentinels for the fields that are field-safe but whose specific values mark
  the off / settlement boundary (``status == CLOSED``, ``inPlay == True``,
  ``runner.status ∈ {WINNER, LOSER, REMOVED}``, ``bspReconciled == True``);
* ``PreLockboxAccessRecorder`` — an append-only, order-independent record of exactly which
  field classes a pre-lockbox reader touched, whose ``content_digest`` makes a replay
  **prove** no prohibited field was accessed (the manifest cannot, by construction, contain
  a non-safe field, because ``record`` routes through the guard).

FAIL CLOSED: any field not in the registry is ``UNKNOWN`` and NOT pre-lockbox-safe. A new
field in a future corpus month is therefore refused until a governed v2 classifies it.

Pure module: no I/O, no clock, no float. It classifies and guards; it does not read the
corpus (the reader that USES the recorder does), and it never touches the lockbox registry
(that stays the permission/audit authority).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum, unique

__all__ = [
    "CLASSIFICATION_VERSION",
    "OutcomeFieldClass",
    "OutcomeFieldAccessError",
    "FieldAccess",
    "PreLockboxAccessRecorder",
    "ALL_CLASSIFIED_FIELDS",
    "classify",
    "is_pre_lockbox_safe",
    "assert_pre_lockbox_readable",
    "is_outcome_sentinel_value",
]

CLASSIFICATION_VERSION = "outcome-field-classification-v1"


@unique
class OutcomeFieldClass(Enum):
    SAFE_BEFORE_LOCKBOX = "SAFE_BEFORE_LOCKBOX"
    OUTCOME_CONTROLLED = "OUTCOME_CONTROLLED"
    POST_SETTLEMENT_ONLY = "POST_SETTLEMENT_ONLY"
    UNKNOWN = "UNKNOWN"


class OutcomeFieldAccessError(RuntimeError):
    """A pre-lockbox consumer attempted to read a field that is not provably safe before
    the lockbox authorises outcome access. Refusal is the only correct behaviour."""


# Authoritative classification — MUST equal specs/evidence/outcome-field-classification-v1.yaml
# (tests/unit/l8/test_outcome_fields.py::TestSpecSync). Keyed (level, field).
_S = OutcomeFieldClass.SAFE_BEFORE_LOCKBOX
_O = OutcomeFieldClass.OUTCOME_CONTROLLED
_P = OutcomeFieldClass.POST_SETTLEMENT_ONLY

_CLASSIFICATION: dict[tuple[str, str], OutcomeFieldClass] = {
    # top-level mcm envelope
    ("top", "op"): _S, ("top", "clk"): _S, ("top", "pt"): _S, ("top", "mc"): _S,
    # mc[]
    ("mc", "id"): _S, ("mc", "img"): _S, ("mc", "marketDefinition"): _S,
    ("mc", "rc"): _S, ("mc", "tv"): _S,
    # marketDefinition
    ("marketDefinition", "betDelay"): _S,
    ("marketDefinition", "bettingType"): _S,
    ("marketDefinition", "bspMarket"): _S,
    ("marketDefinition", "bspReconciled"): _O,
    ("marketDefinition", "complete"): _S,
    ("marketDefinition", "countryCode"): _S,
    ("marketDefinition", "crossMatching"): _S,
    ("marketDefinition", "discountAllowed"): _S,
    ("marketDefinition", "eventId"): _S,
    ("marketDefinition", "eventName"): _S,
    ("marketDefinition", "eventTypeId"): _S,
    ("marketDefinition", "inPlay"): _S,
    ("marketDefinition", "marketBaseRate"): _S,
    ("marketDefinition", "marketTime"): _S,
    ("marketDefinition", "marketType"): _S,
    ("marketDefinition", "name"): _S,
    ("marketDefinition", "numberOfActiveRunners"): _S,
    ("marketDefinition", "numberOfWinners"): _S,
    ("marketDefinition", "openDate"): _S,
    ("marketDefinition", "persistenceEnabled"): _S,
    ("marketDefinition", "regulators"): _S,
    ("marketDefinition", "runners"): _S,
    ("marketDefinition", "runnersVoidable"): _S,
    ("marketDefinition", "status"): _S,
    ("marketDefinition", "settledTime"): _P,
    ("marketDefinition", "suspendTime"): _S,
    ("marketDefinition", "timezone"): _S,
    ("marketDefinition", "turnInPlayEnabled"): _S,
    ("marketDefinition", "version"): _S,
    # marketDefinition.runners[]
    ("runner", "id"): _S,
    ("runner", "name"): _S,
    ("runner", "sortPriority"): _S,
    ("runner", "hc"): _S,
    ("runner", "status"): _O,
    ("runner", "adjustmentFactor"): _O,
    ("runner", "removalDate"): _O,
    # rc[]
    ("rc", "id"): _S, ("rc", "batb"): _S, ("rc", "batl"): _S, ("rc", "trd"): _S,
    ("rc", "ltp"): _S, ("rc", "tv"): _S, ("rc", "hc"): _S,
}

ALL_CLASSIFIED_FIELDS: tuple[tuple[str, str], ...] = tuple(sorted(_CLASSIFICATION))

# Value-level sentinels: field is class-safe but these VALUES mark the off/settlement
# boundary, so a pre-lockbox reader must refuse the whole line carrying them.
_SENTINELS: dict[tuple[str, str], frozenset[object]] = {
    ("marketDefinition", "status"): frozenset({"CLOSED"}),
    ("marketDefinition", "inPlay"): frozenset({True}),
    ("marketDefinition", "bspReconciled"): frozenset({True}),
    ("runner", "status"): frozenset({"WINNER", "LOSER", "REMOVED"}),
}


def classify(level: str, field: str) -> OutcomeFieldClass:
    """Classify a corpus field. Fail closed: unregistered => UNKNOWN."""
    return _CLASSIFICATION.get((level, field), OutcomeFieldClass.UNKNOWN)


def is_pre_lockbox_safe(level: str, field: str) -> bool:
    """True only for SAFE_BEFORE_LOCKBOX — UNKNOWN and every outcome class are unsafe."""
    return classify(level, field) is OutcomeFieldClass.SAFE_BEFORE_LOCKBOX


def assert_pre_lockbox_readable(level: str, field: str, *, context: str = "") -> None:
    """Raise unless the field is provably safe to read before lockbox opening."""
    cls = classify(level, field)
    if cls is not OutcomeFieldClass.SAFE_BEFORE_LOCKBOX:
        where = f" ({context})" if context else ""
        raise OutcomeFieldAccessError(
            f"pre-lockbox read of {level}.{field} refused{where}: classified {cls.value}. "
            "Outcome-controlled fields are reachable only through the authorised "
            "outcome-opening protocol at grading time."
        )


def is_outcome_sentinel_value(level: str, field: str, value: object) -> bool:
    """True if ``value`` is an off/settlement boundary marker for ``(level, field)``.

    Note bool/int identity: Betfair carries inPlay as a JSON bool, so membership uses
    equality; ``True`` matches the sentinel and ``1`` would too (Betfair never sends 1
    here, but equality keeps the guard conservative)."""
    return value in _SENTINELS.get((level, field), frozenset())


@dataclass(frozen=True)
class FieldAccess:
    """One recorded pre-lockbox field access. By construction ``field_class`` is always
    SAFE_BEFORE_LOCKBOX — the recorder refuses anything else."""

    level: str
    field: str
    field_class: OutcomeFieldClass


class PreLockboxAccessRecorder:
    """Append-only record of the distinct safe fields a pre-lockbox reader touched.

    ``record`` routes every access through :func:`assert_pre_lockbox_readable`, so the
    manifest can NEVER contain a non-safe field — a replay that reproduces the same digest
    thereby PROVES no prohibited field was accessed. The digest is order-independent (it is
    a function of the SET of distinct accesses), so two readers touching the same safe
    fields in any order agree."""

    def __init__(self) -> None:
        self._accessed: set[tuple[str, str]] = set()

    def record(self, level: str, field: str) -> None:
        assert_pre_lockbox_readable(level, field, context="PreLockboxAccessRecorder")
        self._accessed.add((level, field))

    def manifest(self) -> tuple[FieldAccess, ...]:
        return tuple(
            FieldAccess(level=lvl, field=fld, field_class=classify(lvl, fld))
            for lvl, fld in sorted(self._accessed)
        )

    def content_digest(self) -> str:
        body = json.dumps(
            {"version": CLASSIFICATION_VERSION, "accessed": sorted(self._accessed)},
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
