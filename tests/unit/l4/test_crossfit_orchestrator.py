"""A5 (audit F-06, founder order): the crossfit orchestrator is model-independent.

Fold assignment, leakage discipline, exclusions, provenance and OOF production are owned
by ``cross_fit`` itself; a stage-one FAMILY only fits and predicts through the
``StageOneFamily`` seam. Conditional logit is ONE registered implementation of that
seam, not the owner of the honest OOF path. Pins:

* a non-logit dummy family flows through the orchestrator and its rows pass the
  SPEC-031 self-check unchanged;
* provenance is the ORCHESTRATOR'S OWN bookkeeping — the dummy model carries no
  training metadata at all, and a family cannot influence trained_through /
  training_race_ids;
* a family's typed fit refusal (``StageOneFitRefusal``) becomes an explicit exclusion,
  never a crash and never a silent skip;
* the default family is conditional logit (racing behaviour unchanged — the legacy
  suite pins it), exposed as a first-class ``CONDITIONAL_LOGIT_FAMILY`` satisfying the
  same seam.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

import pytest

from l4_pricing.conditional_logit import CONDITIONAL_LOGIT_FAMILY
from l4_pricing.crossfit import assert_out_of_fold, cross_fit
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow
from l4_pricing.stage_one import StageOneFamily, StageOneFitRefusal
from sport_core.clustering import ChronologyKey, calendar_day_assignment

pytestmark = pytest.mark.spec("SPEC-031")

SCHEMA = FeatureSchema(names=("fav",))
H = HorizonLabel("T-2m")


def _race(race_id: str, day: date, winner_id: int) -> Race:
    return Race(
        race_id=race_id,
        cluster=calendar_day_assignment("horse_racing", day),
        runners=(
            RunnerRow(runner_id=1, features={"fav": Decimal(1)}),
            RunnerRow(runner_id=2, features={"fav": Decimal(0)}),
        ),
        winner_id=winner_id,
    )


def _corpus() -> list[Race]:
    d0, d1 = date(2026, 7, 1), date(2026, 7, 2)
    return [
        _race("a1", d0, 1),
        _race("a2", d0, 2),
        _race("b1", d1, 1),
        _race("b2", d1, 2),
    ]


class _MetadataFreeModel:
    """A fitted artefact that carries NO training metadata — the orchestrator must not
    need any, because provenance is its own bookkeeping."""


class _UniformFamily:
    family_id = "test-uniform-v1"

    def fit(
        self, _races: object, _schema: object, *, horizon: object, max_iter: int  # noqa: ARG002
    ) -> _MetadataFreeModel:
        return _MetadataFreeModel()

    def predict(self, _model: object, race: Race, *, horizon: object) -> Mapping[int, float]:  # noqa: ARG002
        active = [r.runner_id for r in race.runners if not r.non_runner]
        return {rid: 1.0 / len(active) for rid in active}


class _FoldRefusingFamily:
    """Refuses the (smaller) fold training windows but fits the full window — pins that
    a FOLD refusal becomes explicit exclusions while the deployment fit proceeds."""

    family_id = "test-fold-refusing-v1"

    def fit(
        self, races: Sequence[Race], _schema: object, *, horizon: object, max_iter: int  # noqa: ARG002
    ) -> _MetadataFreeModel:
        if len(races) < 3:
            raise StageOneFitRefusal("this family cannot fit this training window")
        return _MetadataFreeModel()

    def predict(self, _model: object, race: Race, *, horizon: object) -> Mapping[int, float]:  # noqa: ARG002
        active = [r.runner_id for r in race.runners if not r.non_runner]
        return {rid: 1.0 / len(active) for rid in active}


class _AlwaysRefusingFamily:
    family_id = "test-always-refusing-v1"

    def fit(
        self, _races: object, _schema: object, *, horizon: object, max_iter: int  # noqa: ARG002
    ) -> _MetadataFreeModel:
        raise StageOneFitRefusal("this family cannot fit anything")

    def predict(self, _model: object, _race: Race, *, horizon: object) -> Mapping[int, float]:  # noqa: ARG002
        raise AssertionError("predict must never be called when fit refused")


class TestOrchestratorIsModelIndependent:
    def test_non_logit_family_flows_through_with_orchestrator_owned_provenance(self) -> None:
        corpus = _corpus()
        result = cross_fit(corpus, SCHEMA, horizon=H, family=_UniformFamily())
        rows = list(result.oof)
        assert rows, "the second fold must produce OOF rows"
        assert {row.race_id for row in rows} == {"b1", "b2"}
        races_by_id = {race.race_id: race for race in corpus}
        assert_out_of_fold(rows, races_by_id)  # the SPEC-031 self-check is family-blind
        for row in rows:
            # Provenance is the orchestrator's own bookkeeping: the model carried none.
            assert row.provenance.training_race_ids == frozenset({"a1", "a2"})
            assert row.provenance.trained_through == ChronologyKey.from_date(date(2026, 7, 1))

    def test_fold_fit_refusal_is_an_explicit_exclusion(self) -> None:
        # The 2-race fold window refuses; the 4-race full window fits — the refused
        # fold's races are explicit exclusions and the deployment model still exists.
        result = cross_fit(_corpus(), SCHEMA, horizon=H, family=_FoldRefusingFamily())
        assert not list(result.oof)
        excluded_ids = {e.race_id for e in result.excluded}
        assert {"a1", "a2", "b1", "b2"} == excluded_ids
        reasons = {e.race_id: e.reason for e in result.excluded}
        assert "cannot fit" in reasons["b1"]
        assert isinstance(result.deployment_model, _MetadataFreeModel)

    def test_full_window_refusal_propagates_as_the_typed_refusal(self) -> None:
        # No deployable model can exist — the honest outcome is the typed refusal
        # itself, never a silently absent model.
        with pytest.raises(StageOneFitRefusal):
            cross_fit(_corpus(), SCHEMA, horizon=H, family=_AlwaysRefusingFamily())

    def test_conditional_logit_is_one_family_implementation(self) -> None:
        assert isinstance(CONDITIONAL_LOGIT_FAMILY, StageOneFamily)
        assert isinstance(_UniformFamily(), StageOneFamily)
        assert CONDITIONAL_LOGIT_FAMILY.family_id
        explicit = cross_fit(_corpus(), SCHEMA, horizon=H, family=CONDITIONAL_LOGIT_FAMILY)
        default = cross_fit(_corpus(), SCHEMA, horizon=H)
        assert [r.race_id for r in explicit.oof] == [r.race_id for r in default.oof]
