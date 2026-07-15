"""Property tests for raw capture (SPEC-001 verbatim payload, SPEC-002 preserve every message)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l0_raw import records as r
from l0_raw.capture import RawStreamCapture
from l0_raw.clock import Clock, ClockDomain
from l0_raw.store import AppendOnlyLog


def _capture(tmp_path: Path) -> RawStreamCapture:
    domain = ClockDomain(
        host_id="h1",
        boot_id="b1",
        process_id=1,
        process_start_utc=datetime(2026, 7, 15, tzinfo=timezone.utc),
        monotonic_origin_ns=1000,
    )
    log = AppendOnlyLog(tmp_path / "log.l0")
    return RawStreamCapture(clock=Clock(domain), log=log, partition_id="market/2026-07-15/conn-1")


@pytest.mark.spec("SPEC-001")
@settings(max_examples=100)
@given(payload=st.binary(min_size=0, max_size=512))
def test_market_payload_stored_byte_exact(tmp_path_factory: pytest.TempPathFactory, payload: bytes) -> None:
    cap = _capture(tmp_path_factory.mktemp("cap"))
    rec = cap.capture_market(
        payload,
        publish_time=None,
        stream_clock=0,
        connection_id="conn-1",
        subscription_hash="s",
        conflation_settings="none",
        schema_version="mcm-v1",
    )
    # Stored verbatim, checksum is sha256 of the payload, and decode round-trips.
    assert rec.payload_bytes == payload
    assert rec.checksum == r.sha256_hex(payload)
    ((meta, frame),) = list(cap.log.read())
    assert frame == payload
    assert r.decode(meta, frame).payload_bytes == payload


@pytest.mark.spec("SPEC-002")
@settings(max_examples=60)
@given(payloads=st.lists(st.binary(min_size=0, max_size=32), min_size=0, max_size=20))
def test_every_message_preserved_in_order(
    tmp_path_factory: pytest.TempPathFactory, payloads: list[bytes]
) -> None:
    cap = _capture(tmp_path_factory.mktemp("cap"))
    for p in payloads:
        cap.capture_order(p, publish_time=None, stream_clock=None, connection_id="conn-2")
    stored = list(cap.log.read())
    # No dedup, no reorder, no loss — including duplicates.
    assert [frame for _, frame in stored] == payloads
    # capture_sequence is a dense increasing sequence.
    assert [m["capture"]["capture_sequence"] for m, _ in stored] == list(range(len(payloads)))
