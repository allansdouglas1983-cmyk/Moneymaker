"""SPEC-038: predictor performance ledger with versioned benchmark registry."""
from __future__ import annotations

import dataclasses
import math
from decimal import Decimal

import pytest

from l8_evidence.predictor_metrics import (
    BenchmarkConflictError,
    BenchmarkDefinition,
    BenchmarkDefinitionError,
    BenchmarkRegistry,
    CohortEvaluationResult,
    ForecastVintagePolicy,
    ModelKind,
    OverallEvaluationResult,
    RaceEvaluationError,
    RaceEvaluationInput,
    ReliabilityBand,
    RunnerOutcome,
    coverage_rate,
    evaluate_cohorts,
    evaluate_overall,
    evaluate_race,
    reliability_by_band,
)

pytestmark = pytest.mark.spec("SPEC-038")

_INCLUSION_HASH = "sha256:" + "1" * 64
_EXCLUSION_HASH = "sha256:" + "2" * 64
_HORIZON = "T-60m"


def _bands() -> tuple[ReliabilityBand, ...]:
    return (
        ReliabilityBand(label="low", lower=Decimal("0"), upper=Decimal("0.5")),
        ReliabilityBand(label="high", lower=Decimal("0.5"), upper=Decimal("1")),
    )


def _benchmark(version: int = 1, horizon: str = _HORIZON) -> BenchmarkDefinition:
    return BenchmarkDefinition(
        benchmark_id="predictor-eval-v1",
        version=version,
        universe_version="universe-2026-07",
        forecast_vintage_policy=ForecastVintagePolicy.FINAL_APPROVED_HORIZON_ONLY,
        inclusion_hash=_INCLUSION_HASH,
        exclusion_hash=_EXCLUSION_HASH,
        coverage_policy="all scheduled UK/IRE flat races",
        decision_horizon=horizon,
        approved_reliability_bands=_bands(),
    )


def _race(
    race_id: str = "race-1",
    *,
    settled: bool = True,
    horizon: str = _HORIZON,
    model_kind: ModelKind = ModelKind.COMBINED,
    probs: tuple[Decimal, Decimal] = (Decimal("0.6"), Decimal("0.4")),
    winner_index: int = 0,
) -> RaceEvaluationInput:
    return RaceEvaluationInput(
        race_id=race_id,
        model_kind=model_kind,
        decision_horizon=horizon,
        settled=settled,
        runners=(
            RunnerOutcome(runner_id=1, probability=probs[0], is_winner=winner_index == 0),
            RunnerOutcome(runner_id=2, probability=probs[1], is_winner=winner_index == 1),
        ),
    )


class TestBenchmarkDefinition:
    def test_valid_definition_constructs(self) -> None:
        assert _benchmark().benchmark_id == "predictor-eval-v1"

    def test_version_must_be_positive(self) -> None:
        with pytest.raises(BenchmarkDefinitionError):
            BenchmarkDefinition(
                benchmark_id="b",
                version=0,
                universe_version="u",
                forecast_vintage_policy=ForecastVintagePolicy.INITIAL_ONLY,
                inclusion_hash=_INCLUSION_HASH,
                exclusion_hash=_EXCLUSION_HASH,
                coverage_policy="c",
                decision_horizon="T-60m",
                approved_reliability_bands=_bands(),
            )

    def test_bands_must_cover_zero_to_one(self) -> None:
        with pytest.raises(BenchmarkDefinitionError):
            BenchmarkDefinition(
                benchmark_id="b",
                version=1,
                universe_version="u",
                forecast_vintage_policy=ForecastVintagePolicy.INITIAL_ONLY,
                inclusion_hash=_INCLUSION_HASH,
                exclusion_hash=_EXCLUSION_HASH,
                coverage_policy="c",
                decision_horizon="T-60m",
                approved_reliability_bands=(
                    ReliabilityBand(label="low", lower=Decimal("0"), upper=Decimal("0.5")),
                ),
            )

    def test_bands_must_be_gap_free(self) -> None:
        with pytest.raises(BenchmarkDefinitionError):
            BenchmarkDefinition(
                benchmark_id="b",
                version=1,
                universe_version="u",
                forecast_vintage_policy=ForecastVintagePolicy.INITIAL_ONLY,
                inclusion_hash=_INCLUSION_HASH,
                exclusion_hash=_EXCLUSION_HASH,
                coverage_policy="c",
                decision_horizon="T-60m",
                approved_reliability_bands=(
                    ReliabilityBand(label="low", lower=Decimal("0"), upper=Decimal("0.4")),
                    ReliabilityBand(label="high", lower=Decimal("0.5"), upper=Decimal("1")),
                ),
            )

    def test_bad_hash_rejected(self) -> None:
        with pytest.raises(BenchmarkDefinitionError):
            BenchmarkDefinition(
                benchmark_id="b",
                version=1,
                universe_version="u",
                forecast_vintage_policy=ForecastVintagePolicy.INITIAL_ONLY,
                inclusion_hash="not-a-hash",
                exclusion_hash=_EXCLUSION_HASH,
                coverage_policy="c",
                decision_horizon="T-60m",
                approved_reliability_bands=_bands(),
            )


