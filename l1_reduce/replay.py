"""Canonical replay: reconstruct L2 derived state from the L0 append-only log (SPEC-011)."""
from __future__ import annotations

from l0_raw.store import AppendOnlyLog
from l1_reduce.reducer import ReductionResult, reduce


def replay_from_log(log: AppendOnlyLog, reducer_version: str) -> ReductionResult:
    """Read raw market payloads from an L0 log in order and reduce them."""
    events: list[bytes] = [payload for meta, payload in log.read() if meta.get("record_type") == "market"]
    return reduce(events, reducer_version)
