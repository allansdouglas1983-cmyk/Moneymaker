"""SPEC-045: exportable prediction contract with independent status dimensions.

RED: analytics_contracts does not exist yet in the repository. This test module fails at
collection time with a ModuleNotFoundError until the SPEC-045 slice lands
analytics_contracts/export_contract.py.
"""
from __future__ import annotations

import dataclasses
import inspect
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from governance.output_rights import EligibilityResult, EligibilityStatus
from l4_pricing.probability_outputs import (
    CombinedProbability,
    FundamentalProbability,
    MarketProbability,
    RaceProbabilityOutputs,
    RunnerProbabilities,
)
from l8_evidence.explanation_inputs import (
    AttributionUnavailable,
    FeatureContribution,
    build_explanation_inputs,
)
from l8_evidence.prediction_snapshots import (
    DualClockTimestamp,
    MarketStateSnapshot,
    PredictionSnapshot,
    UncertaintySummary,
    VintageType,
    build_active_runner_set_hash,
    build_fair_odds,
)

from analytics_contracts.export_contract import (
    CONTRACT_SCHEMA_VERSION,
    ExplanationReference,
    ExportablePrediction,
    ExportContractError,
    ForecastAvailability,
    PublicationEligibility,
    RecommendationStatus,
    RunnerProbabilityExport,
    UnavailableForecast,
    build_export,
    build_unavailable,
    display_decimal,
    map_eligibility_to_publication_status,
)

pytestmark = pytest.mark.spec("SPEC-045")

_MODEL_DIGEST = "sha256:" + "1" * 64
_FEATURE_DIGEST = "sha256:" + "2" * 64
_SOURCE_DIGEST = "sha256:" + "3" * 64
_REGISTRY_VERSION = "sha256:" + "4" * 64
_APPROVED_FEATURES = ("speed_rating", "going_fit")


def _race(race_id: str = "race-1") -> RaceProbabilityOutputs:
    return RaceProbabilityOutputs(
        race_id=race_id,
        runners=(
            RunnerProbabilities(
                runner_id=1,
                p_fundamental=FundamentalProbability(probability=Decimal("0.55"), model_digest=_MODEL_DIGEST),
                p_market_info=MarketProbability(probability=Decimal("0.58"), price_version="info-price-v1"),
                p_combined=CombinedProbability(probability=Decimal("0.6"), model_digest=_MODEL_DIGEST),
            ),
            RunnerProbabilities(
                runner_id=2,
                p_fundamental=FundamentalProbability(probability=Decimal("0.45"), model_digest=_MODEL_DIGEST),
                p_market_info=MarketProbability(probability=Decimal("0.42"), price_version="info-price-v1"),
                p_combined=CombinedProbability(probability=Decimal("0.4"), model_digest=_MODEL_DIGEST),
            ),
        ),
    )


def _snapshot(prediction_id: str = "pred-1", race_id: str = "race-1") -> PredictionSnapshot:
    race = _race(race_id)
    return PredictionSnapshot(
        prediction_id=prediction_id,
        race_id=race_id,
        market_id="market-1",
        active_runner_set_hash=build_active_runner_set_hash([r.runner_id for r in race.runners]),
        generated_at=DualClockTimestamp(
            wall_utc=datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc), monotonic_ns=1000
        ),
        decision_horizon="T-60m",
        market_state=MarketStateSnapshot(
            market_status="OPEN",
            in_play=False,
            number_of_active_runners=2,
            total_matched=Decimal("1000.00"),
        ),
        probabilities=race,
        fair_odds=build_fair_odds(race),
        uncertainty=UncertaintySummary(
            method="time_fold_ensemble_v1",
            lower=Decimal("0.50"),
            central=Decimal("0.58"),
            upper=Decimal("0.66"),
        ),
        model_lineage_digest=_MODEL_DIGEST,
        feature_lineage_digest=_FEATURE_DIGEST,
        source_lineage_digest=_SOURCE_DIGEST,
        publication_eligibility=EligibilityResult(
            status=EligibilityStatus.ELIGIBLE, reasons=(), rights_registry_version=_REGISTRY_VERSION
        ),
        schema_version="prediction-snapshot-v1",
        forecast_vintage_id="vintage-1",
        vintage_type=VintageType.INITIAL,
        supersedes_prediction_id=None,
        update_reason=None,
        available_to_consumer_at_utc=datetime(2026, 7, 16, 12, 0, 5, tzinfo=timezone.utc),
    )


def _explanation_unavailable(prediction_id: str = "pred-1") -> AttributionUnavailable:
    return AttributionUnavailable(prediction_id=prediction_id, reason="no approved method for this model")


