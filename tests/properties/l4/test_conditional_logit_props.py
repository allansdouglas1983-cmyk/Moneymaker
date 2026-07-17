"""SPEC-030 properties: sum-to-1 natively across field sizes, exact permutation invariance,
per-race translation invariance, and bit-exact fit determinism.

Permutation and determinism assertions are EXACT (==): every accumulation in the fitter uses
math.fsum, which is exactly rounded and argument-order independent, so reordering runners or
races cannot change a single bit of the output.
"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from l4_pricing.conditional_logit import SeparationError, StageOneModel, fit_conditional_logit, predict_race
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow

from sport_core.clustering import ChronologyKey, ClusterAssignment, ClusterId, calendar_day_assignment


def _ca(day: date) -> ClusterAssignment:
    # racing cluster assignment for tests (A4): meeting-day identity + chronology
    return calendar_day_assignment("horse_racing", day)

pytestmark = pytest.mark.spec("SPEC-030")

DAY = date(2026, 7, 1)
SCHEMA = FeatureSchema(names=("fav",))
H = HorizonLabel("T-2m")

_FEATURE = st.decimals(min_value=Decimal("-4"), max_value=Decimal("4"), places=2)
_COEF = st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False)


def _model(coef: float) -> StageOneModel:
    return StageOneModel(
        coefficients=(coef,),
        schema=SCHEMA,
        horizon=H,
        n_races=1,
        log_likelihood=0.0,
        iterations_used=0,
        training_race_ids=frozenset({"synthetic"}),
        training_race_ids_digest="d",
        trained_through=ChronologyKey.from_date(DAY),
    )


def _race(values: list[Decimal], winner_index: int | None = None) -> Race:
    return Race(
        race_id="p1",
        cluster=_ca(DAY),
        runners=tuple(
            RunnerRow(runner_id=i + 1, features={"fav": v}) for i, v in enumerate(values)
        ),
        winner_id=None if winner_index is None else winner_index + 1,
    )


@settings(max_examples=150)
@given(values=st.lists(_FEATURE, min_size=2, max_size=8), coef=_COEF)
def test_probabilities_sum_to_one(values: list[Decimal], coef: float) -> None:
    probs = predict_race(_model(coef), _race(values), horizon=H)
    assert abs(math.fsum(probs.values()) - 1.0) < 1e-12
    assert all(0.0 < p < 1.0 or math.isclose(p, 1.0) for p in probs.values())


@settings(max_examples=150)
@given(values=st.lists(_FEATURE, min_size=2, max_size=8), coef=_COEF)
def test_runner_permutation_invariance_is_exact(values: list[Decimal], coef: float) -> None:
    forward = predict_race(_model(coef), _race(values), horizon=H)
    reversed_race = Race(
        race_id="p1",
        cluster=_ca(DAY),
        runners=tuple(
            RunnerRow(runner_id=i + 1, features={"fav": v}) for i, v in reversed(list(enumerate(values)))
        ),
        winner_id=None,
    )
    backward = predict_race(_model(coef), reversed_race, horizon=H)
    assert forward == backward  # bit-exact, not approximate


@settings(max_examples=150)
@given(values=st.lists(_FEATURE, min_size=2, max_size=8), coef=_COEF, shift=_FEATURE)
def test_per_race_feature_translation_leaves_probabilities_unchanged(
    values: list[Decimal], coef: float, shift: Decimal
) -> None:
    # Adding the same constant to a feature for every runner in a race shifts all utilities
    # equally and cannot change within-race probabilities (conditional logit identifiability).
    base = predict_race(_model(coef), _race(values), horizon=H)
    shifted = predict_race(_model(coef), _race([v + shift for v in values]), horizon=H)
    for runner_id, p in base.items():
        assert abs(shifted[runner_id] - p) < 1e-9


@settings(max_examples=40, deadline=None)
@given(
    fields=st.lists(st.integers(min_value=2, max_value=5), min_size=3, max_size=6),
    seed_values=st.lists(_FEATURE, min_size=5, max_size=5),
)
def test_fit_is_invariant_to_race_order_and_deterministic(
    fields: list[int], seed_values: list[Decimal]
) -> None:
    races = []
    for idx, k in enumerate(fields):
        runners = tuple(
            RunnerRow(runner_id=i + 1, features={"fav": seed_values[(idx + i) % len(seed_values)]})
            for i in range(k)
        )
        races.append(
            Race(
                race_id=f"r{idx}",
                cluster=_ca(DAY),
                runners=runners,
                winner_id=(idx % k) + 1,  # round-robin winners avoid systematic separation
            )
        )
    try:
        a = fit_conditional_logit(races, SCHEMA, horizon=H)
        b = fit_conditional_logit(list(reversed(races)), SCHEMA, horizon=H)
    except SeparationError:
        assume(False)
        return
    assert a.coefficients == b.coefficients  # bit-exact under race reordering
    c = fit_conditional_logit(races, SCHEMA, horizon=H)
    assert a.coefficients == c.coefficients
    assert a.training_race_ids_digest == c.training_race_ids_digest