class TestBenchmarkRegistry:
    def test_register_then_lookup(self) -> None:
        registry = BenchmarkRegistry()
        definition = _benchmark()
        registry.register(definition)
        assert registry.lookup("predictor-eval-v1", 1) is definition

    def test_in_place_change_refused(self) -> None:
        registry = BenchmarkRegistry()
        registry.register(_benchmark(version=1))
        changed = dataclasses.replace(_benchmark(version=1), coverage_policy="different policy")
        with pytest.raises(BenchmarkConflictError):
            registry.register(changed)

    def test_identical_reregistration_refused(self) -> None:
        registry = BenchmarkRegistry()
        registry.register(_benchmark(version=1))
        with pytest.raises(BenchmarkConflictError):
            registry.register(_benchmark(version=1))

    def test_new_version_accepted(self) -> None:
        registry = BenchmarkRegistry()
        registry.register(_benchmark(version=1))
        registry.register(_benchmark(version=2))
        assert registry.lookup("predictor-eval-v1", 2).version == 2

    def test_lookup_missing_raises(self) -> None:
        registry = BenchmarkRegistry()
        with pytest.raises(KeyError):
            registry.lookup("nope", 1)

    def test_registry_has_no_mutation_or_delete_api(self) -> None:
        public_names = {name for name in dir(BenchmarkRegistry) if not name.startswith("_")}
        assert public_names == {"register", "lookup"}


class TestRaceEvaluationInput:
    def test_unsettled_race_refused_at_construction_is_allowed_but_evaluation_refuses(self) -> None:
        race = _race(settled=False)
        with pytest.raises(RaceEvaluationError):
            evaluate_race(race, _benchmark())

    def test_horizon_mismatch_refused(self) -> None:
        race = _race(horizon="T-30m")
        with pytest.raises(RaceEvaluationError):
            evaluate_race(race, _benchmark(horizon="T-60m"))

    def test_probabilities_must_sum_to_one(self) -> None:
        with pytest.raises(RaceEvaluationError):
            _race(probs=(Decimal("0.6"), Decimal("0.6")))

    def test_exactly_one_winner_required(self) -> None:
        with pytest.raises(RaceEvaluationError):
            RaceEvaluationInput(
                race_id="race-x",
                model_kind=ModelKind.COMBINED,
                decision_horizon=_HORIZON,
                settled=True,
                runners=(
                    RunnerOutcome(runner_id=1, probability=Decimal("0.5"), is_winner=False),
                    RunnerOutcome(runner_id=2, probability=Decimal("0.5"), is_winner=False),
                ),
            )

    def test_probability_out_of_range_refused(self) -> None:
        with pytest.raises(RaceEvaluationError):
            RaceEvaluationInput(
                race_id="race-x",
                model_kind=ModelKind.COMBINED,
                decision_horizon=_HORIZON,
                settled=True,
                runners=(
                    RunnerOutcome(runner_id=1, probability=Decimal("1.0"), is_winner=True),
                    RunnerOutcome(runner_id=2, probability=Decimal("0.0"), is_winner=False),
                ),
            )


