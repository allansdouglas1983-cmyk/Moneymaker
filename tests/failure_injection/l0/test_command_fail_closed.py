"""Failure injection for SPEC-003: if the send event cannot be persisted, do NOT send."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from l0_raw.clock import Clock, ClockDomain
from l0_raw.commands import ApiCommandJournal, CommandGateway, CommandIntent, JournalWriteError
from l0_raw.records import ApiCommandSendEvent
from l0_raw.store import AppendOnlyLog

pytestmark = pytest.mark.spec("SPEC-003")


def _clock() -> Clock:
    return Clock(
        ClockDomain(
            host_id="h1",
            boot_id="b1",
            process_id=1,
            process_start_utc=datetime(2026, 7, 15, tzinfo=timezone.utc),
            monotonic_origin_ns=1000,
        )
    )


class _CountingTransport:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, payload: bytes) -> bytes:
        self.calls += 1
        return b"ok:" + payload


class _FailingSendJournal(ApiCommandJournal):
    """A journal whose send-event persistence always fails."""

    def record_send(self, event: ApiCommandSendEvent) -> None:
        raise JournalWriteError(f"disk full while persisting {event.command_id}")


def _intent() -> CommandIntent:
    return CommandIntent(
        command_id="cmd-1",
        customer_ref="cref",
        customer_order_ref="coref",
        signal_id="sig",
        payload=b"payload",
        process_version="proc-v1",
    )


def test_persist_failure_blocks_send(tmp_path: Path) -> None:
    journal = _FailingSendJournal(AppendOnlyLog(tmp_path / "cmd.l0"))
    transport = _CountingTransport()
    gateway = CommandGateway(journal=journal, transport=transport, clock=_clock())

    with pytest.raises(JournalWriteError):
        gateway.send(_intent())

    # Fail closed: the command was never sent.
    assert transport.calls == 0


def test_disk_failure_in_underlying_log_blocks_send(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = AppendOnlyLog(tmp_path / "cmd.l0")
    journal = ApiCommandJournal(log)
    transport = _CountingTransport()
    gateway = CommandGateway(journal=journal, transport=transport, clock=_clock())

    def _boom(_meta: object, _payload: object) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(log, "append", _boom)

    with pytest.raises(OSError):
        gateway.send(_intent())
    assert transport.calls == 0
