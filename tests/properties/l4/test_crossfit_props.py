"""SPEC-031 property: the manifest's core guarantee — a property test MUST fail if any
stage-two training row's fundamental probability came from a model that saw that race.

Over generated multi-day corpora: every OOF row's provenance is strictly earlier than the
priced race and never contains it; universe accounting is exact; the plan is deterministic;
and a contaminated row is always caught by the consumption-side verifier.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from l4_pricing.conditional_logit import SeparationError
from l4_pricing.crossfit import CrossFitViolation, assert_out_of_fold, cross_fit
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow

from sport_core.clustering import ChronologyKey, ClusterAssignment, ClusterId, calendar_day_assignment


def _ca(day: date) -> ClusterAssignment:
    # racing cluster assignment for tests (A4): meeting-day identity + chronology
    return calendar_day_assignment("horse_racing", day)

pytestmark = pytest.mark.spec("SPEC-031")

SCHEMA = FeatureSchema(names=("fav",))
H = HorizonLabel("T-2m")
BASE_DAY = date(2026, 7, 1)

_FEATURE = st.decimals(min_value=Decimal("-2"), max_value=Decimal("2"), places=1)


@st.composite
def _corpus(draw: st.DrawFn) -> list[Race]:
    n_days = draw(st.integers(min_value=2, max_value=5))
    races: list[Race] = []
    counter = 0
    for day_index in range(n_days):
        for _ in range(draw(st.integers(min_value=1, max_value=3))):
            field = draw(st.integers(min_value=2, max_value=4))
            values = [draw(_FEATURE) for _ in range(field)]
            races.append(
                Race(
                    race_id=f"r{counter}",
                    cluster=_ca(BASE_DAY + timedelta(days=day_index)),
                    runners=tuple(
                        RunnerRow(runner_id=i + 1, features={"fav": v})
                        for i, v in enumerate(values)
                    ),
                    winner_id=(counter % field) + 1,  # round-robin winners
                )
            )
            counter += 1
    return races


@settings(max_examples=40, deadline=None)
@given(corpus=_corpus())
def test_every_oof_row_is_strictly_out_of_fold(corpus: list[Race]) -> None:
    # The full-window deployment fit can legitimately refuse a chance-separable corpus;
    # such draws are outside this property's domain.
    try:
        result = cross_fit(corpus, SCHEMA, horizon=H)
    except SeparationError:
        assume(False)
        return
    races = {r.race_id: r for r in corpus}
    for row in result.oof:
        race = races[row.race_id]
        assert row.provenance.trained_through < race.cluster.chronology
        assert row.race_id not in row.provenance.training_race_ids
        assert 0.0 < row.p_fundamental < 1.0
    assert_out_of_fold(result.oof, races)  # the consumption-side verifier agrees
    assert len(result.oof_race_ids) + len(result.excluded) == len(corpus)


@settings(max_examples=40, deadline=None)
@given(corpus=_corpus())
def test_cross_fit_is_deterministic(corpus: list[Race]) -> None:
    try:
        a = cross_fit(corpus, SCHEMA, horizon=H)
        b = cross_fit(list(reversed(corpus)), SCHEMA, horizon=H)
    except SeparationError:
        assume(False)
        return
    assert [(r.race_id, r.runner_id, r.p_fundamental) for r in a.oof] == [
        (r.race_id, r.runner_id, r.p_fundamental) for r in b.oof
    ]
    assert a.deployment_model.coefficients == b.deployment_model.coefficients
    assert {e.race_id for e in a.excluded} == {e.race_id for e in b.excluded}


@settings(max_examples=40, deadline=None)
@given(corpus=_corpus(), data=st.data())
def test_any_contaminated_row_is_caught(corpus: list[Race], data: st.DataObject) -> None:
    try:
        result = cross_fit(corpus, SCHEMA, horizon=H)
    except SeparationError:
        assume(False)
        return
    assume(result.oof)
    races = {r.race_id: r for r in corpus}
    index = data.draw(st.integers(min_value=0, max_value=len(result.oof) - 1))
    victim = result.oof[index]
    mode = data.draw(st.sampled_from(["saw_own_race", "trained_too_late"]))
    if mode == "saw_own_race":
        bad_provenance = replace(
            victim.provenance,
            training_race_ids=victim.provenance.training_race_ids | {victim.race_id},
        )
    else:
        bad_provenance = replace(
            victim.provenance,
            trained_through=races[victim.race_id].cluster.chronology,
        )
    tampered = list(result.oof)
    tampered[index] = replace(victim, provenance=bad_provenance)
    with pytest.raises(CrossFitViolation):
        assert_out_of_fold(tampered, races)
