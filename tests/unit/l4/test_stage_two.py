"""SPEC-032: stage-two market combination — score = alpha*ln(p_fund) + beta*ln(p_market),
softmax within race, (alpha, beta) by MLE on the winner.

Type coupling with SPEC-031: training accepts only provenance-carrying OOFFundamental values
and re-verifies out-of-fold-ness at consumption; the market input is l5's MarketInfoPrice, so
SPEC-051's price separation extends upstream. Recovery fixtures are closed-form: two
interleaved race designs identify alpha and beta independently with exact optima of 1.
"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest

from l4_pricing.crossfit import CrossFitViolation, OOFFundamental, StageOneProvenance
from l4_pricing.horizon import HorizonLabel, HorizonMismatch
from l4_pricing.races import Race, RaceValidationError, RunnerRow
from l4_pricing.stage_two import (
    CollinearInputsError,
    CombinedModel,
    StageTwoFitResult,
    combine,
    fit_stage_two,
    predict_combined,
)
from l5_decision.prices import MarketInfoPrice

from sport_core.clustering import ChronologyKey, ClusterAssignment, ClusterId, calendar_day_assignment


def _ca(day: date) -> ClusterAssignment:
    # racing cluster assignment for tests (A4): meeting-day identity + chronology
    return calendar_day_assignment("horse_racing", day)

pytestmark = pytest.mark.spec("SPEC-032")

H = HorizonLabel("T-2m")
TRAIN_DAY = date(2026, 7, 1)
RACE_DAY = date(2026, 7, 2)


def _provenance() -> StageOneProvenance:
    return StageOneProvenance(
        trained_through=ChronologyKey.from_date(TRAIN_DAY),
        training_race_ids=frozenset({"train-1"}),
        training_race_ids_digest="digest-1",
        horizon=H,
    )


def _race(race_id: str, winner_id: int) -> Race:
    return Race(
        race_id=race_id,
        cluster=_ca(RACE_DAY),
        runners=(
            RunnerRow(runner_id=1, features={"f": Decimal(0)}),
            RunnerRow(runner_id=2, features={"f": Decimal(0)}),
        ),
        winner_id=winner_id,
    )


def _oof(race_id: str, p1: float) -> list[OOFFundamental]:
    prov = _provenance()
    return [
        OOFFundamental(race_id=race_id, runner_id=1, p_fundamental=p1, provenance=prov),
        OOFFundamental(race_id=race_id, runner_id=2, p_fundamental=1.0 - p1, provenance=prov),
    ]


def _market(p1: str) -> dict[int, MarketInfoPrice]:
    p = Decimal(p1)
    return {
        1: MarketInfoPrice(implied_probability=p),
        2: MarketInfoPrice(implied_probability=Decimal(1) - p),
    }


def _fixture(
    a_wins_for_one: int = 3, b_wins_for_one: int = 3
) -> tuple[list[Race], list[OOFFundamental], dict[str, dict[int, MarketInfoPrice]]]:
    """Type A: fundamental informative (0.75/0.25), market flat. Type B: the reverse.

    Winner frequencies of 3-in-4 make each parameter's closed-form optimum exactly 1
    (sigma(x * ln 3) = 3/4  =>  x = 1); 1-in-4 makes it exactly -1.
    """
    races: list[Race] = []
    oof: list[OOFFundamental] = []
    market: dict[str, dict[int, MarketInfoPrice]] = {}
    for i in range(4):
        rid = f"A{i}"
        races.append(_race(rid, 1 if i < a_wins_for_one else 2))
        oof.extend(_oof(rid, 0.75))
        market[rid] = _market("0.5")
    for i in range(4):
        rid = f"B{i}"
        races.append(_race(rid, 1 if i < b_wins_for_one else 2))
        oof.extend(_oof(rid, 0.5))
        market[rid] = _market("0.75")
    return races, oof, market


def test_alpha_and_beta_recover_their_closed_form_optima() -> None:
    races, oof, market = _fixture()
    result = fit_stage_two(races, oof, market, horizon=H)
    assert isinstance(result, StageTwoFitResult)
    assert abs(result.model.alpha - 1.0) < 1e-8
    assert abs(result.model.beta - 1.0) < 1e-8


def test_sign_separation_between_alpha_and_beta() -> None:
    races, oof, market = _fixture(a_wins_for_one=1, b_wins_for_one=3)
    result = fit_stage_two(races, oof, market, horizon=H)
    assert abs(result.model.alpha - (-1.0)) < 1e-8
    assert abs(result.model.beta - 1.0) < 1e-8


def test_collinear_inputs_are_refused() -> None:
    # p_fundamental identical to p_market everywhere: (alpha, beta) unidentified along a
    # ridge — refuse rather than return an arbitrary point.
    races: list[Race] = []
    oof: list[OOFFundamental] = []
    market: dict[str, dict[int, MarketInfoPrice]] = {}
    for i in range(4):
        rid = f"C{i}"
        races.append(_race(rid, 1 if i < 3 else 2))
        oof.extend(_oof(rid, 0.75))
        market[rid] = _market("0.75")
    with pytest.raises(CollinearInputsError):
        fit_stage_two(races, oof, market, horizon=H)


def test_training_reverifies_out_of_fold_at_consumption() -> None:
    races, oof, market = _fixture()
    contaminated = StageOneProvenance(
        trained_through=ChronologyKey.from_date(RACE_DAY),  # not strictly earlier
        training_race_ids=frozenset({"train-1"}),
        training_race_ids_digest="digest-1",
        horizon=H,
    )
    bad = OOFFundamental(race_id="A0", runner_id=1, p_fundamental=0.75, provenance=contaminated)
    tampered = [bad if (r.race_id, r.runner_id) == ("A0", 1) else r for r in oof]
    with pytest.raises(CrossFitViolation):
        fit_stage_two(races, tampered, market, horizon=H)


def test_bare_floats_cannot_enter_training() -> None:
    races, oof, market = _fixture()
    tampered = list(oof)
    tampered[0] = 0.75  # type: ignore[call-overload]
    with pytest.raises((TypeError, CrossFitViolation)):
        fit_stage_two(races, tampered, market, horizon=H)


def test_races_missing_inputs_are_excluded_with_reasons() -> None:
    # Drop one WINNER-1 race from each block (A0/B0), keeping each block at 2-of-3 so the
    # remaining corpus still has finite MLE optima (dropping the sole runner-2 win would
    # create complete separation, which the fit rightly refuses).
    races, oof, market = _fixture()
    market.pop("A0")  # no market price for A0
    oof = [r for r in oof if r.race_id != "B0"]  # no fundamentals for B0
    result = fit_stage_two(races, oof, market, horizon=H)
    excluded = {e.race_id: e.reason for e in result.excluded}
    assert set(excluded) == {"A0", "B0"}
    assert "market" in excluded["A0"].lower()
    assert "fundamental" in excluded["B0"].lower()
    assert len(result.used_race_ids) + len(result.excluded) == len(races)


def test_fit_requires_winners() -> None:
    races, oof, market = _fixture()
    races[0] = Race(
        race_id="A0", cluster=_ca(RACE_DAY), runners=races[0].runners, winner_id=None
    )
    with pytest.raises(RaceValidationError):
        fit_stage_two(races, oof, market, horizon=H)


def test_combine_is_a_pure_normalised_softmax() -> None:
    c = combine(
        alpha=1.0,
        beta=1.0,
        p_fundamental={1: 0.75, 2: 0.25},
        p_market={1: MarketInfoPrice(implied_probability=Decimal("0.5")),
                  2: MarketInfoPrice(implied_probability=Decimal("0.5"))},
    )
    assert set(c) == {1, 2}
    assert abs(math.fsum(c.values()) - 1.0) < 1e-12
    # alpha=1, beta=1 with a flat market reproduces the fundamental exactly.
    assert abs(c[1] - 0.75) < 1e-12


def test_combine_refuses_mismatched_runner_sets() -> None:
    with pytest.raises(RaceValidationError):
        combine(
            alpha=1.0,
            beta=1.0,
            p_fundamental={1: 0.75, 2: 0.25},
            p_market={1: MarketInfoPrice(implied_probability=Decimal("0.5"))},
        )


def test_combine_refuses_out_of_range_fundamentals() -> None:
    with pytest.raises(RaceValidationError):
        combine(
            alpha=1.0,
            beta=1.0,
            p_fundamental={1: 0.0, 2: 1.0},
            p_market={1: MarketInfoPrice(implied_probability=Decimal("0.5")),
                      2: MarketInfoPrice(implied_probability=Decimal("0.5"))},
        )


def test_predict_combined_enforces_the_horizon_door() -> None:
    races, oof, market = _fixture()
    model = fit_stage_two(races, oof, market, horizon=H).model
    assert isinstance(model, CombinedModel)
    p_fund = {1: 0.6, 2: 0.4}
    with pytest.raises(HorizonMismatch):
        predict_combined(model, p_fund, _market("0.5"), horizon=HorizonLabel("T-60s"))
    c = predict_combined(model, p_fund, _market("0.5"), horizon=H)
    assert abs(math.fsum(c.values()) - 1.0) < 1e-12


def test_model_records_lineage() -> None:
    races, oof, market = _fixture()
    model = fit_stage_two(races, oof, market, horizon=H).model
    assert model.training_race_ids == frozenset({f"A{i}" for i in range(4)} | {f"B{i}" for i in range(4)})
    assert model.trained_through == ChronologyKey.from_date(RACE_DAY)
    assert model.stage_one_provenance_digest
    assert model.horizon == H
    again = fit_stage_two(races, oof, market, horizon=H).model
    assert again.stage_one_provenance_digest == model.stage_one_provenance_digest
    assert (again.alpha, again.beta) == (model.alpha, model.beta)  # bit-deterministic
