# Intended repo path: l0_raw/backfill.py
"""Backfill-provenance raw record — sibling of records.py for historical ingestion (SPEC-023).

``RawMarketRecord`` (records.py) is a *live-capture* contract: it carries a live stream
connection id, subscription hash, conflation settings and a ``CaptureMeta`` tied to a running
process/boot/connection identity. A Betfair historical (bz2) file was never captured by a live
subscription — there is no connection, no subscription hash, no live conflation setting, and no
running-process ``CaptureMeta`` to attach. Reusing ``RawMarketRecord`` for backfilled data would
force fabricating those fields (a silent lie) or nulling them out (an implicit, undeclared
special case). SPEC-023 requires the opposite: backfilled data must be **visibly** distinct from
a live capture, and must declare its own true publication time rather than borrowing SPEC-004's
receive-time semantics.

``BackfillMarketRecord`` is that sibling type. It keeps the parts of records.py's contract that
still apply verbatim (payload stored byte-for-byte, sha256 checksum verified on read, frozen
Pydantic v2 model, the same ``(metadata dict, payload bytes)`` framing consumed by
``l0_raw.store.AppendOnlyLog``) and replaces the live-only fields with backfill provenance:

- ``true_publication_time_ms``: the message's own ``pt`` field (epoch milliseconds) — SPEC-023's
  declared true publication time. This is a fact about when Betfair published the message, not
  about when this tool ran.
- ``BackfillProvenance``: SPEC-004-style dual clock (``ingested_at_utc`` +
  ``ingested_at_monotonic_ns``) but describing the *ingestion* instant, kept in fields separate
  from and never conflated with ``true_publication_time_ms``. Plus the manifest/source lineage
  that makes an ingested record traceable back to an exact byte-verified input file.

A ``BackfillMarketRecord`` is never decoded as a ``RawMarketRecord`` or vice versa: the
``record_type`` tag ("backfill_market" vs "market") makes the two types mutually exclusive at
the framing layer, so a reducer or evidence consumer cannot accidentally treat backfilled data as
a live capture (or vice versa).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from l0_raw.records import sha256_hex

# Bump this only alongside a review of every already-ingested corpus; changing what a backfill
# record means retroactively degrades every conclusion drawn from it (see CLAUDE.md rule 1).
BACKFILL_RECORD_SCHEMA_VERSION = "backfill-market-v1"


class BackfillProvenance(BaseModel):
    """Provenance recorded with every backfill-ingested raw record (SPEC-023).

    ``provenance`` is a closed literal, not a free-form string: today only "backfilled" values
    exist, and a future live-equivalent path (if ever added) would be a different literal, never
    a plain reinterpretation of this one.
    """

    model_config = ConfigDict(frozen=True)

    provenance: Literal["backfilled"]
    source_file: str
    source_line: int
    source_file_sha256: str
    manifest_digest: str
    ingest_tool_version: str
    ingested_at_utc: datetime
    ingested_at_monotonic_ns: int


class BackfillMarketRecord(BaseModel):
    """One historical Exchange-Stream ``mcm`` line, ingested with backfill provenance (SPEC-023).

    ``payload_bytes`` is the source file's line, byte-for-byte, exactly as it appeared on disk —
    no re-serialisation, no key reordering, no whitespace normalisation (SPEC-001 semantics
    extended to the backfill path). ``true_publication_time_ms`` is parsed *from* those bytes for
    indexing/reporting purposes only; the bytes themselves, not the parsed value, are what later
    consumers must treat as authoritative.
    """

    model_config = ConfigDict(frozen=True)

    payload_bytes: bytes
    true_publication_time_ms: int
    checksum: str
    schema_version: str
    provenance: BackfillProvenance


def _strip(meta: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in meta.items() if k not in keys}


def backfill_market_to_frame(record: BackfillMarketRecord) -> tuple[dict[str, Any], bytes]:
    """Split a record into ``(metadata, payload_bytes)`` for ``AppendOnlyLog.append``."""
    meta = record.model_dump(mode="json", exclude={"payload_bytes"})
    meta["record_type"] = "backfill_market"
    return meta, record.payload_bytes


def backfill_market_from_frame(meta: dict[str, Any], payload: bytes) -> BackfillMarketRecord:
    """Reconstruct a record from a stored frame, re-verifying its checksum (SPEC-001 semantics)."""
    if meta.get("checksum") != sha256_hex(payload):
        raise ValueError(
            f"checksum mismatch for backfill record (source {meta.get('provenance')})"
        )
    return BackfillMarketRecord(payload_bytes=payload, **_strip(meta, "record_type"))


def decode_backfill(meta: dict[str, Any], payload: bytes) -> BackfillMarketRecord:
    """Type-checked decode: refuses a frame whose ``record_type`` is not "backfill_market".

    This is the guard that keeps a live ``RawMarketRecord`` frame from ever being silently
    reinterpreted as backfilled data (or vice versa) if the two record types ever share a log.
    """
    record_type = meta.get("record_type")
    if record_type != "backfill_market":
        raise ValueError(
            f"expected record_type 'backfill_market', got {record_type!r} "
            "(a live RawMarketRecord frame cannot be decoded as backfill provenance)"
        )
    return backfill_market_from_frame(meta, payload)
