"""SPEC-030: conditional logit stage one — MLE on the winner, race-grouped (§6.4).

The v1 BASELINE: plain (unregularised) conditional logit. The Newton machinery lives in
``l4_pricing._newton`` (shared with stage two — both stages are grouped-softmax MLEs) with
explicit refusals: ``FitDidNotConverge`` when the iteration budget ends, ``SeparationError``
when the MLE is unbounded or unidentified — never silent regularisation (the regularised
variant is a future progression step that must earn its place on held-out race-level score).

Determinism: fsum accumulation everywhere and sorted-race iteration make fits bit-identical
under race reordering, and predictions bit-identical under runner permutation (ADR 0012).
Binary floats live only inside this package; features arrive as exact Decimals and are
converted once.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from sport_core.clustering import ChronologyKey

from l4_pricing._newton import (
    FitDidNotConverge as FitDidNotConverge,
    PreparedRace,
    SeparationError as SeparationError,
    SingularHessianError as SingularHessianError,
    newton_mle,
    softmax,
    utilities,
)
from l4_pricing.horizon import HorizonLabel, require_horizon_match
from l4_pricing.races import FeatureSchema, Race, RaceValidationError, RunnerRow


@dataclass(frozen=True)
class StageOneModel:
    """An immutable fitted stage-one model (§6.11: retraining mints a new object)."""

    coefficients: tuple[float, ...]
    schema: FeatureSchema
    horizon: HorizonLabel
    n_races: int
    log_likelihood: float
    iterations_used: int
    training_race_ids: frozenset[str]
    training_race_ids_digest: str
    trained_through: ChronologyKey


def _feature_vector(runner: RunnerRow, schema: FeatureSchema, race_id: str) -> list[float]:
    actual = set(runner.features)
    expected = set(schema.names)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise RaceValidationError(
            f"race {race_id!r} runner {runner.runner_id}: features do not match the schema "
            f"(missing={missing}, extra={extra})"
        )
    return [float(runner.features[name]) for name in schema.names]


def race_ids_digest(race_ids: Sequence[str]) -> str:
    """Canonical digest of a training race-id set (sorted, newline-joined, sha256)."""
    return hashlib.sha256("\n".join(sorted(race_ids)).encode("utf-8")).hexdigest()


def fit_conditional_logit(
    races: Sequence[Race],
    schema: FeatureSchema,
    *,
    horizon: HorizonLabel,
    max_iter: int = 100,
) -> StageOneModel:
    """Race-grouped MLE on the winner (SPEC-030). Pure and bit-deterministic."""
    race_list = sorted(races, key=lambda race: race.race_id)
    if not race_list:
        raise RaceValidationError("cannot fit on an empty corpus")
    race_ids = [race.race_id for race in race_list]
    if len(set(race_ids)) != len(race_ids):
        raise RaceValidationError("duplicate race ids in the training corpus")

    prepared: list[PreparedRace] = []
    for race in race_list:
        if race.winner_id is None:
            raise RaceValidationError(f"race {race.race_id!r} has no winner; fitting requires outcomes")
        active = race.active_runners
        vectors = [_feature_vector(runner, schema, race.race_id) for runner in active]
        winner_index = next(
            i for i, runner in enumerate(active) if runner.runner_id == race.winner_id
        )
        prepared.append((vectors, winner_index))

    beta, final_ll, iterations_used = newton_mle(prepared, len(schema.names), max_iter)
    return StageOneModel(
        coefficients=tuple(beta),
        schema=schema,
        horizon=horizon,
        n_races=len(race_list),
        log_likelihood=final_ll,
        iterations_used=iterations_used,
        training_race_ids=frozenset(race_ids),
        training_race_ids_digest=race_ids_digest(race_ids),
        trained_through=max(race.cluster.chronology for race in race_list),
    )


def predict_race(
    model: StageOneModel, race: Race, *, horizon: HorizonLabel
) -> Mapping[int, float]:
    """Within-race win probabilities over the ACTIVE runners; sums to 1 (SPEC-030).

    Non-runners are dropped and the remainder renormalised natively by the softmax. The
    horizon declaration is mandatory — scoring is deployment's only door (SPEC-033).
    """
    require_horizon_match(model.horizon, horizon)
    active = race.active_runners
    vectors = [_feature_vector(runner, model.schema, race.race_id) for runner in active]
    probabilities = softmax(utilities(vectors, model.coefficients))
    return {runner.runner_id: p for runner, p in zip(active, probabilities)}

class _ConditionalLogitFamily:
    """Conditional logit as ONE registered StageOneFamily implementation (A5/F-06).

    The orchestrator owns folds, exclusions and provenance; this object only exposes
    fit/predict. Frozen module-level singleton; identity is the family's version string.
    """

    family_id = "conditional-logit-v1"

    def fit(
        self,
        races: Sequence[Race],
        schema: FeatureSchema,
        *,
        horizon: HorizonLabel,
        max_iter: int,
    ) -> StageOneModel:
        return fit_conditional_logit(races, schema, horizon=horizon, max_iter=max_iter)

    def predict(self, model: object, race: Race, *, horizon: HorizonLabel) -> Mapping[int, float]:
        if not isinstance(model, StageOneModel):
            raise TypeError(
                f"conditional-logit predict requires a StageOneModel, got {type(model).__name__}"
            )
        return predict_race(model, race, horizon=horizon)


CONDITIONAL_LOGIT_FAMILY = _ConditionalLogitFamily()
