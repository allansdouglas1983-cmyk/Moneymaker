"""A3 (conceptual audit F-04, founder order #2): replay must handle backfilled corpora.

`replay_from_log` filtered `record_type == "market"` only, so an L0 log produced by
`tools/ingest_historical.py` (every frame `backfill_market`) replayed to an EMPTY universe
with no error — a silent disappearance, contrary to the refuse-don't-degrade posture, and it
meant no backfilled historical corpus (racing pilot or tennis pilot) could flow through the
SPEC-011 replay path at all. Pins:

* a backfill-only log replays to exactly the direct reduction of its payload bytes;
* a mixed live+backfill log reduces every market frame in append order (reduction is
  provenance-agnostic byte folding — provenance discipline lives at L3 via SPEC-023's
  registry, never by silently dropping frames here);
* non-market record types (e.g. an order frame) are still excluded;
* a log yielding ZERO market frames is a typed refusal, never an empty result.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from l0_raw.backfill import (
    BACKFILL_RECORD_SCHEMA_VERSION,
    BackfillMarketRecord,
    BackfillProvenance,
    backfill_market_to_frame,
)
from l0_raw.records import sha256_hex
from l0_raw.store import AppendOnlyLog
from l1_reduce.mcm_v1 import REDUCER_VERSION
from l1_reduce.reducer import reduce
from l1_reduce.replay import EmptyReplayError, replay_from_log

pytestmark = [pytest.mark.spec("SPEC-011"), pytest.mark.spec("SPEC-023")]

_LINES: list[bytes] = [
    json.dumps(
        {
            "op": "mcm",
            "pt": 1000,
            "mc": [
                {
                    "id": "1.202",
                    "img": True,
                    "marketDefinition": {
                        "status": "OPEN",
                        "inPlay": False,
                        "version": 1,
                        "runners": [
                            {"id": 11, "status": "ACTIVE", "sortPriority": 1},
                            {"id": 22, "status": "ACTIVE", "sortPriority": 2},
                        ],
                    },
                    "rc": [{"id": 11, "batb": [[0, 2.5, 20]], "ltp": 2.5}],
                }
            ],
        }
    ).encode("utf-8"),
    json.dumps(
        {"op": "mcm", "pt": 2000, "mc": [{"id": "1.202", "rc": [{"id": 22, "batb": [[0, 3.0, 15]], "ltp": 3.0}]}]}
    ).encode("utf-8"),
]


def _backfill_record(line: bytes, source_line: int, pt: int) -> BackfillMarketRecord:
    return BackfillMarketRecord(
        payload_bytes=line,
        true_publication_time_ms=pt,
        checksum=sha256_hex(line),
        schema_version=BACKFILL_RECORD_SCHEMA_VERSION,
        provenance=BackfillProvenance(
            provenance="backfilled",
            source_file="1.202.bz2",
            source_line=source_line,
            source_file_sha256=sha256_hex(b"file-bytes"),
            manifest_digest="sha256:" + sha256_hex(b"manifest"),
            ingest_tool_version="ingest-historical-v1",
            ingested_at_utc=datetime(2026, 7, 17, tzinfo=timezone.utc),
            ingested_at_monotonic_ns=1,
        ),
    )


def _backfill_log(tmp_path: Path) -> AppendOnlyLog:
    log = AppendOnlyLog(tmp_path / "backfill.l0")
    for i, line in enumerate(_LINES):
        meta, payload = backfill_market_to_frame(_backfill_record(line, i + 1, 1000 * (i + 1)))
        log.append(meta, payload)
    return log


def test_backfill_only_log_replays_to_direct_reduction(tmp_path: Path) -> None:
    log = _backfill_log(tmp_path)
    replayed = replay_from_log(log, REDUCER_VERSION)
    direct = reduce(_LINES, REDUCER_VERSION)
    assert replayed.canonical_bytes == direct.canonical_bytes
    assert replayed.canonical_hash == direct.canonical_hash


def test_mixed_log_reduces_all_market_frames_in_append_order(tmp_path: Path) -> None:
    log = AppendOnlyLog(tmp_path / "mixed.l0")
    log.append({"record_type": "market"}, _LINES[0])
    meta, payload = backfill_market_to_frame(_backfill_record(_LINES[1], 2, 2000))
    log.append(meta, payload)
    replayed = replay_from_log(log, REDUCER_VERSION)
    direct = reduce(_LINES, REDUCER_VERSION)
    assert replayed.canonical_hash == direct.canonical_hash


def test_non_market_record_types_are_still_excluded(tmp_path: Path) -> None:
    log = AppendOnlyLog(tmp_path / "with-order.l0")
    log.append({"record_type": "market"}, _LINES[0])
    log.append({"record_type": "order"}, b'{"op":"ocm"}')
    log.append({"record_type": "market"}, _LINES[1])
    replayed = replay_from_log(log, REDUCER_VERSION)
    direct = reduce(_LINES, REDUCER_VERSION)
    assert replayed.canonical_hash == direct.canonical_hash


def test_zero_market_frames_is_a_typed_refusal_never_an_empty_result(tmp_path: Path) -> None:
    empty = AppendOnlyLog(tmp_path / "empty.l0")
    with pytest.raises(EmptyReplayError):
        replay_from_log(empty, REDUCER_VERSION)

    orders_only = AppendOnlyLog(tmp_path / "orders.l0")
    orders_only.append({"record_type": "order"}, b'{"op":"ocm"}')
    with pytest.raises(EmptyReplayError):
        replay_from_log(orders_only, REDUCER_VERSION)
