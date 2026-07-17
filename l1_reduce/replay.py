"""Canonical replay: reconstruct L2 derived state from the L0 append-only log (SPEC-011).

Market frames are selected by an explicit, closed record-type set: live capture writes
``"market"`` (SPEC-001) and historical ingestion writes ``"backfill_market"`` (SPEC-023,
``l0_raw.backfill``). Both reduce identically — reduction is provenance-agnostic byte
folding; provenance discipline (backfill never confers historical knowability) lives at
L3 via the SPEC-023 registry, never by silently dropping frames here (A3, conceptual
audit F-04). A log yielding zero market frames is a typed refusal, never an empty
result — an empty universe with no error is exactly the silent disappearance the
platform's refuse-don't-degrade posture forbids.
"""
from __future__ import annotations

from l0_raw.store import AppendOnlyLog
from l1_reduce.reducer import ReductionResult, reduce

_MARKET_RECORD_TYPES = frozenset({"market", "backfill_market"})


class EmptyReplayError(ValueError):
    """The log yielded zero market frames — refused, never reduced to an empty universe."""


def replay_from_log(log: AppendOnlyLog, reducer_version: str) -> ReductionResult:
    """Read raw market payloads (live-captured or backfilled) from an L0 log in order
    and reduce them. Raises :class:`EmptyReplayError` on zero market frames."""
    events: list[bytes] = [
        payload for meta, payload in log.read() if meta.get("record_type") in _MARKET_RECORD_TYPES
    ]
    if not events:
        raise EmptyReplayError(
            "L0 log contains no market frames (record_type in "
            f"{sorted(_MARKET_RECORD_TYPES)}); replaying it would silently produce an "
            "empty universe — refused (SPEC-011 / audit F-04)"
        )
    return reduce(events, reducer_version)
