"""SPEC-011 canonical replay from the L0 append-only log (reconstruction equivalence).

The golden-hash regression (that pins reducer-mcm-v1's canonical output) is added with the
implementation, since the pinned value is an output of the reducer.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from l0_raw.capture import RawStreamCapture
from l0_raw.clock import Clock, ClockDomain
from l0_raw.store import AppendOnlyLog
from l1_reduce.mcm_v1 import REDUCER_VERSION
from l1_reduce.reducer import reduce
from l1_reduce.replay import replay_from_log

pytestmark = [pytest.mark.spec("SPEC-011"), pytest.mark.spec("SPEC-012")]

_FIXTURE: list[dict[str, object]] = [
    {
        "op": "mcm",
        "pt": 1000,
        "mc": [
            {
                "id": "1.101",
                "img": True,
                "marketDefinition": {
                    "status": "OPEN",
                    "inPlay": False,
                    "version": 1,
                    "betDelay": 0,
                    "runners": [
                        {"id": 111, "status": "ACTIVE", "sortPriority": 1},
                        {"id": 222, "status": "ACTIVE", "sortPriority": 2},
                    ],
                },
                "rc": [
                    {"id": 111, "batb": [[0, 3.45, 10.5]], "ltp": 3.45},
                    {"id": 222, "batb": [[0, 4.2, 8]], "ltp": 4.2},
                ],
            }
        ],
    },
    {"op": "mcm", "pt": 1500, "mc": [{"id": "1.101", "rc": [{"id": 111, "batb": [[0, 3.4, 12]], "ltp": 3.4}]}]},
    {
        "op": "mcm",
        "pt": 2000,
        "mc": [
            {
                "id": "1.101",
                "marketDefinition": {
                    "status": "SUSPENDED",
                    "inPlay": False,
                    "version": 2,
                    "runners": [
                        {"id": 111, "status": "ACTIVE", "sortPriority": 1},
                        {"id": 222, "status": "ACTIVE", "sortPriority": 2},
                    ],
                },
            }
        ],
    },
]
_EVENTS: list[bytes] = [json.dumps(m).encode("utf-8") for m in _FIXTURE]


def _domain() -> ClockDomain:
    return ClockDomain(
        host_id="h",
        boot_id="b",
        process_id=1,
        process_start_utc=datetime(2026, 7, 15, tzinfo=timezone.utc),
        monotonic_origin_ns=0,
    )


def test_replay_from_log_matches_direct_reduce(tmp_path: Path) -> None:
    log = AppendOnlyLog(tmp_path / "raw.l0")
    cap = RawStreamCapture(clock=Clock(_domain()), log=log, partition_id="p")
    for payload in _EVENTS:
        cap.capture_market(
            payload,
            publish_time=None,
            stream_clock=None,
            connection_id="c",
            subscription_hash="s",
            conflation_settings="none",
            schema_version="mcm-v1",
        )
    replayed = replay_from_log(log, REDUCER_VERSION)
    direct = reduce(_EVENTS, REDUCER_VERSION)
    # L2 derived state is reconstructible from L0 + reducer version, byte-identical (SPEC-011).
    assert replayed.canonical_bytes == direct.canonical_bytes
    assert replayed.canonical_hash == direct.canonical_hash
