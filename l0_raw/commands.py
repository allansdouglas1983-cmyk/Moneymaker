"""API command log and persist-before-send gateway (SPEC-003, money).

Every outbound command is persisted BEFORE it is sent, never after. The command is logged as
two append-only events (SPECIFICATION.md §6.2, "both clocks on both events"): a send event
written before the transport call, and a response event written after. If the send event
cannot be persisted, the transport is never invoked — the command fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol

from l0_raw.clock import Clock
from l0_raw.records import (
    ApiCommandResponseEvent,
    ApiCommandSendEvent,
    decode,
    response_to_frame,
    send_to_frame,
    sha256_hex,
)
from l0_raw.store import AppendOnlyLog


class JournalWriteError(Exception):
    """Raised when a command event cannot be durably persisted."""


class CommandTransport(Protocol):
    """Anything that can send a command payload and return a response payload."""

    def send(self, payload: bytes) -> bytes: ...


@dataclass(frozen=True)
class CommandIntent:
    command_id: str
    customer_ref: str
    customer_order_ref: str
    signal_id: str
    payload: bytes
    process_version: str
    retry_parent_id: str | None = None


class ApiCommandJournal:
    """Append-only journal of API command send/response events (SPEC-003)."""

    def __init__(self, log: AppendOnlyLog) -> None:
        self._log = log

    def record_send(self, event: ApiCommandSendEvent) -> None:
        meta, payload = send_to_frame(event)
        self._log.append(meta, payload)

    def record_response(self, event: ApiCommandResponseEvent) -> None:
        meta, payload = response_to_frame(event)
        self._log.append(meta, payload)

    def read(self) -> Iterator[ApiCommandSendEvent | ApiCommandResponseEvent]:
        for meta, payload in self._log.read():
            event = decode(meta, payload)
            if isinstance(event, (ApiCommandSendEvent, ApiCommandResponseEvent)):
                yield event


class CommandGateway:
    """Sends commands only after their send event is durably persisted (SPEC-003)."""

    def __init__(self, *, journal: ApiCommandJournal, transport: CommandTransport, clock: Clock) -> None:
        self._journal = journal
        self._transport = transport
        self._clock = clock

    def send(self, intent: CommandIntent) -> bytes:
        send_event = ApiCommandSendEvent(
            command_id=intent.command_id,
            customer_ref=intent.customer_ref,
            customer_order_ref=intent.customer_order_ref,
            signal_id=intent.signal_id,
            payload_hash=sha256_hex(intent.payload),
            local_send_time=self._clock.now(),
            retry_parent_id=intent.retry_parent_id,
            process_version=intent.process_version,
        )
        # SPEC-003: persist BEFORE sending. If this raises, the command is NOT sent.
        self._journal.record_send(send_event)

        response_payload = self._transport.send(intent.payload)

        self._journal.record_response(
            ApiCommandResponseEvent(
                command_id=intent.command_id,
                response_time=self._clock.now(),
                response_payload=response_payload,
            )
        )
        return response_payload