class TestExactMetrics:
    def test_log_score_exact(self) -> None:
        race = _race(probs=(Decimal("0.5"), Decimal("0.5")))
        result = evaluate_race(race, _benchmark())
        assert result.log_score == pytest.approx(-math.log(0.5))

    def test_brier_score_exact(self) -> None:
        race = _race(probs=(Decimal("0.6"), Decimal("0.4")), winner_index=0)
        result = evaluate_race(race, _benchmark())
        # (0.6-1)^2 + (0.4-0)^2 = 0.16 + 0.16 = 0.32
        assert result.brier_score == pytest.approx(0.32)

    def test_winner_rank_favourite(self) -> None:
        race = _race(probs=(Decimal("0.6"), Decimal("0.4")), winner_index=0)
        result = evaluate_race(race, _benchmark())
        assert result.winner_rank == 1

    def test_winner_rank_second_favourite(self) -> None:
        race = _race(probs=(Decimal("0.6"), Decimal("0.4")), winner_index=1)
        result = evaluate_race(race, _benchmark())
        assert result.winner_rank == 2

    def test_field_size(self) -> None:
        race = _race()
        result = evaluate_race(race, _benchmark())
        assert result.field_size == 2


class TestOverallEvaluation:
    def test_overall_result_kind_tagged(self) -> None:
        races = [_race("race-1"), _race("race-2", winner_index=1)]
        result = evaluate_overall(
            races, _benchmark(), ModelKind.COMBINED, total_universe_races=2
        )
        assert result.model_kind is ModelKind.COMBINED
        assert result.races_evaluated == 2

    def test_kind_distinction_never_merged(self) -> None:
        races_combined = [_race("race-1", model_kind=ModelKind.COMBINED)]
        races_fundamental = [_race("race-1", model_kind=ModelKind.FUNDAMENTAL)]
        result_combined = evaluate_overall(
            races_combined, _benchmark(), ModelKind.COMBINED, total_universe_races=1
        )
        result_fundamental = evaluate_overall(
            races_fundamental, _benchmark(), ModelKind.FUNDAMENTAL, total_universe_races=1
        )
        assert result_combined.model_kind != result_fundamental.model_kind
        assert result_combined.input_digest is not None
        assert result_fundamental.input_digest is not None

    def test_mixed_kind_race_set_refused(self) -> None:
        races = [
            _race("race-1", model_kind=ModelKind.COMBINED),
            _race("race-2", model_kind=ModelKind.FUNDAMENTAL),
        ]
        with pytest.raises(RaceEvaluationError):
            evaluate_overall(races, _benchmark(), ModelKind.COMBINED, total_universe_races=2)

    def test_empty_race_set_refused(self) -> None:
        with pytest.raises(RaceEvaluationError):
            evaluate_overall([], _benchmark(), ModelKind.COMBINED, total_universe_races=0)

    def test_top1_hit_rate(self) -> None:
        races = [
            _race("race-1", winner_index=0),  # favourite wins
            _race("race-2", winner_index=1),  # favourite loses
        ]
        result = evaluate_overall(
            races, _benchmark(), ModelKind.COMBINED, total_universe_races=2
        )
        assert result.top1_hit_rate == pytest.approx(0.5)

    def test_no_field_named_performance_or_bare_roi(self) -> None:
        names = {f.name for f in dataclasses.fields(OverallEvaluationResult)}
        assert "performance" not in names
        assert "roi" not in names

    def test_roi_field_is_secondary_and_optional(self) -> None:
        races = [_race("race-1")]
        result = evaluate_overall(
            races, _benchmark(), ModelKind.COMBINED, total_universe_races=1
        )
        assert result.roi_frozen_policy_diagnostic is None


class TestCohortEvaluation:
    def test_cohort_result_distinct_type_from_overall(self) -> None:
        races = [_race("race-1"), _race("race-2", winner_index=1)]
        cohorts = evaluate_cohorts(
            races, _benchmark(), ModelKind.COMBINED, cohort_of={"race-1": "A", "race-2": "B"}
        )
        for result in cohorts:
            assert isinstance(result, CohortEvaluationResult)
            assert not isinstance(result, OverallEvaluationResult)
            assert result.cohort_label in {"A", "B"}

    def test_cohort_result_has_no_field_named_performance_or_bare_roi(self) -> None:
        names = {f.name for f in dataclasses.fields(CohortEvaluationResult)}
        assert "performance" not in names
        assert "roi" not in names

    def test_missing_cohort_label_refused(self) -> None:
        races = [_race("race-1"), _race("race-2", winner_index=1)]
        with pytest.raises(RaceEvaluationError):
            evaluate_cohorts(races, _benchmark(), ModelKind.COMBINED, cohort_of={"race-1": "A"})

    def test_overall_result_has_no_cohort_label(self) -> None:
        names = {f.name for f in dataclasses.fields(OverallEvaluationResult)}
        assert "cohort_label" not in names


