"""Feature build context — the knowability boundary is adapter-governed (SPEC-020/022, A1).

Two facts, never conflated:

* **Actual event start is not a live feature** (SPEC-022): a live-mode builder can never
  read or derive the actual off/start; that is post-hoc only, and the mode is explicit.
* **"Scheduled start is a safe live boundary" is a RACING fact, not a platform fact**
  (conceptual audit F-01): races are only ever delayed, so racing's live boundary may be
  the scheduled start. Sports whose events can start early (tennis) make that boundary a
  LEAKAGE HOLE — a feature first usable after the true start but before the scheduled
  start would pass the guard. And a market with no scheduled event start at all (a binary
  financial market, F-02) cannot honestly supply one.

So the boundary discipline is an explicit, required :class:`LiveBoundaryPolicy`, derived
from the sport adapter's declared ``events_can_start_early`` fact
(:class:`sport_core.adapter.SportAdapter.live_boundary_policy`):

* ``SCHEDULED_START_FLOOR`` — racing-exact semantics. Live boundary = scheduled start;
  post-hoc = actual off when known, else scheduled start. Requires ``scheduled_start``.
* ``OBSERVED_MARKET_STATE`` — the general policy. A LIVE context's boundary is the
  ``decision_time`` itself, constructible only with observed proof the market is pre-off
  at that instant (``observed_market_open=True``, ``observed_in_play=False`` — nothing
  else proves pre-off for an event that may already have started). A POST_HOC context's
  boundary is the RECORDED ``pre_off_transition`` (the first observed in-play/close
  transition), required. ``scheduled_start`` is optional and never the boundary.

Every cross-policy field contradiction is refused at construction, both directions — a
context declares exactly one boundary discipline.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from l3_features.knowledge_time import normalize_aware_datetimes_to_utc


class BuildMode(str, Enum):
    """Whether features are built for the live model or for post-hoc analysis (SPEC-022)."""

    LIVE = "live"
    POST_HOC = "post_hoc"


class LiveBoundaryPolicy(str, Enum):
    """How the knowability boundary is established (A1, audit F-01/F-02).

    ``SCHEDULED_START_FLOOR`` is valid only for sports whose adapter declares
    ``events_can_start_early=False`` (racing); the derivation lives on the adapter so an
    early-start sport can never obtain the floor by construction.
    """

    SCHEDULED_START_FLOOR = "scheduled_start_floor"
    OBSERVED_MARKET_STATE = "observed_market_state"


class LiveModeViolation(RuntimeError):
    """A live-mode builder tried to read a quantity that is only knowable post-hoc.

    A ``RuntimeError`` (not ``ValueError``) so it is distinguishable from an ordinary
    missing-data error such as post-hoc mode lacking ``actual_off``.
    """


class FeatureBuildContext(BaseModel):
    """Context a feature builder runs in. ``mode`` and ``boundary_policy`` are required —
    both must be explicit (SPEC-022, A1); silence is neither a mode nor a policy.

    ``actual_off`` is meaningful only in post-hoc mode: a live context may not carry it at
    all (rejected at construction), so the raw field cannot be read as a leakage
    side-channel, and the derived seconds-to-actual-off is additionally refused in live
    mode as defence in depth.
    """

    model_config = ConfigDict(frozen=True)

    mode: BuildMode
    boundary_policy: LiveBoundaryPolicy
    scheduled_start: datetime | None = None
    actual_off: datetime | None = None
    decision_time: datetime | None = None
    observed_market_open: bool | None = None
    observed_in_play: bool | None = None
    pre_off_transition: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _utc_normalise(cls, data: Any) -> Any:
        # Same instant, same hash (SPEC-024): aware datetimes are stored as UTC. Naive values
        # pass through so _validate still rejects them with the precise error below.
        return normalize_aware_datetimes_to_utc(data)

    @model_validator(mode="after")
    def _validate(self) -> FeatureBuildContext:
        for name in ("scheduled_start", "actual_off", "decision_time", "pre_off_transition"):
            value = getattr(self, name)
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware (UTC)")

        # SPEC-022: a live context must not even *carry* the actual off — the raw field is a
        # leakage surface, not only the derived seconds-to-off method. Reject at construction so
        # a live builder structurally cannot read actual_off, regardless of population. A
        # LiveModeViolation (not ValueError) propagates unwrapped past pydantic's validator.
        if self.mode is BuildMode.LIVE and self.actual_off is not None:
            raise LiveModeViolation(
                "a live-mode feature build context must not carry actual_off; the actual off is "
                "not knowable live (SPEC-022)"
            )

        if self.boundary_policy is LiveBoundaryPolicy.SCHEDULED_START_FLOOR:
            if self.scheduled_start is None:
                raise ValueError(
                    "SCHEDULED_START_FLOOR requires scheduled_start — the floor IS the "
                    "scheduled clock (racing-adapter policy, audit F-01)"
                )
            for name in (
                "decision_time",
                "observed_market_open",
                "observed_in_play",
                "pre_off_transition",
            ):
                if getattr(self, name) is not None:
                    raise ValueError(
                        f"SCHEDULED_START_FLOOR must not carry {name}: a context declares "
                        "exactly one boundary discipline (A1); observed-state fields belong "
                        "to OBSERVED_MARKET_STATE"
                    )
        else:  # OBSERVED_MARKET_STATE
            if self.mode is BuildMode.LIVE:
                if self.decision_time is None:
                    raise ValueError(
                        "OBSERVED_MARKET_STATE live mode requires decision_time — the live "
                        "boundary is the decision instant itself (A1)"
                    )
                if self.observed_market_open is not True or self.observed_in_play is not False:
                    raise ValueError(
                        "OBSERVED_MARKET_STATE live mode requires observed pre-off proof at "
                        "the decision time: observed_market_open=True and "
                        "observed_in_play=False. Anything less is refused — for an event that "
                        "may already have started, nothing but observed market state proves "
                        "pre-off (audit F-01)"
                    )
                if self.pre_off_transition is not None:
                    raise ValueError(
                        "pre_off_transition is the POST_HOC boundary; a live context must "
                        "not carry it"
                    )
            else:  # POST_HOC
                if self.pre_off_transition is None:
                    raise ValueError(
                        "OBSERVED_MARKET_STATE post-hoc mode requires pre_off_transition — "
                        "the recorded first in-play/close transition is the boundary (A1)"
                    )
                for name in ("decision_time", "observed_market_open", "observed_in_play"):
                    if getattr(self, name) is not None:
                        raise ValueError(
                            f"OBSERVED_MARKET_STATE post-hoc mode must not carry {name}: "
                            "live-proof fields have no post-hoc meaning and would suggest a "
                            "boundary the recorded transition already fixes"
                        )
        return self

    @property
    def knowability_boundary(self) -> datetime:
        """The boundary a feature must be provably knowable before (SPEC-020/022, A1)."""
        if self.boundary_policy is LiveBoundaryPolicy.SCHEDULED_START_FLOOR:
            assert self.scheduled_start is not None  # construction-guaranteed
            if self.mode is BuildMode.POST_HOC and self.actual_off is not None:
                return self.actual_off
            return self.scheduled_start
        if self.mode is BuildMode.LIVE:
            assert self.decision_time is not None  # construction-guaranteed
            return self.decision_time
        assert self.pre_off_transition is not None  # construction-guaranteed
        return self.pre_off_transition

    def seconds_to_scheduled_off(self, at: datetime) -> float:
        """Seconds from ``at`` to the scheduled start. Live-safe where a schedule exists;
        raises ``ValueError`` where the market has none (OBSERVED policy without one)."""
        if self.scheduled_start is None:
            raise ValueError(
                "this market has no scheduled_start (OBSERVED_MARKET_STATE policy without a "
                "schedule); there is no scheduled off to measure against"
            )
        return (self.scheduled_start - at).total_seconds()

    def seconds_to_actual_off(self, at: datetime) -> float:
        """Seconds from ``at`` to the *actual* off — post-hoc only (SPEC-022).

        Raises :class:`LiveModeViolation` in live mode (the actual off is not knowable), and
        ``ValueError`` in post-hoc mode when ``actual_off`` was not supplied.
        """
        if self.mode is BuildMode.LIVE:
            raise LiveModeViolation(
                "actual-off time is not available to a live-mode feature builder; the live "
                "model knows only the scheduled start (SPEC-022)"
            )
        if self.actual_off is None:
            raise ValueError("post-hoc mode requires actual_off to be set to derive seconds-to-off")
        return (self.actual_off - at).total_seconds()
