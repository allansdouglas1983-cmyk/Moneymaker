"""Feature build context — actual-off time is not a live feature (SPEC-022).

Races are delayed, so the *actual* off time is unknowable while the race is still pre-off. A
live-mode feature builder knows only the **scheduled** start and current market state;
"seconds to actual off" is a post-hoc quantity. The build mode is explicit — there is no
default that could silently expose actual-off to a live model.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator


class BuildMode(str, Enum):
    """Whether features are built for the live model or for post-hoc analysis (SPEC-022)."""

    LIVE = "live"
    POST_HOC = "post_hoc"


class LiveModeViolation(RuntimeError):
    """A live-mode builder tried to read a quantity that is only knowable post-hoc.

    A ``RuntimeError`` (not ``ValueError``) so it is distinguishable from an ordinary
    missing-data error such as post-hoc mode lacking ``actual_off``.
    """


class FeatureBuildContext(BaseModel):
    """Context a feature builder runs in. ``mode`` is required — it must be explicit (SPEC-022).

    ``scheduled_start`` is always available (the live model knows it). ``actual_off`` is
    meaningful only in post-hoc mode: a live context may not carry it at all (rejected at
    construction), so the raw field cannot be read as a leakage side-channel, and the derived
    seconds-to-actual-off is additionally refused in live mode as defence in depth.
    """

    model_config = ConfigDict(frozen=True)

    mode: BuildMode
    scheduled_start: datetime
    actual_off: datetime | None = None

    @model_validator(mode="after")
    def _validate(self) -> FeatureBuildContext:
        if self.scheduled_start.tzinfo is None:
            raise ValueError("scheduled_start must be timezone-aware (UTC)")
        if self.actual_off is not None and self.actual_off.tzinfo is None:
            raise ValueError("actual_off must be timezone-aware (UTC)")
        # SPEC-022: a live context must not even *carry* the actual off — the raw field is a
        # leakage surface, not only the derived seconds-to-off method. Reject at construction so
        # a live builder structurally cannot read actual_off, regardless of population. A
        # LiveModeViolation (not ValueError) propagates unwrapped past pydantic's validator.
        if self.mode is BuildMode.LIVE and self.actual_off is not None:
            raise LiveModeViolation(
                "a live-mode feature build context must not carry actual_off; the actual off is "
                "not knowable live (SPEC-022)"
            )
        return self

    def seconds_to_scheduled_off(self, at: datetime) -> float:
        """Seconds from ``at`` to the scheduled off. Always available (live-safe)."""
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
