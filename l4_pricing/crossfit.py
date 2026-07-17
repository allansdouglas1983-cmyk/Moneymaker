"""SPEC-031: time-respecting, strictly out-of-fold cross-fitting (§6.4 steps 1–4).

If ``p_fundamental`` is not out-of-sample, alpha is spuriously inflated and the entire result
is worthless — the single most common way this class of model fools its builder. Every
out-of-fold fundamental therefore carries provenance (the trained-through day and the exact
training race-id set), the plan self-verifies before returning, and stage two re-verifies at
consumption (`assert_out_of_fold`).

Fold structure: one block per meeting day, expanding window — day k's model trains on ALL
races from strictly earlier days (the finest time-respecting granularity; no tunable fold
count). The earliest day, and any day whose stage-one fit fails, become explicit exclusions
with reasons; excluded days' races still serve as TRAINING data for later days (they are
valid outcomes). Universe accounting is exact: every input race is an OOF race or an
exclusion, never a disappearance.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from sport_core.clustering import ChronologyKey, ClusterAssignment

from l4_pricing.conditional_logit import (
    FitDidNotConverge,
    SeparationError,
    StageOneModel,
    fit_conditional_logit,
    predict_race,
)
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import Race, RaceValidationError, FeatureSchema


class CrossFitViolation(Exception):
    """A fundamental probability came from a model that saw its race (SPEC-031)."""


@dataclass(frozen=True)
class StageOneProvenance:
    """Which data produced an out-of-fold fundamental — the SPEC-031 audit trail."""

    trained_through: ChronologyKey
    training_race_ids: frozenset[str]
    training_race_ids_digest: str
    horizon: HorizonLabel


@dataclass(frozen=True)
class OOFFundamental:
    """One runner's strictly out-of-fold fundamental probability, with provenance."""

    race_id: str
    runner_id: int
    p_fundamental: float
    provenance: StageOneProvenance

    def __post_init__(self) -> None:
        if not 0.0 < self.p_fundamental < 1.0:
            raise ValueError(
                f"p_fundamental must be in the open interval (0, 1); got "
                f"{self.p_fundamental!r} for race {self.race_id!r} runner {self.runner_id}"
            )


@dataclass(frozen=True)
class ExcludedRace:
    """An explicit exclusion with its reason — universe accounting, never a disappearance."""

    race_id: str
    reason: str


@dataclass(frozen=True)
class CrossFitResult:
    oof: tuple[OOFFundamental, ...]
    oof_race_ids: frozenset[str]
    excluded: tuple[ExcludedRace, ...]
    deployment_model: StageOneModel  # §6.4 step 4: retrained on the full window
    horizon: HorizonLabel


def assert_out_of_fold(rows: Iterable[object], races: Mapping[str, Race]) -> None:
    """Re-verify SPEC-031 at consumption: refuse any row whose model saw its race.

    Accepts ``Iterable[object]`` deliberately — the whole point is to refuse values that are
    not provenance-carrying ``OOFFundamental`` rows (a bare float cannot type into stage two).
    """
    for row in rows:
        if not isinstance(row, OOFFundamental):
            raise CrossFitViolation(
                f"stage-two fundamentals must be OOFFundamental values with provenance; "
                f"got {type(row).__name__}"
            )
        race = races.get(row.race_id)
        if race is None:
            raise CrossFitViolation(f"OOF row references unknown race {row.race_id!r}")
        if row.race_id in row.provenance.training_race_ids:
            raise CrossFitViolation(
                f"race {row.race_id!r}: its fundamental came from a model trained ON that race"
            )
        if row.provenance.trained_through >= race.cluster.chronology:
            raise CrossFitViolation(
                f"race {row.race_id!r} (chronology {race.cluster.chronology.ordinal}): model "
                f"trained through {row.provenance.trained_through.ordinal} is not strictly "
                "earlier (SPEC-031, A4 — folds compare ChronologyKey, never cluster identity)"
            )


def cross_fit(
    races: Sequence[Race],
    schema: FeatureSchema,
    *,
    horizon: HorizonLabel,
    max_iter: int = 100,
) -> CrossFitResult:
    """Produce strictly out-of-fold fundamentals for every race that can honestly have one."""
    race_list = sorted(races, key=lambda race: race.race_id)
    if not race_list:
        raise RaceValidationError("cannot cross-fit an empty corpus")
    race_ids = [race.race_id for race in race_list]
    if len(set(race_ids)) != len(race_ids):
        raise RaceValidationError("duplicate race ids in the corpus")
    for race in race_list:
        if race.winner_id is None:
            raise RaceValidationError(
                f"race {race.race_id!r} has no winner; cross-fitting is a training procedure"
            )

    # A4: folds are ordered by the adapter's explicit ChronologyKey, grouped by opaque
    # ClusterId. Sorting key: (chronology, cluster_id.value) — the id component is a
    # DETERMINISM device for same-chronology clusters, never time order (ClusterId
    # itself is unorderable by design).
    assignments = {race.cluster for race in race_list}
    days = sorted(assignments, key=lambda a: (a.chronology, a.cluster_id.value))
    by_day: dict[ClusterAssignment, list[Race]] = {day: [] for day in days}
    for race in race_list:
        by_day[race.cluster].append(race)

    oof: list[OOFFundamental] = []
    excluded: list[ExcludedRace] = []
    for index, day in enumerate(days):
        day_races = by_day[day]
        if index == 0:
            excluded.extend(
                ExcludedRace(race.race_id, "no earlier cluster chronology to train on")
                for race in day_races
            )
            continue
        training = [race for earlier in days[:index] for race in by_day[earlier]]
        try:
            model = fit_conditional_logit(training, schema, horizon=horizon, max_iter=max_iter)
        except (SeparationError, FitDidNotConverge) as exc:
            excluded.extend(
                ExcludedRace(race.race_id, f"stage-one fit failed on earlier days: {exc}")
                for race in day_races
            )
            continue
        provenance = StageOneProvenance(
            trained_through=model.trained_through,
            training_race_ids=model.training_race_ids,
            training_race_ids_digest=model.training_race_ids_digest,
            horizon=horizon,
        )
        for race in day_races:
            probabilities = predict_race(model, race, horizon=horizon)
            if not all(0.0 < p < 1.0 for p in probabilities.values()):
                # A near-separated model can saturate a prediction to exactly 0.0/1.0 in
                # float64. That is not a usable fundamental — exclude the race explicitly
                # rather than emit a degenerate probability or silently clamp it.
                excluded.append(
                    ExcludedRace(
                        race.race_id,
                        "degenerate fundamental probability (near-separated stage-one model)",
                    )
                )
                continue
            for runner_id in sorted(probabilities):
                oof.append(
                    OOFFundamental(
                        race_id=race.race_id,
                        runner_id=runner_id,
                        p_fundamental=probabilities[runner_id],
                        provenance=provenance,
                    )
                )

    result = CrossFitResult(
        oof=tuple(oof),
        oof_race_ids=frozenset(row.race_id for row in oof),
        excluded=tuple(excluded),
        deployment_model=fit_conditional_logit(
            race_list, schema, horizon=horizon, max_iter=max_iter
        ),
        horizon=horizon,
    )
    # Self-check: the producer holds itself to the same standard the consumer re-verifies.
    assert_out_of_fold(result.oof, {race.race_id: race for race in race_list})
    if len(result.oof_race_ids) + len(result.excluded) != len(race_list):
        raise CrossFitViolation("universe accounting failed: races lost or double-counted")
    return result