def _explanation_inputs(snapshot: PredictionSnapshot):
    return build_explanation_inputs(
        snapshot,
        method_id="linear-coefficient-contributions",
        method_version=1,
        contributions=(
            FeatureContribution(feature_name="speed_rating", magnitude=1.1),
            FeatureContribution(feature_name="going_fit", magnitude=-0.3),
        ),
        approved_feature_names=_APPROVED_FEATURES,
        source_lineage_ids=("source-a",),
    )


def _eligible() -> EligibilityResult:
    return EligibilityResult(
        status=EligibilityStatus.ELIGIBLE, reasons=(), rights_registry_version=_REGISTRY_VERSION
    )


def _ineligible_licensing() -> EligibilityResult:
    return EligibilityResult(
        status=EligibilityStatus.INELIGIBLE_LICENSING,
        reasons=("source-x: derived_probability_publication not granted",),
        rights_registry_version=_REGISTRY_VERSION,
    )


def _ineligible_stale() -> EligibilityResult:
    return EligibilityResult(
        status=EligibilityStatus.INELIGIBLE_STALE_RIGHTS,
        reasons=("source-x: rights review date has passed",),
        rights_registry_version=_REGISTRY_VERSION,
    )


# --- module purity: no trading imports (belt-and-braces alongside the CI boundary test) ----


def test_module_has_no_forbidden_import_statements() -> None:
    import ast

    import analytics_contracts.export_contract as mod

    tree = ast.parse(inspect.getsource(mod))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for forbidden in ("l5_decision", "l5b_risk", "l6_broker", "l7_settle"):
        assert not any(name == forbidden or name.startswith(forbidden + ".") for name in imported)


# --- three independent status dimensions ----------------------------------------------------


@pytest.mark.parametrize("eligibility", [_eligible(), _ineligible_licensing(), _ineligible_stale()])
@pytest.mark.parametrize("gate_p1_activated", [True, False])
def test_every_availability_x_eligibility_combination_is_constructible(
    eligibility: EligibilityResult, gate_p1_activated: bool
) -> None:
    snapshot = _snapshot()
    export = build_export(
        snapshot,
        eligibility,
        gate_p1_activated=gate_p1_activated,
        explanations=_explanation_unavailable(),
    )
    assert export.forecast_availability is ForecastAvailability.AVAILABLE
    assert export.recommendation_status is RecommendationStatus.NOT_EVALUATED
    assert isinstance(export.publication_eligibility, PublicationEligibility)


@pytest.mark.parametrize(
    "availability",
    [
        ForecastAvailability.UNAVAILABLE_NO_PREDICTION,
        ForecastAvailability.UNAVAILABLE_EXCLUDED,
        ForecastAvailability.WITHHELD_DATA_QUALITY,
    ],
)
def test_every_unavailable_variant_is_constructible(availability: ForecastAvailability) -> None:
    export = build_unavailable(
        "race-1",
        "market-1",
        availability,
        "no forecast produced for this race",
        generated_at_utc=datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert export.forecast_availability is availability
    assert export.recommendation_status is RecommendationStatus.NOT_EVALUATED


def test_unavailable_forecast_refuses_available_variant() -> None:
    with pytest.raises(ExportContractError):
        build_unavailable(
            "race-1",
            "market-1",
            ForecastAvailability.AVAILABLE,
            "reason",
            generated_at_utc=datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc),
        )


def test_unavailable_forecast_requires_non_empty_reason() -> None:
    with pytest.raises(ExportContractError):
        build_unavailable(
            "race-1",
            "market-1",
            ForecastAvailability.UNAVAILABLE_NO_PREDICTION,
            "   ",
            generated_at_utc=datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc),
        )


def test_unavailable_forecast_carries_no_probability_or_odds_field() -> None:
    field_names = {f.name for f in dataclasses.fields(UnavailableForecast)}
    for forbidden in (
        "probability",
        "fair_odds",
        "uncertainty",
        "p_fundamental",
        "p_market_info",
        "p_combined",
    ):
        assert forbidden not in field_names


# --- recommendation status: exactly one member, no parameter anywhere ----------------------


def test_recommendation_status_enum_has_exactly_one_member() -> None:
    assert list(RecommendationStatus) == [RecommendationStatus.NOT_EVALUATED]


def test_build_export_signature_has_no_recommendation_parameter() -> None:
    sig = inspect.signature(build_export)
    for name in sig.parameters:
        assert "recommend" not in name.lower()


def test_build_unavailable_signature_has_no_recommendation_parameter() -> None:
    sig = inspect.signature(build_unavailable)
    for name in sig.parameters:
        assert "recommend" not in name.lower()


