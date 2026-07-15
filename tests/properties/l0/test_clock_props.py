"""Property tests for SPEC-004: latency is the monotonic delta, invariant to wall-clock jumps."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l0_raw import clock as c

pytestmark = pytest.mark.spec("SPEC-004")

_FP = "h1:b1:1"


def _stamp(monotonic_ns: int, wall_offset_s: int) -> c.ClockStamp:
    return c.ClockStamp(
        wall_utc=datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=wall_offset_s),
        monotonic_ns=monotonic_ns,
        domain_fingerprint=_FP,
    )


@settings(max_examples=200)
@given(
    start_mono=st.integers(min_value=-(10**15), max_value=10**15),
    delta=st.integers(min_value=0, max_value=10**12),
    wall_start=st.integers(min_value=-10_000, max_value=10_000),
    wall_end=st.integers(min_value=-10_000, max_value=10_000),
)
def test_latency_equals_monotonic_delta_regardless_of_wall(
    start_mono: int, delta: int, wall_start: int, wall_end: int
) -> None:
    start = _stamp(start_mono, wall_start)
    end = _stamp(start_mono + delta, wall_end)
    # Wall clock may move forward, backward, or not at all; latency depends only on monotonic.
    assert c.latency_ns(start, end) == delta


@settings(max_examples=100)
@given(mono_a=st.integers(), mono_b=st.integers())
def test_cross_domain_always_raises(mono_a: int, mono_b: int) -> None:
    a = c.ClockStamp(
        wall_utc=datetime(2026, 7, 15, tzinfo=timezone.utc), monotonic_ns=mono_a, domain_fingerprint="dom-A"
    )
    b = c.ClockStamp(
        wall_utc=datetime(2026, 7, 15, tzinfo=timezone.utc), monotonic_ns=mono_b, domain_fingerprint="dom-B"
    )
    with pytest.raises(ValueError):
        c.latency_ns(a, b)
