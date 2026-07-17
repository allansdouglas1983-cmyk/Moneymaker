"""SPEC-030 input contracts: the race as one mutually exclusive choice set.

Features arrive as l3's exact Decimals — a binary float is refused at this boundary (floats
exist only INSIDE the fitter, per ADR 0012 decision 2). A race with fewer than two active
runners is refused at construction: the exclusion happens explicitly upstream, never as a
silent disappearance. Non-runners stay present but inert (dropped by fit and prediction,
which renormalise over the active set).
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, model_validator

from sport_core.clustering import ClusterAssignment


class RaceValidationError(Exception):
    """A race/schema contract violation. Deliberately not a ValueError subclass: raised
    inside pydantic validators it propagates unwrapped, so callers catch a precise error."""


class FeatureSchema(BaseModel):
    """The canonical, ordered feature-name tuple a model is fitted against.

    Names must be pre-sorted and unique so the coefficient order and the schema hash are
    canonical — silent reordering would make two textually different schemas alias.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    names: tuple[str, ...]

    @model_validator(mode="after")
    def _validate(self) -> "FeatureSchema":
        if not self.names:
            raise RaceValidationError("a feature schema needs at least one feature name")
        if any(not name or name != name.strip() for name in self.names):
            raise RaceValidationError("feature names must be non-empty trimmed text")
        if list(self.names) != sorted(self.names):
            raise RaceValidationError("feature names must be sorted (canonical coefficient order)")
        if len(set(self.names)) != len(self.names):
            raise RaceValidationError("feature names must be unique")
        return self

    @property
    def feature_schema_hash(self) -> str:
        canonical = json.dumps({"names": list(self.names)}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RunnerRow(BaseModel):
    """One runner's exact-Decimal feature values; ``non_runner`` marks withdrawal."""

    model_config = ConfigDict(frozen=True, strict=True)

    runner_id: int
    features: Mapping[str, Decimal]
    non_runner: bool = False

    @model_validator(mode="before")
    @classmethod
    def _refuse_non_finite(cls, data: Any) -> Any:
        # Raised here (not left to pydantic's finite_number check) so callers get the
        # module's precise error type; runs only on raw construction data — an already
        # validated instance passes through on strict-mode revalidation.
        if isinstance(data, dict):
            features = data.get("features")
            if isinstance(features, Mapping):
                for name, value in features.items():
                    if isinstance(value, Decimal) and not value.is_finite():
                        raise RaceValidationError(
                            f"feature {name!r} must be a finite Decimal, got {value!r}"
                        )
        return data

    @model_validator(mode="after")
    def _validate(self) -> "RunnerRow":
        if self.runner_id <= 0:
            raise RaceValidationError(f"runner_id must be positive, got {self.runner_id}")
        return self


class Race(BaseModel):
    """One race: a mutually exclusive choice set over its active runners (SPEC-030)."""

    model_config = ConfigDict(frozen=True, strict=True)

    race_id: str
    # A4 (audit F-05): the adapter-owned dependence-group identity + explicit chronology
    # replaced the date-typed meeting_day — generic layers no longer reconstruct
    # meeting-day semantics; racing's meeting day arrives as calendar_day_assignment.
    cluster: ClusterAssignment
    runners: tuple[RunnerRow, ...]
    winner_id: int | None

    @model_validator(mode="after")
    def _validate(self) -> "Race":
        if not self.race_id or self.race_id != self.race_id.strip():
            raise RaceValidationError("race_id must be non-empty trimmed text")
        runner_ids = [r.runner_id for r in self.runners]
        if len(set(runner_ids)) != len(runner_ids):
            raise RaceValidationError(f"race {self.race_id!r}: duplicate runner ids")
        active_ids = {r.runner_id for r in self.runners if not r.non_runner}
        if len(active_ids) < 2:
            raise RaceValidationError(
                f"race {self.race_id!r}: needs >= 2 active runners "
                "(exclude it explicitly upstream; a one-runner choice set has no likelihood)"
            )
        if self.winner_id is not None and self.winner_id not in active_ids:
            raise RaceValidationError(
                f"race {self.race_id!r}: winner {self.winner_id} is not an active runner"
            )
        return self

    @property
    def active_runners(self) -> tuple[RunnerRow, ...]:
        return tuple(r for r in self.runners if not r.non_runner)
