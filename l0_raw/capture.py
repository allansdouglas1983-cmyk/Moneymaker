"""Raw stream capture (SPEC-001 market, SPEC-002 order).

Persists each message exactly as received, append-only, assigning a monotonically increasing
``capture_sequence``. Never deduplicates or reorders, so duplicate and out-of-order messages
are retained unmodified (SPEC-002).
"""
from __future__ import annotations

from datetime import datetime

from l0_raw.clock import Clock
from l0_raw.records import (
    CaptureMeta,
    RawMarketRecord,
    RawOrderRecord,
    market_to_frame,
    order_to_frame,
    sha256_hex,
)
from l0_raw.store import AppendOnlyLog


class RawStreamCapture:
    def __init__(self, *, clock: Clock, log: AppendOnlyLog, partition_id: str) -> None:
        self._clock = clock
        self._log = log
        self._partition_id = partition_id
        self._partition_hash = sha256_hex(partition_id.encode("utf-8"))
        self._sequence = 0

    @property
    def log(self) -> AppendOnlyLog:
        return self._log

    def _next_capture_meta(self) -> CaptureMeta:
        domain = self._clock.domain
        meta = CaptureMeta(
            host_id=domain.host_id,
            boot_id=domain.boot_id,
            process_id=domain.process_id,
            capture_sequence=self._sequence,
            process_start_utc=domain.process_start_utc,
            monotonic_origin_ns=domain.monotonic_origin_ns,
            raw_partition_id=self._partition_id,
            raw_partition_hash=self._partition_hash,
        )
        self._sequence += 1
        return meta

    def capture_market(
        self,
        payload: bytes,
        *,
        publish_time: datetime | None,
        stream_clock: str | None,
        connection_id: str,
        subscription_hash: str,
        conflation_settings: str,
        schema_version: str,
    ) -> RawMarketRecord:
        record = RawMarketRecord(
            payload_bytes=payload,
            publish_time=publish_time,
            receive=self._clock.now(),
            stream_clock=stream_clock,
            connection_id=connection_id,
            subscription_hash=subscription_hash,
            conflation_settings=conflation_settings,
            schema_version=schema_version,
            checksum=sha256_hex(payload),
            capture=self._next_capture_meta(),
        )
        meta, frame_payload = market_to_frame(record)
        self._log.append(meta, frame_payload)
        return record

    def capture_order(
        self,
        payload: bytes,
        *,
        publish_time: datetime | None,
        stream_clock: str | None,
        connection_id: str,
    ) -> RawOrderRecord:
        record = RawOrderRecord(
            payload_bytes=payload,
            publish_time=publish_time,
            receive=self._clock.now(),
            stream_clock=stream_clock,
            connection_id=connection_id,
            checksum=sha256_hex(payload),
            capture=self._next_capture_meta(),
        )
        meta, frame_payload = order_to_frame(record)
        self._log.append(meta, frame_payload)
        return record
