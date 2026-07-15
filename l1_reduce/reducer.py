"""Reducer framework: registry, versioning, and canonical replay result (SPEC-010/011/012).

`reduce(raw_events, reducer_version)` is a pure function dispatched by immutable version
string. Registered reducers are never removed, so old versions stay runnable for replay of
historical conclusions (SPEC-012). The result records the reducer version, a reducer digest,
a digest of the raw inputs, and the canonical bytes + hash of the derived state.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from l1_reduce import mcm_v1
from l1_reduce.canonical import canonical_bytes
from l1_reduce.state import MarketUniverseState

ReducerFn = Callable[[Sequence[bytes]], MarketUniverseState]


class UnknownReducerVersion(Exception):
    """Raised when reduce() is asked for a reducer version that is not registered."""


@dataclass(frozen=True)
class _Reducer:
    version: str
    digest: str
    fn: ReducerFn


_REGISTRY: dict[str, _Reducer] = {}


def _register(version: str, digest: str, fn: ReducerFn) -> None:
    if version in _REGISTRY:
        raise ValueError(f"reducer version already registered: {version}")
    _REGISTRY[version] = _Reducer(version=version, digest=digest, fn=fn)


_register(mcm_v1.REDUCER_VERSION, mcm_v1.REDUCER_DIGEST, mcm_v1.reduce_events)


def available_versions() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


@dataclass(frozen=True)
class ReductionResult:
    reducer_version: str
    reducer_digest: str
    raw_events_digest: str
    canonical_bytes: bytes
    canonical_hash: str
    state: MarketUniverseState


def _raw_events_digest(events: Sequence[bytes]) -> str:
    digest = hashlib.sha256()
    for payload in events:
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def reduce(raw_events: Sequence[bytes], reducer_version: str) -> ReductionResult:
    reducer = _REGISTRY.get(reducer_version)
    if reducer is None:
        raise UnknownReducerVersion(
            f"unknown reducer version: {reducer_version!r}; available: {available_versions()}"
        )
    events = list(raw_events)
    state = reducer.fn(events)
    cbytes = canonical_bytes(state)
    return ReductionResult(
        reducer_version=reducer.version,
        reducer_digest=reducer.digest,
        raw_events_digest=_raw_events_digest(events),
        canonical_bytes=cbytes,
        canonical_hash=hashlib.sha256(cbytes).hexdigest(),
        state=state,
    )
