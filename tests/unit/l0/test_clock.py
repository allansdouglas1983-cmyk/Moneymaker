"""Unit tests for l0_raw.clock (SPEC-004: dual wall+monotonic clock)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from l0_raw import clock as c

pytestmark = pytest.mark.spec("SPEC-004")


def _domain(fingerprint_pid: int = 111) -> c.ClockDomain:
    return c.ClockDomain(
        host_id="h1",
        boot_id="b1",
        process_id=fingerprint_pid,
        process_start_utc=datetime(2026, 7, 15, tzinfo=timezone.utc),
        monotonic_origin_ns=1_000,
    )


def test_new_process_domain_is_populated() -> None:
    d = c.new_process_domain()
    assert d.host_id
    assert d.boot_id
    assert d.process_id > 0
    assert d.process_start_utc.tzinfo is not None
    assert isinstance(d.monotonic_origin_ns, int)


def test_now_carries_both_clocks() -> None:
    clock = c.Clock(_domain())
    stamp = clock.now()
    assert stamp.wall_utc.tzinfo is not None
    assert isinstance(stamp.monotonic_ns, int)
    assert stamp.domain_fingerprint == clock.domain.fingerprint


def test_latency_uses_monotonic_difference() -> None:
    fp = _domain().fingerprint
    a = c.ClockStamp(wall_utc=datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc), monotonic_ns=1_000, domain_fingerprint=fp)
    b = c.ClockStamp(wall_utc=datetime(2026, 7, 15, 12, 0, 1, tzinfo=timezone.utc), monotonic_ns=1_500, domain_fingerprint=fp)
    assert c.latency_ns(a, b) == 500


def test_latency_ignores_wall_clock_backward_jump() -> None:
    # Wall clock jumps BACKWARD (NTP) but monotonic advances: latency must stay positive.
    fp = _domain().fingerprint
    start = c.ClockStamp(
        wall_utc=datetime(2026, 7, 15, 12, 0, 5, tzinfo=timezone.utc), monotonic_ns=2_000, domain_fingerprint=fp
    )
    end = c.ClockStamp(
        wall_utc=datetime(2026, 7, 15, 12, 0, 1, tzinfo=timezone.utc), monotonic_ns=2_900, domain_fingerprint=fp
    )
    assert end.wall_utc < start.wall_utc
    assert c.latency_ns(start, end) == 900


def test_latency_across_domains_raises() -> None:
    a = c.ClockStamp(wall_utc=datetime(2026, 7, 15, tzinfo=timezone.utc), monotonic_ns=1, domain_fingerprint="h1:b1:1")
    b = c.ClockStamp(wall_utc=datetime(2026, 7, 15, tzinfo=timezone.utc), monotonic_ns=9, domain_fingerprint="h1:b1:2")
    with pytest.raises(ValueError):
        c.latency_ns(a, b)
