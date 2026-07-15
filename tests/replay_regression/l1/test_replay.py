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


# Golden canonical hash for reducer-mcm-v1 over the fixture. Any change to the reduction
# logic changes this hash and fails here, forcing a version bump or a reviewed golden update
# (SPEC-012 enforcement via the SPEC-011 replay regression).
_GOLDEN_HASH = "c20a3c8205ca191a4be359771e0e5b451c7ef80427a22e173c5aad3c00ec8a59"


def test_golden_canonical_hash_is_stable() -> None:
    assert reduce(_EVENTS, REDUCER_VERSION).canonical_hash == _GOLDEN_HASH


# A second golden fixture exercising EVERY declared-scope field (batb, batl, atb, atl, ltp,
# tv, adjustmentFactor, removalDate, sortPriority, numberOfActiveRunners, betDelay) plus
# level and price removals, so a regression anywhere in the reducer's in-scope surface fails
# the SPEC-012 version-bump guard (advisory review F2).
_FULL_FIXTURE: list[dict[str, object]] = [
    {
        "op": "mcm",
        "pt": 5000,
        "mc": [
            {
                "id": "1.202",
                "img": True,
                "marketDefinition": {
                    "status": "OPEN",
                    "inPlay": False,
                    "version": 1,
                    "betDelay": 5,
                    "numberOfActiveRunners": 2,
                    "runners": [
                        {"id": 111, "status": "ACTIVE", "sortPriority": 1},
                        {"id": 222, "status": "REMOVED", "adjustmentFactor": 12.5, "removalDate": "2026-07-15T13:00:00.000Z", "sortPriority": 2},
                        {"id": 333, "status": "ACTIVE", "sortPriority": 3},
                    ],
                },
                "rc": [
                    {
                        "id": 111,
                        "batb": [[0, 3.45, 10.5], [1, 3.5, 20]],
                        "batl": [[0, 3.6, 8]],
                        "atb": [[3.45, 10.5], [3.4, 5]],
                        "atl": [[3.6, 8]],
                        "ltp": 3.45,
                        "tv": 100.5,
                    },
                    {"id": 333, "batb": [[0, 6.0, 4]], "ltp": 6.0},
                ],
            }
        ],
    },
    {
        "op": "mcm",
        "pt": 5500,
        "mc": [
            {
                "id": "1.202",
                "rc": [{"id": 111, "batb": [[1, 3.5, 0]], "atb": [[3.4, 0]], "ltp": 3.4, "tv": 120.0}],
            }
        ],
    },
    {"op": "mcm", "pt": 6000, "mc": [{"id": "1.202", "marketDefinition": {"status": "SUSPENDED", "version": 2, "runners": [{"id": 111, "status": "ACTIVE", "sortPriority": 1}, {"id": 333, "status": "ACTIVE", "sortPriority": 3}]}}]},
]
_FULL_EVENTS: list[bytes] = [json.dumps(m).encode("utf-8") for m in _FULL_FIXTURE]
_FULL_GOLDEN_HASH = "3c4c7a69649fa7979f99bef29ca7d3b95f6b99d3c48b84c8026d562e60a1c773"


def test_full_scope_golden_canonical_hash_is_stable() -> None:
    assert reduce(_FULL_EVENTS, REDUCER_VERSION).canonical_hash == _FULL_GOLDEN_HASH
