"""L0 record contracts and their append-log framing (SPEC-001/002/003).

Frozen Pydantic v2 models (§6.9: Pydantic at the persisted-contract boundary; L0 is
immutable). Each record serialises to ``(metadata dict, payload bytes)`` where the payload is
stored **verbatim** — no transform or normalisation (SPEC-001). Raw records verify their
``sha256`` checksum on read.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from l0_raw.clock import ClockStamp


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CaptureMeta(BaseModel):
    """Provenance recorded with every raw stream capture (SPECIFICATION.md §6.2)."""

    model_config = ConfigDict(frozen=True)

    host_id: str
    boot_id: str
    process_id: int
    capture_sequence: int
    process_start_utc: datetime
    monotonic_origin_ns: int
    raw_partition_id: str
    raw_partition_hash: str


class RawMarketRecord(BaseModel):
    """raw_market_stream (SPECIFICATION.md §6.1)."""

    model_config = ConfigDict(frozen=True)

    payload_bytes: bytes
    publish_time: datetime | None
    receive: ClockStamp
    stream_clock: int | None
    connection_id: str
    subscription_hash: str
    conflation_settings: str
    schema_version: str
    checksum: str
    capture: CaptureMeta


class RawOrderRecord(BaseModel):
    """raw_order_stream (SPECIFICATION.md §6.1 — fewer fields than the market stream)."""

    model_config = ConfigDict(frozen=True)

    payload_bytes: bytes
    publish_time: datetime | None
    receive: ClockStamp
    stream_clock: int | None
    connection_id: str
    checksum: str
    capture: CaptureMeta


class ApiCommandSendEvent(BaseModel):
    """api_command send event — persisted BEFORE the command is sent (SPEC-003)."""

    model_config = ConfigDict(frozen=True)

    command_id: str
    customer_ref: str
    customer_order_ref: str
    signal_id: str
    payload_hash: str
    send_time: ClockStamp
    retry_parent_id: str | None
    process_version: str


class ApiCommandResponseEvent(BaseModel):
    """api_command response event — persisted after the response arrives (SPEC-003)."""

    model_config = ConfigDict(frozen=True)

    command_id: str
    response_time: ClockStamp
    response_payload: bytes | None


def _strip(meta: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in meta.items() if k not in keys}


def market_to_frame(record: RawMarketRecord) -> tuple[dict[str, Any], bytes]:
    meta = record.model_dump(mode="json", exclude={"payload_bytes"})
    meta["record_type"] = "market"
    return meta, record.payload_bytes


def market_from_frame(meta: dict[str, Any], payload: bytes) -> RawMarketRecord:
    if meta.get("checksum") != sha256_hex(payload):
        raise ValueError(f"checksum mismatch for market record (partition {meta.get('capture')})")
    return RawMarketRecord(payload_bytes=payload, **_strip(meta, "record_type"))


def order_to_frame(record: RawOrderRecord) -> tuple[dict[str, Any], bytes]:
    meta = record.model_dump(mode="json", exclude={"payload_bytes"})
    meta["record_type"] = "order"
    return meta, record.payload_bytes


def order_from_frame(meta: dict[str, Any], payload: bytes) -> RawOrderRecord:
    if meta.get("checksum") != sha256_hex(payload):
        raise ValueError(f"checksum mismatch for order record (partition {meta.get('capture')})")
    return RawOrderRecord(payload_bytes=payload, **_strip(meta, "record_type"))


def send_to_frame(event: ApiCommandSendEvent) -> tuple[dict[str, Any], bytes]:
    meta = event.model_dump(mode="json")
    meta["record_type"] = "api_send"
    return meta, b""


def send_from_frame(meta: dict[str, Any], payload: bytes) -> ApiCommandSendEvent:
    del payload  # send events carry no payload bytes (only payload_hash)
    return ApiCommandSendEvent(**_strip(meta, "record_type"))


def response_to_frame(event: ApiCommandResponseEvent) -> tuple[dict[str, Any], bytes]:
    meta = event.model_dump(mode="json", exclude={"response_payload"})
    meta["record_type"] = "api_response"
    present = event.response_payload is not None
    meta["response_present"] = present
    return meta, (event.response_payload if event.response_payload is not None else b"")


def response_from_frame(meta: dict[str, Any], payload: bytes) -> ApiCommandResponseEvent:
    present = bool(meta.get("response_present", False))
    body = payload if present else None
    return ApiCommandResponseEvent(response_payload=body, **_strip(meta, "record_type", "response_present"))


def decode(
    meta: dict[str, Any], payload: bytes
) -> RawMarketRecord | RawOrderRecord | ApiCommandSendEvent | ApiCommandResponseEvent:
    """Reconstruct a typed record from a stored frame using its ``record_type``."""
    record_type = meta.get("record_type")
    if record_type == "market":
        return market_from_frame(meta, payload)
    if record_type == "order":
        return order_from_frame(meta, payload)
    if record_type == "api_send":
        return send_from_frame(meta, payload)
    if record_type == "api_response":
        return response_from_frame(meta, payload)
    raise ValueError(f"unknown record_type: {record_type!r}")
