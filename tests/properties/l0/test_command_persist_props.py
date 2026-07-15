"""Property tests for SPEC-003: API command persisted BEFORE it is sent."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l0_raw import records as r
from l0_raw.clock import Clock, ClockDomain
from l0_raw.commands import ApiCommandJournal, CommandGateway, CommandIntent
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


class _AssertPersistedTransport:
    """A transport that fails unless the send event is ALREADY in the journal."""

    def __init__(self, journal: ApiCommandJournal, command_id: str) -> None:
        self._journal = journal
        self._command_id = command_id
        self.calls = 0

    def send(self, payload: bytes) -> bytes:
        self.calls += 1
        send_ids = {
            ev.command_id
            for ev in self._journal.read()
            if isinstance(ev, r.ApiCommandSendEvent)
        }
        # If the gateway sent before persisting, this command_id would be absent.
        assert self._command_id in send_ids, "transport invoked before send event was persisted"
        return b"response-for:" + payload


@settings(max_examples=100)
@given(payload=st.binary(min_size=0, max_size=128), cid=st.text(min_size=1, max_size=12))
def test_send_event_persisted_before_transport(
    tmp_path_factory: pytest.TempPathFactory, payload: bytes, cid: str
) -> None:
    tmp: Path = tmp_path_factory.mktemp("cmd")
    journal = ApiCommandJournal(AppendOnlyLog(tmp / "cmd.l0"))
    transport = _AssertPersistedTransport(journal, cid)
    gateway = CommandGateway(journal=journal, transport=transport, clock=_clock())

    intent = CommandIntent(
        command_id=cid,
        customer_ref="cref",
        customer_order_ref="coref",
        signal_id="sig",
        payload=payload,
        process_version="proc-v1",
    )
    response = gateway.send(intent)

    assert transport.calls == 1
    assert response == b"response-for:" + payload
    events = list(journal.read())
    sends = [e for e in events if isinstance(e, r.ApiCommandSendEvent)]
    responses = [e for e in events if isinstance(e, r.ApiCommandResponseEvent)]
    assert len(sends) == 1 and len(responses) == 1
    # payload_hash is the hash of the sent payload; response links by command_id.
    assert sends[0].payload_hash == r.sha256_hex(payload)
    assert responses[0].command_id == cid
    assert responses[0].response_payload == response