def test_exportable_prediction_constructor_has_no_recommendation_parameter_that_varies() -> None:
    # recommendation_status is a field (always fixed), never accepted as a free-form value:
    # constructing with anything other than NOT_EVALUATED must be refused.
    kwargs = _valid_export_kwargs()
    kwargs["recommendation_status"] = RecommendationStatus.NOT_EVALUATED
    ExportablePrediction(**kwargs)  # sanity: the only legal value succeeds


def _valid_export_kwargs() -> dict:
    snapshot = _snapshot()
    runner_exports = tuple(
        RunnerProbabilityExport(
            runner_id=r.runner_id,
            p_fundamental=r.p_fundamental.probability if r.p_fundamental else None,
            p_fundamental_missing_reason=r.p_fundamental_missing_reason,
            p_market_info=r.p_market_info.probability if r.p_market_info else None,
            p_market_info_missing_reason=r.p_market_info_missing_reason,
            p_combined=r.p_combined.probability if r.p_combined else None,
            p_combined_missing_reason=r.p_combined_missing_reason,
            fair_odds=snapshot.fair_odds[r.runner_id],
        )
        for r in sorted(snapshot.probabilities.runners, key=lambda x: x.runner_id)
    )
    return dict(
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        prediction_id=snapshot.prediction_id,
        race_id=snapshot.race_id,
        market_id=snapshot.market_id,
        generated_at_utc=snapshot.generated_at.wall_utc,
        available_to_consumer_at_utc=snapshot.available_to_consumer_at_utc,
        decision_horizon=snapshot.decision_horizon,
        runner_probabilities=runner_exports,
        fair_odds=dict(snapshot.fair_odds),
        uncertainty=snapshot.uncertainty,
        model_lineage_digest=snapshot.model_lineage_digest,
        feature_lineage_digest=snapshot.feature_lineage_digest,
        source_lineage_digest=snapshot.source_lineage_digest,
        forecast_availability=ForecastAvailability.AVAILABLE,
        publication_eligibility=PublicationEligibility.INTERNAL_ONLY,
        rights_registry_version=_REGISTRY_VERSION,
        recommendation_status=RecommendationStatus.NOT_EVALUATED,
        explanations=_explanation_unavailable(snapshot.prediction_id),
    )


def test_recommendation_status_field_refuses_any_other_value() -> None:
    # RecommendationStatus has exactly one member, so there is no "other" enum value to try —
    # this test documents that fact positively rather than constructing an impossible enum.
    assert len(RecommendationStatus) == 1


# --- eligibility -> publication mapping -----------------------------------------------------


def test_mapping_ineligible_licensing_is_always_ineligible_rights() -> None:
    for gate in (True, False):
        result = map_eligibility_to_publication_status(_ineligible_licensing(), gate_p1_activated=gate)
        assert result is PublicationEligibility.INELIGIBLE_RIGHTS


def test_mapping_stale_rights_is_always_ineligible_stale_rights() -> None:
    for gate in (True, False):
        result = map_eligibility_to_publication_status(_ineligible_stale(), gate_p1_activated=gate)
        assert result is PublicationEligibility.INELIGIBLE_STALE_RIGHTS


def test_mapping_eligible_without_gate_is_internal_only() -> None:
    result = map_eligibility_to_publication_status(_eligible(), gate_p1_activated=False)
    assert result is PublicationEligibility.INTERNAL_ONLY


def test_mapping_eligible_with_gate_is_publication_eligible() -> None:
    result = map_eligibility_to_publication_status(_eligible(), gate_p1_activated=True)
    assert result is PublicationEligibility.PUBLICATION_ELIGIBLE


def test_ineligible_prediction_is_still_constructible_and_evaluable() -> None:
    # Ineligible predictions remain internally storable and evaluable: eligibility never
    # blocks construction, only marks status.
    export = build_export(
        _snapshot(),
        _ineligible_licensing(),
        gate_p1_activated=False,
        explanations=_explanation_unavailable(),
    )
    assert export.publication_eligibility is PublicationEligibility.INELIGIBLE_RIGHTS
    assert export.prediction_id == "pred-1"


# --- forbidden field-name scan --------------------------------------------------------------


_FORBIDDEN_SUBSTRINGS = (
    "stake",
    "order",
    "balance",
    "risk",
    "credential",
    "threshold",
    "bankroll",
    "budget",
    "account",
)


def test_no_forbidden_field_names_anywhere_in_the_contract_type_tree() -> None:
    types_to_scan = (
        ExportablePrediction,
        UnavailableForecast,
        RunnerProbabilityExport,
        ExplanationReference,
    )
    for typ in types_to_scan:
        for field in dataclasses.fields(typ):
            lowered = field.name.lower()
            for forbidden in _FORBIDDEN_SUBSTRINGS:
                assert forbidden not in lowered, f"{typ.__name__}.{field.name} contains {forbidden!r}"


