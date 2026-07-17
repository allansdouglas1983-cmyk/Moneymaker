"""Actual-off time is not a live feature (SPEC-022).

Races are delayed. The live model knows scheduled start and current market state only.
"Seconds to actual off" MUST be unavailable to live-mode feature builders and available in
post-hoc mode only, with the mode explicit.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from l3_features.build_context import (
    LiveBoundaryPolicy,
    BuildMode,
    FeatureBuildContext,
    LiveModeViolation,
)

pytestmark = pytest.mark.spec("SPEC-022")


def _utc(offset_s: int) -> datetime:
    return datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_s)


SCHEDULED = _utc(0)
ACTUAL = _utc(180)  # race went off 3 minutes late


class TestModeIsExplicit:
    def test_mode_is_required(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, scheduled_start=SCHEDULED)  # type: ignore[call-arg]

    def test_context_is_frozen(self) -> None:
        ctx = FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, mode=BuildMode.LIVE, scheduled_start=SCHEDULED)
        with pytest.raises((ValueError, TypeError)):
            ctx.mode = BuildMode.POST_HOC


class TestLiveMode:
    def test_scheduled_off_is_always_available(self) -> None:
        ctx = FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, mode=BuildMode.LIVE, scheduled_start=SCHEDULED)
        assert ctx.seconds_to_scheduled_off(_utc(-60)) == pytest.approx(60.0)

    def test_live_context_cannot_carry_actual_off(self) -> None:
        # The raw field is a leakage surface, not just the derived method: a live context must
        # not even hold actual_off, so it cannot be read as a side-channel.
        with pytest.raises(LiveModeViolation):
            FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, mode=BuildMode.LIVE, scheduled_start=SCHEDULED, actual_off=ACTUAL)

    def test_actual_off_seconds_unavailable_even_without_actual_off_set(self) -> None:
        ctx = FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, mode=BuildMode.LIVE, scheduled_start=SCHEDULED)
        with pytest.raises(LiveModeViolation):
            ctx.seconds_to_actual_off(_utc(-60))


class TestPostHocMode:
    def test_actual_off_seconds_available_in_post_hoc(self) -> None:
        ctx = FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, 
            mode=BuildMode.POST_HOC, scheduled_start=SCHEDULED, actual_off=ACTUAL
        )
        # 60s before scheduled off -> 240s before actual off.
        assert ctx.seconds_to_actual_off(_utc(-60)) == pytest.approx(240.0)

    def test_post_hoc_without_actual_off_raises_value_error_not_leak(self) -> None:
        ctx = FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, mode=BuildMode.POST_HOC, scheduled_start=SCHEDULED)
        with pytest.raises(ValueError) as ei:
            ctx.seconds_to_actual_off(_utc(-60))
        assert not isinstance(ei.value, LiveModeViolation)
