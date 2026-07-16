"""SPEC-001/002 audit-gap tests: order-stream corruption detection, per-append fsync, and the
stream clock as an opaque token.

2026-07-16 retrospective audit. The Betfair stream clock (``clk``/``initialClk``) is an opaque
*string* token on the wire, not an integer — typing it ``int`` would reject real stream data at
the first live integration. No persisted data exists yet, so widening the type now is free.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from l0_raw import clock
from l0_raw import records as r
from l0_raw.store import AppendOnlyLog

pytestmark = [pytest.mark.spec("SPEC-001"), pytest.mark.spec("SPEC-002")]


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


def _order(payload: bytes, stream_clock: str | None = None) -> r.RawOrderRecord:
    return r.RawOrderRecord(
        payload_bytes=payload,
        publish_time=None,
        receive=_stamp(),
        stream_clock=stream_clock,
        connection_id="conn-2",
        checksum=r.sha256_hex(payload),
        capture=_capture(3),
    )


def test_order_from_frame_detects_corruption() -> None:
    # Mirrors the market-stream corruption test; previously only the market variant existed.
    rec = _order(b"original")
    meta, _ = r.order_to_frame(rec)
    with pytest.raises(ValueError):
        r.order_from_frame(meta, b"tampered")


def test_stream_clock_is_an_opaque_string_token() -> None:
    market = r.RawMarketRecord(
        payload_bytes=b"{}",
        publish_time=None,
        receive=_stamp(),
        stream_clock="AAAAF9uX0w==",  # a realistic Betfair clk token; base64, not an integer
        connection_id="conn-1",
        subscription_hash="subhash",
        conflation_settings="none",
        schema_version="mcm-v1",
        checksum=r.sha256_hex(b"{}"),
        capture=_capture(),
    )
    assert market.stream_clock == "AAAAF9uX0w=="
    order = _order(b"{}", stream_clock="AJ7B0w==")
    assert order.stream_clock == "AJ7B0w=="


def test_every_append_fsyncs_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Durability is per append, not per log lifetime: each append must fsync. Previously only
    # the one-time directory fsync was spy-verified.
    calls: list[int] = []
    real_fsync = os.fsync

    def spy(fd: int) -> None:
        calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", spy)
    log = AppendOnlyLog(tmp_path / "log.l0")
    before = len(calls)
    log.append({"a": 1}, b"x")
    after_first = len(calls)
    log.append({"a": 2}, b"y")
    after_second = len(calls)
    assert after_first - before >= 1
    assert after_second - after_first >= 1
