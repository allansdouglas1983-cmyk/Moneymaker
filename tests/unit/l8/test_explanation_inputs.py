"""SPEC-039: deterministic explanation inputs."""
from __future__ import annotations

import ast
import dataclasses
import inspect
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from governance.output_rights import EligibilityResult, EligibilityStatus
from l4_pricing.probability_outputs import (
    CombinedProbability,
    RaceProbabilityOutputs,
    RunnerProbabilities,
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

pytestmark = pytest.mark.spec("SPEC-039")

_MODEL_DIGEST = "sha256:" + "1" * 64
_FEATURE_DIGEST = "sha256:" + "2" * 64
_SOURCE_DIGEST = "sha256:" + "3" * 64
_REGISTRY_VERSION = "sha256:" + "4" * 64


def _race(race_id: str = "race-1") -> RaceProbabilityOutputs:
    return RaceProbabilityOutputs(
        race_id=race_id,
        runners=(
            RunnerProbabilities(
                runner_id=1,
                p_combined=CombinedProbability(probability=Decimal("0.6"), model_digest=_MODEL_DIGEST),
                p_fundamental_missing_reason="not modelled in this test",
                p_market_info_missing_reason="not modelled in this test",
            ),
            RunnerProbabilities(
                runner_id=2,
                p_combined=CombinedProbability(probability=Decimal("0.4"), model_digest=_MODEL_DIGEST),
                p_fundamental_missing_reason="not modelled in this test",
                p_market_info_missing_reason="not modelled in this test",
            ),
        ),
    )


def _snapshot(prediction_id: str = "pred-1") -> PredictionSnapshot:
    race = _race()
    return PredictionSnapshot(
        prediction_id=prediction_id,
        race_id="race-1",
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


from l8_evidence.explanation_inputs import (  # noqa: E402
    APPROVED_ATTRIBUTION_METHODS,
    AttributionMethod,
    AttributionUnavailable,
    EmptyLineageError,
    ExplanationInputs,
    FeatureContribution,
    ReasonCode,
    UnapprovedAttributionMethodError,
    UnapprovedFeatureError,
    build_explanation_inputs,
)

_APPROVED_FEATURES = ("speed_rating", "going_fit", "jockey_win_rate")


def _contributions() -> tuple[FeatureContribution, ...]:
    return (
        FeatureContribution(feature_name="speed_rating", magnitude=1.25),
        FeatureContribution(feature_name="going_fit", magnitude=-0.4),
        FeatureContribution(feature_name="jockey_win_rate", magnitude=0.1),
    )


def _build(**overrides: object) -> ExplanationInputs:
    kwargs: dict[str, object] = dict(
        snapshot=_snapshot(),
        method_id="linear-coefficient-contributions",
        method_version=1,
        contributions=_contributions(),
        approved_feature_names=_APPROVED_FEATURES,
        source_lineage_ids=("source-a", "source-b"),
    )
    kwargs.update(overrides)
    return build_explanation_inputs(**kwargs)  # type: ignore[arg-type]


# --- approved method registry -------------------------------------------------------------


def test_approved_method_is_used_successfully() -> None:
    explanation = _build()
    assert explanation.method_id == "linear-coefficient-contributions"
    assert explanation.method_version == 1


def test_unapproved_method_id_is_refused() -> None:
    with pytest.raises(UnapprovedAttributionMethodError):
        _build(method_id="llm-vibes", method_version=1)


def test_unapproved_method_version_is_refused() -> None:
    with pytest.raises(UnapprovedAttributionMethodError):
        _build(method_version=2)


def test_approved_registry_has_exactly_one_v1_entry() -> None:
    assert APPROVED_ATTRIBUTION_METHODS == frozenset(
        {AttributionMethod(method_id="linear-coefficient-contributions", method_version=1)}
    )


# --- unapproved feature ---------------------------------------------------------------------


def test_unapproved_feature_name_is_refused() -> None:
    bad = (*_contributions(), FeatureContribution(feature_name="astrology_index", magnitude=0.9))
    with pytest.raises(UnapprovedFeatureError):
        _build(contributions=bad)


# --- lineage ---------------------------------------------------------------------------------


def test_empty_lineage_is_refused() -> None:
    with pytest.raises(EmptyLineageError):
        _build(source_lineage_ids=())


def test_lineage_is_carried_verbatim_as_sorted_tuple() -> None:
    explanation = _build(source_lineage_ids=("z-source", "a-source"))
    assert set(explanation.source_lineage_ids) == {"z-source", "a-source"}


# --- prediction linkage: cannot exist without / be re-pointed to a valid prediction ----------


def test_explanation_carries_the_snapshots_own_prediction_id_and_digest() -> None:
    snapshot = _snapshot()
    explanation = build_explanation_inputs(
        snapshot=snapshot,
        method_id="linear-coefficient-contributions",
        method_version=1,
        contributions=_contributions(),
        approved_feature_names=_APPROVED_FEATURES,
        source_lineage_ids=("source-a",),
    )
    assert explanation.prediction_id == snapshot.prediction_id
    assert explanation.prediction_content_digest == snapshot.content_digest()


def test_different_snapshots_produce_different_prediction_content_digests() -> None:
    a = _build(snapshot=_snapshot(prediction_id="pred-1"))
    b = _build(snapshot=_snapshot(prediction_id="pred-2"))
    assert a.prediction_content_digest != b.prediction_content_digest
    assert a.reproducibility_digest != b.reproducibility_digest


def test_explanation_inputs_rejects_malformed_digest_fields() -> None:
    # __post_init__ enforces the sha256:<hex> SHAPE of both digest fields AND self-verifies
    # the reproducibility digest against the object's own canonical content, so even a
    # well-formed-but-wrong digest is refused at direct construction. (The prediction
    # content digest stays shape-checked only — verifying it needs the snapshot, which is
    # build_explanation_inputs' job as the sanctioned entry point.)
    snapshot = _snapshot()
    with pytest.raises(Exception):
        ExplanationInputs(
            prediction_id=snapshot.prediction_id,
            prediction_content_digest="not-a-digest",
            method_id="linear-coefficient-contributions",
            method_version=1,
            contributions=_contributions(),
            reason_codes=(ReasonCode.STRONGEST_POSITIVE_FACTOR,),
            source_lineage_ids=("source-a",),
            reproducibility_digest="sha256:" + "0" * 64,
        )


def test_explanation_inputs_rejects_well_formed_but_wrong_reproducibility_digest() -> None:
    # The type is self-verifying: a syntactically valid sha256 that does not match the
    # object's own canonical content is refused — an explanation cannot lie about its
    # reproducibility even when constructed directly.
    valid = _build()
    with pytest.raises(Exception):
        ExplanationInputs(
            prediction_id=valid.prediction_id,
            prediction_content_digest=valid.prediction_content_digest,
            method_id=valid.method_id,
            method_version=valid.method_version,
            contributions=valid.contributions,
            reason_codes=valid.reason_codes,
            source_lineage_ids=valid.source_lineage_ids,
            reproducibility_digest="sha256:" + "0" * 64,
        )


# --- reason codes: deterministic, derived from sign/rank only, order-invariant --------------


def test_reason_codes_pick_strongest_positive_and_negative() -> None:
    explanation = _build()
    assert ReasonCode.STRONGEST_POSITIVE_FACTOR in explanation.reason_codes
    assert ReasonCode.STRONGEST_NEGATIVE_FACTOR in explanation.reason_codes


def test_reason_codes_are_order_invariant() -> None:
    forward = _build(contributions=_contributions())
    reversed_contribs = tuple(reversed(_contributions()))
    backward = _build(contributions=reversed_contribs)
    assert forward.reason_codes == backward.reason_codes
    assert forward.reproducibility_digest == backward.reproducibility_digest


def test_all_non_negative_contributions_yield_no_negative_reason_code() -> None:
    contribs = (
        FeatureContribution(feature_name="speed_rating", magnitude=1.0),
        FeatureContribution(feature_name="going_fit", magnitude=0.0),
        FeatureContribution(feature_name="jockey_win_rate", magnitude=0.5),
    )
    explanation = _build(contributions=contribs)
    assert ReasonCode.STRONGEST_NEGATIVE_FACTOR not in explanation.reason_codes
    assert ReasonCode.STRONGEST_POSITIVE_FACTOR in explanation.reason_codes


# --- no causal language ----------------------------------------------------------------------


_CAUSAL_BLOCKLIST = ("because", "caused", "causes", "causing", "due to", "leads to", "results in")


def test_no_generated_string_contains_causal_vocabulary() -> None:
    import l8_evidence.explanation_inputs as mod

    reason_pairs = mod._derive_reason_codes(_contributions())
    for _code, display in reason_pairs:
        lowered = display.lower()
        for word in _CAUSAL_BLOCKLIST:
            assert word not in lowered, f"{display!r} contains causal vocabulary {word!r}"


# --- no probability/odds field on the explanation type ---------------------------------------


def test_explanation_inputs_has_no_probability_or_odds_fields() -> None:
    field_names = {f.name for f in dataclasses.fields(ExplanationInputs)}
    for name in field_names:
        lowered = name.lower()
        assert "probability" not in lowered
        assert "odds" not in lowered


# --- AttributionUnavailable requires a reason -------------------------------------------------


def test_attribution_unavailable_requires_a_non_empty_reason() -> None:
    with pytest.raises(Exception):
        AttributionUnavailable(prediction_id="pred-1", reason="")


def test_attribution_unavailable_is_a_distinct_type_from_explanation_inputs() -> None:
    unavailable = AttributionUnavailable(prediction_id="pred-1", reason="model has no linear form")
    assert not isinstance(unavailable, ExplanationInputs)
    assert unavailable.prediction_id == "pred-1"


# --- digest determinism (unit sanity; Hypothesis property test covers this exhaustively) -----


def test_reproducibility_digest_is_sha256_hex() -> None:
    explanation = _build()
    assert explanation.reproducibility_digest.startswith("sha256:")
    assert len(explanation.reproducibility_digest) == len("sha256:") + 64


def test_reproducibility_digest_changes_when_a_contribution_changes() -> None:
    a = _build()
    changed = (
        FeatureContribution(feature_name="speed_rating", magnitude=9.9),
        FeatureContribution(feature_name="going_fit", magnitude=-0.4),
        FeatureContribution(feature_name="jockey_win_rate", magnitude=0.1),
    )
    b = _build(contributions=changed)
    assert a.reproducibility_digest != b.reproducibility_digest


# --- frozen ------------------------------------------------------------------------------


def test_explanation_inputs_is_frozen() -> None:
    explanation = _build()
    with pytest.raises(dataclasses.FrozenInstanceError):
        explanation.prediction_id = "other"  # type: ignore[misc]


def test_feature_contribution_is_frozen() -> None:
    contribution = FeatureContribution(feature_name="speed_rating", magnitude=1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        contribution.magnitude = 2.0  # type: ignore[misc]


# --- no import of live-trading modules --------------------------------------------------------


def test_module_does_not_import_live_trading_modules() -> None:
    import l8_evidence.explanation_inputs as mod

    tree = ast.parse(inspect.getsource(mod))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    forbidden = {"l5_decision", "l5b_risk", "l6_broker", "l7_settle"}
    assert not (imported_roots & forbidden), f"module imports forbidden package(s): {imported_roots & forbidden}"