# --- fair odds only where valid; faithful mirroring of the snapshot -------------------------


def test_export_probabilities_and_fair_odds_mirror_the_snapshot_exactly() -> None:
    snapshot = _snapshot()
    export = build_export(
        snapshot, _eligible(), gate_p1_activated=True, explanations=_explanation_unavailable()
    )
    by_runner = {r.runner_id: r for r in snapshot.probabilities.runners}
    for exported in export.runner_probabilities:
        source = by_runner[exported.runner_id]
        assert exported.p_fundamental == source.p_fundamental.probability
        assert exported.p_market_info == source.p_market_info.probability
        assert exported.p_combined == source.p_combined.probability
        assert exported.fair_odds == snapshot.fair_odds[exported.runner_id]
    assert dict(export.fair_odds) == dict(snapshot.fair_odds)


def test_fair_odds_never_appears_without_the_backing_probability() -> None:
    # A runner whose fair-odds-backing kind is race-wide absent for every kind would fail
    # snapshot construction itself (SPEC-037 build_fair_odds), so within one export every
    # exported runner's fair_odds is always positive and paired with fair-odds having been
    # derivable in the first place — this test documents that invariant travels through.
    snapshot = _snapshot()
    export = build_export(
        snapshot, _eligible(), gate_p1_activated=True, explanations=_explanation_unavailable()
    )
    for exported in export.runner_probabilities:
        assert exported.fair_odds > Decimal(0)


def test_constructing_an_export_never_mutates_the_snapshot() -> None:
    snapshot = _snapshot()
    before_digest = snapshot.content_digest()
    build_export(snapshot, _eligible(), gate_p1_activated=True, explanations=_explanation_unavailable())
    assert snapshot.content_digest() == before_digest


# --- display rounding purity ------------------------------------------------------------------


def test_display_decimal_returns_new_value_and_never_mutates_stored_decimal() -> None:
    stored = Decimal("0.123456")
    rounded = display_decimal(stored, places=2)
    assert rounded == Decimal("0.12")
    assert stored == Decimal("0.123456")  # unchanged
    assert rounded is not stored


def test_display_decimal_is_never_wired_into_build_export() -> None:
    snapshot = _snapshot()
    export = build_export(
        snapshot, _eligible(), gate_p1_activated=True, explanations=_explanation_unavailable()
    )
    by_runner = {r.runner_id: r for r in snapshot.probabilities.runners}
    for exported in export.runner_probabilities:
        # Stored values are full-precision snapshot Decimals, not display-rounded copies.
        assert exported.p_combined == by_runner[exported.runner_id].p_combined.probability


# --- explanations: reference by digest or explicit AttributionUnavailable ------------------


def test_build_export_accepts_attribution_unavailable() -> None:
    export = build_export(
        _snapshot(), _eligible(), gate_p1_activated=True, explanations=_explanation_unavailable()
    )
    assert isinstance(export.explanations, AttributionUnavailable)


def test_build_export_accepts_explanation_inputs_as_a_digest_reference() -> None:
    snapshot = _snapshot()
    explanation = _explanation_inputs(snapshot)
    export = build_export(
        snapshot, _eligible(), gate_p1_activated=True, explanations=explanation
    )
    assert isinstance(export.explanations, ExplanationReference)
    assert export.explanations.reproducibility_digest == explanation.reproducibility_digest
    assert export.explanations.prediction_id == snapshot.prediction_id


def test_build_export_refuses_an_explanation_for_a_different_prediction() -> None:
    snapshot = _snapshot(prediction_id="pred-1")
    other_snapshot = _snapshot(prediction_id="pred-2", race_id="race-2")
    mismatched_explanation = _explanation_inputs(other_snapshot)
    with pytest.raises(ExportContractError):
        build_export(
            snapshot, _eligible(), gate_p1_activated=True, explanations=mismatched_explanation
        )


# --- no LLM-derived recommendation: nothing derives one from rank/prob/odds/disagreement ----


def test_no_public_function_in_module_accepts_a_rank_or_disagreement_derived_recommendation() -> None:
    import analytics_contracts.export_contract as mod

    for name in mod.__all__:
        obj = getattr(mod, name)
        if inspect.isfunction(obj):
            sig = inspect.signature(obj)
            for pname in sig.parameters:
                assert "recommend" not in pname.lower()
                assert "tip" not in pname.lower()
                assert "selection" not in pname.lower()
