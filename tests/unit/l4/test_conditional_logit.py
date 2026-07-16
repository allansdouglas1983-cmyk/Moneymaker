"""SPEC-030: conditional logit stage one — MLE on the winner, race as one choice set.

Recovery fixtures use replicated-frequency constructions with CLOSED-FORM optima (no
sampling noise): four replicated two-runner races where the favourite wins three give
beta-hat = ln 3 exactly at the optimum.
"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest

from l4_pricing.conditional_logit import (
    FitDidNotConverge,
    SeparationError,
    StageOneModel,
    fit_conditional_logit,
    predict_race,
)
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RaceValidationError, RunnerRow

pytestmark = pytest.mark.spec("SPEC-030")

DAY = date(2026, 7, 1)
SCHEMA = FeatureSchema(names=("fav",))
H = HorizonLabel("T-2m")


def _two_runner_race(race_id: str, winner_id: int) -> Race:
    return Race(
        race_id=race_id,
        meeting_day=DAY,
        runners=(
            RunnerRow(runner_id=1, features={"fav": Decimal(1)}),
            RunnerRow(runner_id=2, features={"fav": Decimal(0)}),
        ),
        winner_id=winner_id,
    )


def _three_to_one_corpus() -> list[Race]:
    # Favourite wins 3 of 4 replicated races: MLE beta = logit(3/4) = ln 3 exactly.
    return [
        _two_runner_race("r1", 1),
        _two_runner_race("r2", 1),
        _two_runner_race("r3", 1),
        _two_runner_race("r4", 2),
    ]


def test_mle_recovers_log_three_exactly() -> None:
    model = fit_conditional_logit(_three_to_one_corpus(), SCHEMA, horizon=H)
    assert abs(model.coefficients[0] - math.log(3)) < 1e-8


def test_log_likelihood_at_optimum_matches_closed_form() -> None:
    model = fit_conditional_logit(_three_to_one_corpus(), SCHEMA, horizon=H)
    expected = 3 * math.log(0.75) + math.log(0.25)
    assert abs(model.log_likelihood - expected) < 1e-10


def test_predicted_probabilities_match_empirical_frequencies() -> None:
    model = fit_conditional_logit(_three_to_one_corpus(), SCHEMA, horizon=H)
    probs = predict_race(model, _two_runner_race("r9", 1), horizon=H)
    assert abs(probs[1] - 0.75) < 1e-8
    assert abs(probs[2] - 0.25) < 1e-8


def test_probabilities_sum_to_one_across_field_sizes() -> None:
    model = fit_conditional_logit(_three_to_one_corpus(), SCHEMA, horizon=H)
    for k in (2, 3, 5, 8):
        race = Race(
            race_id=f"f{k}",
            meeting_day=DAY,
            runners=tuple(
                RunnerRow(runner_id=i + 1, features={"fav": Decimal(i) / Decimal(4)}) for i in range(k)
            ),
            winner_id=None,
        )
        probs = predict_race(model, race, horizon=H)
        assert set(probs) == {i + 1 for i in range(k)}
        assert abs(math.fsum(probs.values()) - 1.0) < 1e-12


def test_non_runners_are_dropped_and_prediction_renormalises() -> None:
    model = fit_conditional_logit(_three_to_one_corpus(), SCHEMA, horizon=H)
    with_nr = Race(
        race_id="nr",
        meeting_day=DAY,
        runners=(
            RunnerRow(runner_id=1, features={"fav": Decimal(1)}),
            RunnerRow(runner_id=2, features={"fav": Decimal(0)}),
            RunnerRow(runner_id=3, features={"fav": Decimal(9)}, non_runner=True),
        ),
        winner_id=None,
    )
    probs = predict_race(model, with_nr, horizon=H)
    assert set(probs) == {1, 2}
    assert abs(math.fsum(probs.values()) - 1.0) < 1e-12


def test_fit_ignores_non_runner_rows_entirely() -> None:
    # A marked non-runner with an extreme feature value must not perturb the fit at all:
    # coefficients are bit-identical to the fit on races without that runner present.
    corpus_with_nr = [
        Race(
            race_id=r.race_id,
            meeting_day=r.meeting_day,
            runners=r.runners + (RunnerRow(runner_id=99, features={"fav": Decimal(50)}, non_runner=True),),
            winner_id=r.winner_id,
        )
        for r in _three_to_one_corpus()
    ]
    a = fit_conditional_logit(_three_to_one_corpus(), SCHEMA, horizon=H)
    b = fit_conditional_logit(corpus_with_nr, SCHEMA, horizon=H)
    assert a.coefficients == b.coefficients


def test_fit_is_bit_deterministic() -> None:
    a = fit_conditional_logit(_three_to_one_corpus(), SCHEMA, horizon=H)
    b = fit_conditional_logit(_three_to_one_corpus(), SCHEMA, horizon=H)
    assert a.coefficients == b.coefficients
    assert a.log_likelihood == b.log_likelihood
    assert a.training_race_ids_digest == b.training_race_ids_digest


def test_model_records_training_provenance() -> None:
    model = fit_conditional_logit(_three_to_one_corpus(), SCHEMA, horizon=H)
    assert model.training_race_ids == frozenset({"r1", "r2", "r3", "r4"})
    assert model.trained_through_day == DAY
    assert model.training_race_ids_digest
    assert model.horizon == H
    assert isinstance(model, StageOneModel)


def test_perfect_separation_raises() -> None:
    # Favourite wins every race: the MLE diverges and MUST be refused, never silently
    # regularised (the regularised variant is a future, separately-earned progression step).
    corpus = [_two_runner_race(f"r{i}", 1) for i in range(4)]
    with pytest.raises(SeparationError):
        fit_conditional_logit(corpus, SCHEMA, horizon=H)


def test_iteration_budget_exhaustion_raises() -> None:
    with pytest.raises(FitDidNotConverge):
        fit_conditional_logit(_three_to_one_corpus(), SCHEMA, horizon=H, max_iter=1)


def test_fit_requires_winners_on_every_race() -> None:
    races = _three_to_one_corpus()
    races.append(
        Race(
            race_id="no-winner",
            meeting_day=DAY,
            runners=(
                RunnerRow(runner_id=1, features={"fav": Decimal(1)}),
                RunnerRow(runner_id=2, features={"fav": Decimal(0)}),
            ),
            winner_id=None,
        )
    )
    with pytest.raises(RaceValidationError):
        fit_conditional_logit(races, SCHEMA, horizon=H)


def test_fit_requires_nonempty_corpus() -> None:
    with pytest.raises(RaceValidationError):
        fit_conditional_logit([], SCHEMA, horizon=H)


def test_features_must_match_schema_exactly() -> None:
    missing = Race(
        race_id="m",
        meeting_day=DAY,
        runners=(
            RunnerRow(runner_id=1, features={"other": Decimal(1)}),
            RunnerRow(runner_id=2, features={"other": Decimal(0)}),
        ),
        winner_id=1,
    )
    with pytest.raises(RaceValidationError):
        fit_conditional_logit([missing], SCHEMA, horizon=H)
    extra = Race(
        race_id="x",
        meeting_day=DAY,
        runners=(
            RunnerRow(runner_id=1, features={"fav": Decimal(1), "spare": Decimal(2)}),
            RunnerRow(runner_id=2, features={"fav": Decimal(0), "spare": Decimal(1)}),
        ),
        winner_id=1,
    )
    with pytest.raises(RaceValidationError):
        fit_conditional_logit([extra], SCHEMA, horizon=H)
