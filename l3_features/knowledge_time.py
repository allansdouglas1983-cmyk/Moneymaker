"""Knowledge-time semantics and backfill provenance (SPEC-020, SPEC-023).

Every feature carries the timestamps §6.3 distinguishes. A feature whose *first usable time*
is not provably before the market off is rejected at **build time with an error, not a
warning** (SPEC-020). A backfilled source must declare its true publication time, and a
backfill first-seen timestamp never confers earlier knowability than that publication time
(SPEC-023) — populating ``first_seen_ts`` during backfill does not make a retrospective file
historically valid.

This module contains no money logic; it is the evidence-integrity gate that keeps leakage out
of the model. See ``.claude/rules/evidence.md``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class LeakageError(Exception):
    """A feature is not provably knowable before the off, or claims impossible knowability.

    A build-time **error**, never a warning (SPEC-020). Deliberately not a ``ValueError``
    subclass: raised inside pydantic model validators it must propagate unwrapped (pydantic
    re-wraps only ``ValueError``/``AssertionError``), so callers catch a clean ``LeakageError``
    rather than a generic ``ValidationError``.
    """


class ProvenanceMode(str, Enum):
    """How a source's values became known to us (SPEC-023)."""

    LIVE_CAPTURED = "live_captured"
    BACKFILLED = "backfilled"


def _require_aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise LeakageError(f"{field} must be timezone-aware (UTC); got naive {value!r}")
    return value


def normalize_aware_datetimes_to_utc(data: Any) -> Any:
    """Rewrite every timezone-*aware* datetime in a construction mapping to UTC.

    The type rule is "Timestamps: UTC": two representations of the same instant
    (``13:00+00:00`` vs ``14:00+01:00``) must serialise — and therefore hash — identically
    (SPEC-024). Naive datetimes are deliberately left untouched so the model validators still
    reject them with a precise error rather than silently assuming a zone.
    """
    if not isinstance(data, dict):
        return data
    return {
        key: (
            value.astimezone(timezone.utc)
            if isinstance(value, datetime)
            and value.tzinfo is not None
            and value.tzinfo.utcoffset(value) is not None
            else value
        )
        for key, value in data.items()
    }


class SourceProvenance(BaseModel):
    """Provenance of a feature source (SPEC-023).

    A ``BACKFILLED`` source MUST declare ``true_publication_time`` — the instant the value was
    genuinely published by its provider — so that backfill cannot smuggle in a value that was
    not knowable before the off.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    mode: ProvenanceMode
    true_publication_time: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _utc_normalise(cls, data: Any) -> Any:
        return normalize_aware_datetimes_to_utc(data)

    @model_validator(mode="after")
    def _check_backfill_declares_publication(self) -> SourceProvenance:
        # LeakageError is not a ValueError, so it propagates from the validator unwrapped.
        if self.true_publication_time is not None:
            _require_aware(self.true_publication_time, "true_publication_time")
        if self.mode is ProvenanceMode.BACKFILLED and self.true_publication_time is None:
            raise LeakageError(
                f"backfilled source {self.source_id!r} must declare true_publication_time "
                "(SPEC-023: backfill does not confer historical validity)"
            )
        return self


class KnowledgeStamps(BaseModel):
    """The knowledge-time stamps §6.3 requires for every feature (SPEC-020).

    ``decision_time`` (when the model consumed the value) and ``correction_time`` (when a later
    revision arrived) are not known at feature-build time and default to ``None``.
    """

    model_config = ConfigDict(frozen=True)

    event_time: datetime
    source_publication_time: datetime
    provider_timestamp: datetime
    ingestion_receive_time: datetime
    first_usable_time: datetime
    decision_time: datetime | None = None
    correction_time: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _utc_normalise(cls, data: Any) -> Any:
        return normalize_aware_datetimes_to_utc(data)

    @model_validator(mode="after")
    def _all_aware(self) -> KnowledgeStamps:
        _require_aware(self.event_time, "event_time")
        _require_aware(self.source_publication_time, "source_publication_time")
        _require_aware(self.provider_timestamp, "provider_timestamp")
        _require_aware(self.ingestion_receive_time, "ingestion_receive_time")
        _require_aware(self.first_usable_time, "first_usable_time")
        if self.decision_time is not None:
            _require_aware(self.decision_time, "decision_time")
        if self.correction_time is not None:
            _require_aware(self.correction_time, "correction_time")
        # Coherence floors: a value cannot be usable before it was received or before its
        # provider published it. Declaring an earlier first_usable_time is an unprovable
        # knowability claim — the leakage semantics §6.3 warns about (SPEC-020).
        if self.first_usable_time < self.ingestion_receive_time:
            raise LeakageError(
                f"first_usable_time {self.first_usable_time!r} precedes ingestion_receive_time "
                f"{self.ingestion_receive_time!r}: a value cannot be usable before it was received"
            )
        if self.first_usable_time < self.source_publication_time:
            raise LeakageError(
                f"first_usable_time {self.first_usable_time!r} precedes source_publication_time "
                f"{self.source_publication_time!r}: a value cannot be knowable before it was published"
            )
        return self


def assert_knowable_before_off(
    stamps: KnowledgeStamps,
    market_off: datetime,
    *,
    source: SourceProvenance,
) -> None:
    """Reject a feature that is not provably knowable before ``market_off`` (SPEC-020).

    Raises :class:`LeakageError` (an error, never a warning) when:
      * ``market_off`` is timezone-naive (an unprovable boundary);
      * a backfilled source's ``first_usable_time`` precedes its true publication time — the
        backfill claims knowability the provider had not yet published (SPEC-023);
      * ``first_usable_time`` is not strictly before ``market_off`` — "provably before" is
        strict, so a value first usable at or after the off is out.
    """
    if market_off.tzinfo is None or market_off.tzinfo.utcoffset(market_off) is None:
        raise LeakageError(f"market_off must be timezone-aware (UTC); got naive {market_off!r}")

    if source.mode is ProvenanceMode.BACKFILLED:
        # Guarded by SourceProvenance's validator, but assert for the type checker and defence.
        true_pub = source.true_publication_time
        if true_pub is None:  # pragma: no cover - unreachable given the model validator
            raise LeakageError(
                f"backfilled source {source.source_id!r} has no true_publication_time"
            )
        if stamps.first_usable_time < true_pub:
            raise LeakageError(
                f"source {source.source_id!r}: first_usable_time {stamps.first_usable_time!r} "
                f"precedes true publication {true_pub!r}; backfill first-seen does not confer "
                "earlier knowability (SPEC-023)"
            )

    if not stamps.first_usable_time < market_off:
        raise LeakageError(
            f"first_usable_time {stamps.first_usable_time!r} is not provably before market off "
            f"{market_off!r}; the feature is rejected (SPEC-020)"
        )
