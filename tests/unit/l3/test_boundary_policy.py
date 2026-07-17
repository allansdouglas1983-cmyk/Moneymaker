"""A1 (conceptual audit F-01/F-02, founder order #3): adapter-governed knowability boundary.

"Scheduled start is a safe live boundary" is TRUE only where events can never start early —
a racing-adapter fact. Tennis matches are routinely brought forward: under the old
scheduled-clock boundary, a feature first usable after the TRUE start but before the
scheduled start would pass the SPEC-020 guard — a live leakage hole. And a binary financial
market has no scheduled event start at all (F-02), so requiring one forces a fabricated
timestamp that then BECOMES the leakage boundary.

The fix pinned here:

* ``FeatureBuildContext`` carries an explicit, required ``boundary_policy``
  (:class:`LiveBoundaryPolicy`) — no default, silence is not a policy;
* ``SCHEDULED_START_FLOOR`` reproduces racing's semantics exactly (live boundary =
  scheduled start; post-hoc = actual off when known, else scheduled start) and REQUIRES a
  scheduled start;
* ``OBSERVED_MARKET_STATE`` is the general policy: a LIVE context's boundary is the
  decision time itself, constructible only with observed proof the market is pre-off at
  that instant (market open, not in-play — anything less is refused, because nothing else
  proves pre-off for an event that may already have started); a POST_HOC context's
  boundary is the RECORDED pre-off transition (first in-play/close transition), required;
* the sport adapter declares the FACT (``events_can_start_early``) and the policy DERIVES
  from it — a sport whose events can start early can never obtain the scheduled-start
  floor, by construction rather than by review;
* every cross-policy field contradiction is refused, both directions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from l3_features.build_context import (
    BuildMode,
    FeatureBuildContext,
    LiveBoundaryPolicy,
)
from sport_core.adapter import SportAdapter
from sport_core.capabilities import SportCapabilities

pytestmark = [pytest.mark.spec("SPEC-020"), pytest.mark.spec("SPEC-022")]


def _utc(offset_s: int) -> datetime:
    return datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_s)


SCHEDULED = _utc(0)
DECISION = _utc(-600)
TRANSITION = _utc(-120)  # match went in-play two minutes EARLY


def _floor_live() -> FeatureBuildContext:
    return FeatureBuildContext(
        mode=BuildMode.LIVE,
        boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR,
        scheduled_start=SCHEDULED,
    )


def _observed_live(**overrides: object) -> FeatureBuildContext:
    kwargs: dict[str, object] = {
        "mode": BuildMode.LIVE,
        "boundary_policy": LiveBoundaryPolicy.OBSERVED_MARKET_STATE,
        "decision_time": DECISION,
        "observed_market_open": True,
        "observed_in_play": False,
    }
    kwargs.update(overrides)
    return FeatureBuildContext(**kwargs)  # type: ignore[arg-type]


class TestPolicyIsExplicit:
    def test_boundary_policy_is_required(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            FeatureBuildContext(mode=BuildMode.LIVE, scheduled_start=SCHEDULED)  # type: ignore[call-arg]


class TestScheduledStartFloorIsRacingExact:
    def test_live_boundary_is_scheduled_start(self) -> None:
        assert _floor_live().knowability_boundary == SCHEDULED

    def test_post_hoc_boundary_is_actual_off_when_known(self) -> None:
        ctx = FeatureBuildContext(
            mode=BuildMode.POST_HOC,
            boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR,
            scheduled_start=SCHEDULED,
            actual_off=_utc(180),
        )
        assert ctx.knowability_boundary == _utc(180)

    def test_floor_requires_scheduled_start(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            FeatureBuildContext(
                mode=BuildMode.LIVE,
                boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR,
            )  # type: ignore[call-arg]

    def test_floor_refuses_observed_policy_fields(self) -> None:
        # A context declares exactly one boundary discipline; smuggling the other
        # policy's fields in is a contradiction, refused both directions.
        with pytest.raises(ValueError):
            FeatureBuildContext(
                mode=BuildMode.LIVE,
                boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR,
                scheduled_start=SCHEDULED,
                decision_time=DECISION,
            )
        with pytest.raises(ValueError):
            FeatureBuildContext(
                mode=BuildMode.POST_HOC,
                boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR,
                scheduled_start=SCHEDULED,
                pre_off_transition=TRANSITION,
            )


class TestObservedMarketStateLive:
    def test_live_boundary_is_decision_time(self) -> None:
        assert _observed_live().knowability_boundary == DECISION

    def test_live_requires_observed_pre_off_proof(self) -> None:
        # In-play, market closed, or missing observations: pre-off is not proven and the
        # context is refused — for an event that may have started early, nothing but
        # observed state proves pre-off.
        with pytest.raises(ValueError):
            _observed_live(observed_in_play=True)
        with pytest.raises(ValueError):
            _observed_live(observed_market_open=False)
        with pytest.raises((TypeError, ValueError)):
            _observed_live(observed_in_play=None)
        with pytest.raises((TypeError, ValueError)):
            _observed_live(observed_market_open=None)

    def test_live_requires_decision_time(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            _observed_live(decision_time=None)

    def test_scheduled_start_is_optional_under_observed_policy(self) -> None:
        # F-02: a binary financial market has no scheduled event start; none is fabricated.
        ctx = _observed_live()
        assert ctx.scheduled_start is None
        with_schedule = _observed_live(scheduled_start=SCHEDULED)
        assert with_schedule.knowability_boundary == DECISION  # schedule never the boundary

    def test_early_start_leakage_case_is_closed(self) -> None:
        # THE F-01 case: match went in-play at TRANSITION, BEFORE the scheduled start.
        # A live decision after the observed in-play transition is refused outright —
        # under the old scheduled-clock boundary it would have passed.
        with pytest.raises(ValueError):
            _observed_live(decision_time=_utc(-60), observed_in_play=True)


class TestObservedMarketStatePostHoc:
    def test_post_hoc_boundary_is_recorded_pre_off_transition(self) -> None:
        ctx = FeatureBuildContext(
            mode=BuildMode.POST_HOC,
            boundary_policy=LiveBoundaryPolicy.OBSERVED_MARKET_STATE,
            pre_off_transition=TRANSITION,
        )
        assert ctx.knowability_boundary == TRANSITION

    def test_post_hoc_requires_the_recorded_transition(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            FeatureBuildContext(
                mode=BuildMode.POST_HOC,
                boundary_policy=LiveBoundaryPolicy.OBSERVED_MARKET_STATE,
            )  # type: ignore[call-arg]

    def test_post_hoc_refuses_live_proof_fields(self) -> None:
        with pytest.raises(ValueError):
            FeatureBuildContext(
                mode=BuildMode.POST_HOC,
                boundary_policy=LiveBoundaryPolicy.OBSERVED_MARKET_STATE,
                pre_off_transition=TRANSITION,
                observed_in_play=False,
            )


class TestAdapterDeclaresTheFact:
    def _caps(self) -> SportCapabilities:
        return SportCapabilities(
            supports_multi_runner=True,
            supports_binary=False,
            supports_bsp=True,
            supports_dead_heat=True,
            supports_reduction_factor=True,
            supports_retirements=False,
            supports_draw=False,
            supports_partial_settlement=True,
            supports_void_rules=True,
            supports_in_play=True,
            supports_pre_match_only=False,
        )

    def _adapter(self, *, early: bool) -> SportAdapter:
        return SportAdapter(
            sport_id="horse_racing" if not early else "tennis_like",
            decision_unit="race" if not early else "match",
            capabilities=self._caps(),
            cluster_key_name="meeting_day",
            event_start_name="off",
            closing_diagnostic_taints=frozenset(),
            events_can_start_early=early,
        )

    def test_events_can_start_early_is_required(self) -> None:
        with pytest.raises(TypeError):
            SportAdapter(  # type: ignore[call-arg]
                sport_id="x",
                decision_unit="race",
                capabilities=self._caps(),
                cluster_key_name="k",
                event_start_name="s",
                closing_diagnostic_taints=frozenset(),
            )

    def test_policy_derives_from_the_fact_never_declared_separately(self) -> None:
        # The adapter declares the FACT; the policy DERIVES. A sport whose events can
        # start early can never obtain the scheduled-start floor, by construction.
        assert self._adapter(early=False).live_boundary_policy is (
            LiveBoundaryPolicy.SCHEDULED_START_FLOOR
        )
        assert self._adapter(early=True).live_boundary_policy is (
            LiveBoundaryPolicy.OBSERVED_MARKET_STATE
        )

    def test_tennis_adapter_declares_early_starts(self) -> None:
        from sport_tennis.adapter import TENNIS_ADAPTER

        assert TENNIS_ADAPTER.events_can_start_early is True
        assert TENNIS_ADAPTER.live_boundary_policy is LiveBoundaryPolicy.OBSERVED_MARKET_STATE