class TestCoverage:
    def test_missing_race_lowers_coverage(self) -> None:
        full = coverage_rate(races_evaluated=10, total_universe_races=10)
        with_missing = coverage_rate(races_evaluated=9, total_universe_races=10)
        assert with_missing.coverage_rate < full.coverage_rate

    def test_coverage_uses_explicit_total_not_len(self) -> None:
        result = coverage_rate(races_evaluated=1, total_universe_races=100)
        assert result.coverage_rate == pytest.approx(0.01)

    def test_evaluated_cannot_exceed_universe(self) -> None:
        with pytest.raises(Exception):
            coverage_rate(races_evaluated=11, total_universe_races=10)


class TestReliabilityBands:
    def test_bands_required_no_defaults(self) -> None:
        with pytest.raises(TypeError):
            reliability_by_band([_race()])  # type: ignore[call-arg]

    def test_reliability_result_keyed_by_band_label(self) -> None:
        races = [_race("race-1", probs=(Decimal("0.6"), Decimal("0.4")))]
        result = reliability_by_band(races, _bands())
        assert set(result) == {"low", "high"}

    def test_bands_must_partition_or_rejected(self) -> None:
        with pytest.raises(BenchmarkDefinitionError):
            reliability_by_band(
                [_race()],
                (ReliabilityBand(label="only-half", lower=Decimal("0"), upper=Decimal("0.5")),),
            )


class TestInputDigest:
    def test_digest_deterministic_regardless_of_order(self) -> None:
        races_a = [_race("race-1"), _race("race-2", winner_index=1)]
        races_b = list(reversed(races_a))
        result_a = evaluate_overall(races_a, _benchmark(), ModelKind.COMBINED, total_universe_races=2)
        result_b = evaluate_overall(races_b, _benchmark(), ModelKind.COMBINED, total_universe_races=2)
        assert result_a.input_digest == result_b.input_digest

    def test_digest_changes_with_content(self) -> None:
        races_a = [_race("race-1", winner_index=0)]
        races_b = [_race("race-1", winner_index=1)]
        result_a = evaluate_overall(races_a, _benchmark(), ModelKind.COMBINED, total_universe_races=1)
        result_b = evaluate_overall(races_b, _benchmark(), ModelKind.COMBINED, total_universe_races=1)
        assert result_a.input_digest != result_b.input_digest


# --- forecast-vintage policy is ENFORCED at evaluation (verifier finding, 2026-07-16) --------


class TestVintagePolicyEnforcement:
    def test_vintage_mismatched_race_is_refused(self) -> None:
        # The benchmark pins FINAL_APPROVED_HORIZON_ONLY; an INITIAL-vintage evaluation input
        # must be refused — vintage selection is enforced in code, never by caller convention.
        from l8_evidence.prediction_snapshots import VintageType

        race = _race(vintage_type=VintageType.INITIAL)
        with pytest.raises(RaceEvaluationError):
            evaluate_race(race, _benchmark())

    def test_vintage_matched_race_is_accepted(self) -> None:
        from l8_evidence.prediction_snapshots import VintageType

        race = _race(vintage_type=VintageType.FINAL_APPROVED_HORIZON)
        result = evaluate_race(race, _benchmark())
        assert result.race_id == race.race_id

    def test_initial_only_policy_accepts_only_initial(self) -> None:
        from l8_evidence.prediction_snapshots import VintageType

        benchmark = BenchmarkDefinition(
            benchmark_id="predictor-eval-initial",
            version=1,
            universe_version="universe-2026-07",
            forecast_vintage_policy=ForecastVintagePolicy.INITIAL_ONLY,
            inclusion_hash=_INCLUSION_HASH,
            exclusion_hash=_EXCLUSION_HASH,
            coverage_policy="all scheduled UK/IRE flat races",
            decision_horizon=_HORIZON,
            approved_reliability_bands=_bands(),
        )
        assert evaluate_race(_race(vintage_type=VintageType.INITIAL), benchmark).race_id
        with pytest.raises(RaceEvaluationError):
            evaluate_race(_race(vintage_type=VintageType.FINAL_APPROVED_HORIZON), benchmark)
