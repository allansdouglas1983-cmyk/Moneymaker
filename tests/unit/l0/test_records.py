"""Unit tests for l0_raw.records (SPEC-001 payloads/checksums, SPEC-003 api-command frames)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from l0_raw import clock
from l0_raw import records as r


def _stamp() -> clock.ClockStamp:
    return clock.ClockStamp(
        wall_utc=datetime(2026, 7, 15, tzinfo=timezone.utc), monotonic_ns=42, domain_fingerprint="h1:b1:1"
    )


def _capture(seq: int = 0) -> r.CaptureMeta:
    return r.CaptureMeta(
        host_id="h1",
        boot_id="b1",
        process_id=1,
        capture_sequence=seq,
        process_start_utc=datetime(2026, 7, 15, tzinfo=timezone.utc),
        monotonic_origin_ns=1000,
        raw_partition_id="market/2026-07-15/conn-1",
        raw_partition_hash="deadbeef",
    )


def _market(payload: bytes) -> r.RawMarketRecord:
    return r.RawMarketRecord(
        payload_bytes=payload,
        publish_time=datetime(2026, 7, 15, tzinfo=timezone.utc),
        receive=_stamp(),
        stream_clock="7",
        connection_id="conn-1",
        subscription_hash="subhash",
        conflation_settings="none",
        schema_version="mcm-v1",
        checksum=r.sha256_hex(payload),
        capture=_capture(),
    )


@pytest.mark.spec("SPEC-001")
def test_checksum_matches_payload() -> None:
    payload = b"\x00\x01\x02abc\xff"
    rec = _market(payload)
    assert rec.checksum == r.sha256_hex(payload)


@pytest.mark.spec("SPEC-001")
def test_market_frame_roundtrip_preserves_payload() -> None:
    payload = bytes(range(256))
    rec = _market(payload)
    meta, frame_payload = r.market_to_frame(rec)
    assert frame_payload == payload
    back = r.market_from_frame(meta, frame_payload)
    assert back == rec
    assert back.payload_bytes == payload


@pytest.mark.spec("SPEC-001")
def test_market_from_frame_detects_corruption() -> None:
    rec = _market(b"original")
    meta, _ = r.market_to_frame(rec)
    with pytest.raises(ValueError):
        r.market_from_frame(meta, b"tampered")


@pytest.mark.spec("SPEC-001")
def test_order_frame_roundtrip() -> None:
    payload = b"\x10\x20order"
    rec = r.RawOrderRecord(
        payload_bytes=payload,
        publish_time=None,
        receive=_stamp(),
        stream_clock=None,
        connection_id="conn-2",
        checksum=r.sha256_hex(payload),
        capture=_capture(3),
    )
    meta, frame_payload = r.order_to_frame(rec)
    assert r.order_from_frame(meta, frame_payload) == rec


@pytest.mark.spec("SPEC-003")
def test_api_send_frame_roundtrip() -> None:
    ev = r.ApiCommandSendEvent(
        command_id="cmd-1",
        customer_ref="cref",
        customer_order_ref="coref",
        signal_id="sig-1",
        payload_hash=r.sha256_hex(b"payload"),
        local_send_time=_stamp(),
        retry_parent_id=None,
        process_version="proc-v1",
    )
    meta, payload = r.send_to_frame(ev)
    assert payload == b""
    assert r.send_from_frame(meta, payload) == ev
    assert r.decode(meta, payload) == ev


@pytest.mark.spec("SPEC-003")
def test_api_response_frame_roundtrip_with_and_without_payload() -> None:
    with_payload = r.ApiCommandResponseEvent(
        command_id="cmd-1", response_time=_stamp(), response_payload=b"\x01ok"
    )
    meta, payload = r.response_to_frame(with_payload)
    assert payload == b"\x01ok"
    assert r.response_from_frame(meta, payload) == with_payload

    without = r.ApiCommandResponseEvent(command_id="cmd-2", response_time=_stamp(), response_payload=None)
    meta2, payload2 = r.response_to_frame(without)
    assert payload2 == b""
    assert r.response_from_frame(meta2, payload2) == without
