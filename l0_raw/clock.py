"""Dual wall + monotonic clock (SPEC-004).

Every timestamped record carries both a UTC wall clock and a monotonic process clock. Wall
clock can jump backwards under NTP adjustment, so latency computations MUST use monotonic
(SPEC-004). Monotonic clocks are only comparable within a process/boot clock domain
(SPECIFICATION.md §6.2); ``latency_ns`` refuses to compare across domains.
"""
from __future__ import annotations

import os
import socket
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ClockDomain(BaseModel):
    """Identity of a process/boot clock domain; monotonic values are only comparable within one."""

    model_config = ConfigDict(frozen=True)

    host_id: str
    boot_id: str
    process_id: int
    process_start_utc: datetime
    monotonic_origin_ns: int

    @property
    def fingerprint(self) -> str:
        return f"{self.host_id}:{self.boot_id}:{self.process_id}"


class ClockStamp(BaseModel):
    """A single instant recorded on both clocks, tagged with its clock domain."""

    model_config = ConfigDict(frozen=True)

    wall_utc: datetime
    monotonic_ns: int
    domain_fingerprint: str


class Clock:
    """Real dual clock bound to a :class:`ClockDomain`."""

    def __init__(self, domain: ClockDomain) -> None:
        self._domain = domain

    @property
    def domain(self) -> ClockDomain:
        return self._domain

    def now(self) -> ClockStamp:
        return ClockStamp(
            wall_utc=datetime.now(timezone.utc),
            monotonic_ns=time.monotonic_ns(),
            domain_fingerprint=self._domain.fingerprint,
        )


def _read_boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    except OSError:
        return "boot-" + uuid.uuid4().hex


def new_process_domain() -> ClockDomain:
    """Capture the current process/boot clock domain."""
    return ClockDomain(
        host_id=socket.gethostname() or "unknown-host",
        boot_id=_read_boot_id(),
        process_id=os.getpid(),
        process_start_utc=datetime.now(timezone.utc),
        monotonic_origin_ns=time.monotonic_ns(),
    )


def latency_ns(start: ClockStamp, end: ClockStamp) -> int:
    """Latency in nanoseconds from ``start`` to ``end``, using the monotonic clock only.

    Raises ``ValueError`` if the two stamps are from different clock domains — monotonic
    clocks are not comparable across processes/boots/hosts (SPECIFICATION.md §6.2).
    """
    if start.domain_fingerprint != end.domain_fingerprint:
        raise ValueError(
            "monotonic clocks are not comparable across clock domains: "
            f"{start.domain_fingerprint!r} != {end.domain_fingerprint!r}"
        )
    return end.monotonic_ns - start.monotonic_ns
