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
    """The replay would produce an empty market universe — refused, with diagnostics.

    Raised both when the log yields zero market frames AND when a non-empty, successfully
    decoded corpus reconstructs to zero markets (e.g. heartbeat-only frames): the two
    failures need distinguishable diagnostics — "wrong file" reads differently from
    "empty log" — but neither may silently return an empty universe.
    """


def replay_from_log(log: AppendOnlyLog, reducer_version: str) -> ReductionResult:
    """Read raw market payloads (live-captured or backfilled) from an L0 log in order
    and reduce them.

    Raises :class:`EmptyReplayError` when zero market frames are selected, and again
    when the frames decode and reduce but reconstruct zero markets — an empty universe
    is never a silent success (A3, audit F-04 + founder completion requirement).
    """
    events: list[bytes] = [
        payload for meta, payload in log.read() if meta.get("record_type") in _MARKET_RECORD_TYPES
    ]
    if not events:
        raise EmptyReplayError(
            "L0 log contains no market frames (record_type in "
            f"{sorted(_MARKET_RECORD_TYPES)}); replaying it would silently produce an "
            "empty universe — refused (SPEC-011 / audit F-04)"
        )
    result = reduce(events, reducer_version)
    if not result.state.markets:
        raise EmptyReplayError(
            f"replay read {len(events)} market frame(s) under reducer "
            f"{reducer_version!r} but reconstructed 0 markets — the corpus decoded but "
            "contains no market changes (e.g. heartbeat-only frames, or the wrong "
            "file); an empty universe is never a silent success (SPEC-011 / A3)"
        )
    return result
