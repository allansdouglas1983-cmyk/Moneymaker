"""SPEC-037: immutable prediction snapshots with forecast vintage lineage."""
from __future__ import annotations

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
    DuplicatePredictionError,
    MarketStateSnapshot,
    PredictionSnapshot,
    SnapshotChainError,
    SnapshotStore,
    SnapshotValidationError,
    UncertaintySummary,
    UpdateReason,
    VintageType,
    build_active_runner_set_hash,
    build_fair_odds,
)

pytestmark = pytest.mark.spec("SPEC-037")

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


def _clock(ns: int = 1_000) -> DualClockTimestamp:
    return DualClockTimestamp(wall_utc=datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc), monotonic_ns=ns)


def _market_state() -> MarketStateSnapshot:
    return MarketStateSnapshot(
        market_status="OPEN",
        in_play=False,
        number_of_active_runners=2,
        total_matched=Decimal("1000.00"),
    )


def _uncertainty() -> UncertaintySummary:
    return UncertaintySummary(
        method="time_fold_ensemble_v1",
        lower=Decimal("0.50"),
        central=Decimal("0.58"),
        upper=Decimal("0.66"),
    )


def _eligibility() -> EligibilityResult:
    return EligibilityResult(
        status=EligibilityStatus.ELIGIBLE, reasons=(), rights_registry_version=_REGISTRY_VERSION
    )


def _snapshot(
    *,
    race_id: str = "race-1",
    prediction_id: str = "pred-1",
    vintage_type: VintageType = VintageType.INITIAL,
    supersedes_prediction_id: str | None = None,
    update_reason: UpdateReason | None = None,
    race: RaceProbabilityOutputs | None = None,
) -> PredictionSnapshot:
    race = race if race is not None else _race(race_id)
    return PredictionSnapshot(
        prediction_id=prediction_id,
        race_id=race_id,
        market_id="market-1",
        active_runner_set_hash=build_active_runner_set_hash([r.runner_id for r in race.runners]),
        generated_at=_clock(),
        decision_horizon="T-60m",
        market_state=_market_state(),
        probabilities=race,
        fair_odds=build_fair_odds(race),
        uncertainty=_uncertainty(),
        model_lineage_digest=_MODEL_DIGEST,
        feature_lineage_digest=_FEATURE_DIGEST,
        source_lineage_digest=_SOURCE_DIGEST,
        publication_eligibility=_eligibility(),
        schema_version="prediction-snapshot-v1",
        forecast_vintage_id="vintage-1",
        vintage_type=vintage_type,
        supersedes_prediction_id=supersedes_prediction_id,
        update_reason=update_reason,
        available_to_consumer_at_utc=datetime(2026, 7, 16, 12, 0, 5, tzinfo=timezone.utc),
    )


# --- immutability -----------------------------------------------------------------------


def test_snapshot_is_frozen() -> None:
    snapshot = _snapshot()
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.prediction_id = "other"  # type: ignore[misc]


def test_uncertainty_summary_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _uncertainty().method = "x"  # type: ignore[misc]


def test_dual_clock_timestamp_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _clock().monotonic_ns = 2  # type: ignore[misc]


# --- no outcome fields --------------------------------------------------------------------


def test_snapshot_has_no_outcome_settlement_or_bsp_fields() -> None:
    field_names = {f.name for f in dataclasses.fields(PredictionSnapshot)}
    forbidden_substrings = ("result", "bsp", "settlement", "winner", "outcome", "actual_off")
    for name in field_names:
        lowered = name.lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in lowered, f"field {name!r} looks like a post-outcome field"


# --- vintage / supersedes validation matrix ------------------------------------------------


def test_initial_with_supersedes_is_refused() -> None:
    with pytest.raises(SnapshotValidationError):
        _snapshot(vintage_type=VintageType.INITIAL, supersedes_prediction_id="pred-0")


def test_initial_with_update_reason_is_refused() -> None:
    with pytest.raises(SnapshotValidationError):
        _snapshot(vintage_type=VintageType.INITIAL, update_reason=UpdateReason.NON_RUNNER)


def test_updated_without_supersedes_is_refused() -> None:
    with pytest.raises(SnapshotValidationError):
        _snapshot(
            prediction_id="pred-2",
            vintage_type=VintageType.UPDATED,
            update_reason=UpdateReason.NON_RUNNER,
        )


def test_updated_without_update_reason_is_refused() -> None:
    with pytest.raises(SnapshotValidationError):
        _snapshot(
            prediction_id="pred-2",
            vintage_type=VintageType.UPDATED,
            supersedes_prediction_id="pred-1",
        )


def test_updated_with_mismatched_reason_is_refused() -> None:
    with pytest.raises(SnapshotValidationError):
        _snapshot(
            prediction_id="pred-2",
            vintage_type=VintageType.UPDATED,
            supersedes_prediction_id="pred-1",
            update_reason=UpdateReason.DATA_CORRECTION,
        )


def test_correction_requires_data_correction_reason() -> None:
    with pytest.raises(SnapshotValidationError):
        _snapshot(
            prediction_id="pred-2",
            vintage_type=VintageType.CORRECTION,
            supersedes_prediction_id="pred-1",
            update_reason=UpdateReason.NON_RUNNER,
        )
    snapshot = _snapshot(
        prediction_id="pred-2",
        vintage_type=VintageType.CORRECTION,
        supersedes_prediction_id="pred-1",
        update_reason=UpdateReason.DATA_CORRECTION,
    )
    assert snapshot.vintage_type is VintageType.CORRECTION


def test_snapshot_cannot_supersede_itself() -> None:
    with pytest.raises(SnapshotValidationError):
        _snapshot(
            prediction_id="pred-1",
            vintage_type=VintageType.UPDATED,
            supersedes_prediction_id="pred-1",
            update_reason=UpdateReason.NON_RUNNER,
        )


# --- active runner set hash / non-runner change ---------------------------------------------


def test_active_runner_set_hash_mismatch_is_refused() -> None:
    race = _race()
    with pytest.raises(SnapshotValidationError):
        PredictionSnapshot(
            prediction_id="pred-1",
            race_id="race-1",
            market_id="market-1",
            active_runner_set_hash="sha256:" + "0" * 64,
            generated_at=_clock(),
            decision_horizon="T-60m",
            market_state=_market_state(),
            probabilities=race,
            fair_odds=build_fair_odds(race),
            uncertainty=_uncertainty(),
            model_lineage_digest=_MODEL_DIGEST,
            feature_lineage_digest=_FEATURE_DIGEST,
            source_lineage_digest=_SOURCE_DIGEST,
            publication_eligibility=_eligibility(),
            schema_version="prediction-snapshot-v1",
            forecast_vintage_id="vintage-1",
            vintage_type=VintageType.INITIAL,
            supersedes_prediction_id=None,
            update_reason=None,
            available_to_consumer_at_utc=datetime(2026, 7, 16, 12, 0, 5, tzinfo=timezone.utc),
        )


def test_non_runner_change_produces_new_hash_and_updated_vintage() -> None:
    full_race = _race()
    reduced_race = RaceProbabilityOutputs(
        race_id="race-1",
        runners=(
            RunnerProbabilities(
                runner_id=1,
                p_combined=CombinedProbability(probability=Decimal("0.7"), model_digest=_MODEL_DIGEST),
                p_fundamental_missing_reason="not modelled in this test",
                p_market_info_missing_reason="not modelled in this test",
            ),
            RunnerProbabilities(
                runner_id=3,
                p_combined=CombinedProbability(probability=Decimal("0.3"), model_digest=_MODEL_DIGEST),
                p_fundamental_missing_reason="not modelled in this test",
                p_market_info_missing_reason="not modelled in this test",
            ),
        ),
    )
    initial = _snapshot(race=full_race)
    updated = _snapshot(
        prediction_id="pred-2",
        vintage_type=VintageType.UPDATED,
        supersedes_prediction_id="pred-1",
        update_reason=UpdateReason.NON_RUNNER,
        race=reduced_race,
    )
    assert initial.active_runner_set_hash != updated.active_runner_set_hash


# --- fair odds derivation ---------------------------------------------------------------


def test_fair_odds_is_exact_decimal_inversion() -> None:
    race = _race()
    odds = build_fair_odds(race)
    assert odds[1] == (Decimal(1) / Decimal("0.6")).quantize(Decimal("0.0001"))
    assert odds[2] == (Decimal(1) / Decimal("0.4")).quantize(Decimal("0.0001"))


def test_fair_odds_must_cover_exactly_the_race_runner_ids() -> None:
    race = _race()
    with pytest.raises(SnapshotValidationError):
        PredictionSnapshot(
            prediction_id="pred-1",
            race_id="race-1",
            market_id="market-1",
            active_runner_set_hash=build_active_runner_set_hash([r.runner_id for r in race.runners]),
            generated_at=_clock(),
            decision_horizon="T-60m",
            market_state=_market_state(),
            probabilities=race,
            fair_odds={1: Decimal("1.5")},
            uncertainty=_uncertainty(),
            model_lineage_digest=_MODEL_DIGEST,
            feature_lineage_digest=_FEATURE_DIGEST,
            source_lineage_digest=_SOURCE_DIGEST,
            publication_eligibility=_eligibility(),
            schema_version="prediction-snapshot-v1",
            forecast_vintage_id="vintage-1",
            vintage_type=VintageType.INITIAL,
            supersedes_prediction_id=None,
            update_reason=None,
            available_to_consumer_at_utc=datetime(2026, 7, 16, 12, 0, 5, tzinfo=timezone.utc),
        )


# --- digest determinism (unit-level sanity; property test covers this exhaustively) ----------


def test_content_digest_is_sha256_hex() -> None:
    digest = _snapshot().content_digest()
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64


def test_content_digest_changes_when_a_field_changes() -> None:
    a = _snapshot()
    b = _snapshot(prediction_id="pred-2", vintage_type=VintageType.INITIAL)
    assert a.content_digest() != b.content_digest()


# --- dual clocks -------------------------------------------------------------------------


def test_dual_clock_requires_utc() -> None:
    with pytest.raises(SnapshotValidationError):
        DualClockTimestamp(wall_utc=datetime(2026, 7, 16, 12, 0, 0), monotonic_ns=1)


# --- SnapshotStore: append-only, chain derivation -----------------------------------------


def test_append_refuses_duplicate_prediction_id() -> None:
    store = SnapshotStore()
    store.append(_snapshot())
    with pytest.raises(DuplicatePredictionError):
        store.append(_snapshot())


def test_append_refuses_unknown_supersedes() -> None:
    store = SnapshotStore()
    orphan = _snapshot(
        prediction_id="pred-2",
        vintage_type=VintageType.UPDATED,
        supersedes_prediction_id="does-not-exist",
        update_reason=UpdateReason.NON_RUNNER,
    )
    with pytest.raises(SnapshotChainError):
        store.append(orphan)


def test_append_refuses_chain_race_market_mismatch() -> None:
    store = SnapshotStore()
    store.append(_snapshot())
    mismatched = _snapshot(
        prediction_id="pred-2",
        race_id="race-2",
        vintage_type=VintageType.UPDATED,
        supersedes_prediction_id="pred-1",
        update_reason=UpdateReason.NON_RUNNER,
    )
    with pytest.raises(SnapshotChainError):
        store.append(mismatched)


def test_append_refuses_a_second_supersession_of_the_same_parent() -> None:
    store = SnapshotStore()
    store.append(_snapshot())
    store.append(
        _snapshot(
            prediction_id="pred-2",
            vintage_type=VintageType.UPDATED,
            supersedes_prediction_id="pred-1",
            update_reason=UpdateReason.NON_RUNNER,
        )
    )
    fork = _snapshot(
        prediction_id="pred-3",
        vintage_type=VintageType.UPDATED,
        supersedes_prediction_id="pred-1",
        update_reason=UpdateReason.MARKET_STATE_REFRESH,
    )
    with pytest.raises(SnapshotChainError):
        store.append(fork)


def test_store_has_no_update_or_delete_api() -> None:
    public_methods = {
        name
        for name, _ in inspect.getmembers(SnapshotStore, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    assert public_methods == {"append", "snapshot_by_id", "latest_for", "all_vintages"}


def test_latest_for_is_derived_by_walking_the_chain() -> None:
    store = SnapshotStore()
    store.append(_snapshot())
    store.append(
        _snapshot(
            prediction_id="pred-2",
            vintage_type=VintageType.UPDATED,
            supersedes_prediction_id="pred-1",
            update_reason=UpdateReason.MARKET_STATE_REFRESH,
        )
    )
    latest = store.latest_for("race-1", "market-1")
    assert latest is not None
    assert latest.prediction_id == "pred-2"


def test_latest_for_unknown_race_returns_none() -> None:
    store = SnapshotStore()
    assert store.latest_for("nope", "nope") is None


def test_all_vintages_returns_initial_to_latest_order() -> None:
    store = SnapshotStore()
    store.append(_snapshot())
    store.append(
        _snapshot(
            prediction_id="pred-2",
            vintage_type=VintageType.UPDATED,
            supersedes_prediction_id="pred-1",
            update_reason=UpdateReason.MARKET_STATE_REFRESH,
        )
    )
    store.append(
        _snapshot(
            prediction_id="pred-3",
            vintage_type=VintageType.FINAL_APPROVED_HORIZON,
            supersedes_prediction_id="pred-2",
            update_reason=UpdateReason.HORIZON_FINALISED,
        )
    )
    chain = store.all_vintages("pred-2")
    assert [s.prediction_id for s in chain] == ["pred-1", "pred-2", "pred-3"]


def test_snapshot_by_id_unknown_raises_key_error() -> None:
    store = SnapshotStore()
    with pytest.raises(KeyError):
        store.snapshot_by_id("nope")


# --- no consumer may select the best-performing vintage after the result --------------------


def test_public_api_surface_is_exactly_declared() -> None:
    import l8_evidence.prediction_snapshots as mod

    assert set(mod.__all__) == {
        "VintageType",
        "UpdateReason",
        "DualClockTimestamp",
        "MarketStateSnapshot",
        "UncertaintySummary",
        "PredictionSnapshot",
        "SnapshotStore",
        "SnapshotValidationError",
        "SnapshotChainError",
        "DuplicatePredictionError",
        "build_active_runner_set_hash",
        "build_fair_odds",
    }


def test_no_public_callable_accepts_a_result_or_winner_parameter() -> None:
    import l8_evidence.prediction_snapshots as mod

    forbidden_param_names = {"result", "winner", "outcome", "bsp", "settlement"}
    for name in mod.__all__:
        obj = getattr(mod, name)
        if inspect.isclass(obj):
            members = [
                m for _, m in inspect.getmembers(obj, predicate=inspect.isfunction) if not _.startswith("_")
            ]
        elif inspect.isfunction(obj):
            members = [obj]
        else:
            continue
        for member in members:
            params = set(inspect.signature(member).parameters)
            assert not (params & forbidden_param_names), f"{name} exposes a forbidden parameter"


# --- no import of live-trading modules -----------------------------------------------------


def test_module_does_not_import_live_trading_modules() -> None:
    import ast

    import l8_evidence.prediction_snapshots as mod

    tree = ast.parse(inspect.getsource(mod))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    forbidden = {"l5_decision", "l5b_risk", "l6_broker", "l7_settle"}
    assert not (imported_roots & forbidden), f"module imports forbidden package(s): {imported_roots & forbidden}"


# --- knowledge-time ordering & hindsight guards (founder confirmations, 2026-07-16) ----------


def test_available_to_consumer_cannot_precede_generation() -> None:
    race = _race()
    with pytest.raises(SnapshotValidationError):
        PredictionSnapshot(
            prediction_id="pred-1",
            race_id="race-1",
            market_id="market-1",
            active_runner_set_hash=build_active_runner_set_hash([r.runner_id for r in race.runners]),
            generated_at=_clock(),
            decision_horizon="T-60m",
            market_state=_market_state(),
            probabilities=race,
            fair_odds=build_fair_odds(race),
            uncertainty=_uncertainty(),
            model_lineage_digest=_MODEL_DIGEST,
            feature_lineage_digest=_FEATURE_DIGEST,
            source_lineage_digest=_SOURCE_DIGEST,
            publication_eligibility=_eligibility(),
            schema_version="prediction-snapshot-v1",
            forecast_vintage_id="vintage-1",
            vintage_type=VintageType.INITIAL,
            supersedes_prediction_id=None,
            update_reason=None,
            available_to_consumer_at_utc=datetime(2026, 7, 16, 11, 59, 59, tzinfo=timezone.utc),
        )


def test_superseding_snapshot_cannot_be_backdated_before_parent() -> None:
    # A CORRECTION (or any superseding vintage) is a NEW belief formed no earlier than its
    # parent — retrospective data repairs can never masquerade as pre-off forecasts.
    store = SnapshotStore()
    store.append(_snapshot())
    backdated = dataclasses.replace(
        _snapshot(
            prediction_id="pred-2",
            vintage_type=VintageType.CORRECTION,
            supersedes_prediction_id="pred-1",
            update_reason=UpdateReason.DATA_CORRECTION,
        ),
        generated_at=DualClockTimestamp(
            wall_utc=datetime(2026, 7, 16, 11, 0, 0, tzinfo=timezone.utc), monotonic_ns=1
        ),
        available_to_consumer_at_utc=datetime(2026, 7, 16, 11, 0, 0, tzinfo=timezone.utc),
    )
    with pytest.raises(SnapshotChainError):
        store.append(backdated)


def test_correction_keeps_the_original_vintage_in_the_chain() -> None:
    # Hindsight rewriting is impossible: correcting never removes what was believed pre-off.
    store = SnapshotStore()
    store.append(_snapshot())
    store.append(
        _snapshot(
            prediction_id="pred-2",
            vintage_type=VintageType.CORRECTION,
            supersedes_prediction_id="pred-1",
            update_reason=UpdateReason.DATA_CORRECTION,
        )
    )
    chain = store.all_vintages("pred-2")
    assert [s.prediction_id for s in chain] == ["pred-1", "pred-2"]
    assert chain[0].vintage_type is VintageType.INITIAL  # the original belief survives intact


def test_append_refuses_second_initial_root_for_same_race_market() -> None:
    store = SnapshotStore()
    store.append(_snapshot())
    with pytest.raises(SnapshotChainError):
        store.append(_snapshot(prediction_id="pred-9"))


# --- full uncertainty preservation & decision-layer separation ------------------------------


def test_uncertainty_summary_is_preserved_in_full_on_the_snapshot() -> None:
    snapshot = _snapshot()
    assert snapshot.uncertainty.method == "time_fold_ensemble_v1"
    assert snapshot.uncertainty.lower == Decimal("0.50")
    assert snapshot.uncertainty.central == Decimal("0.58")
    assert snapshot.uncertainty.upper == Decimal("0.66")


def test_uncertainty_summary_has_no_numeric_coercion() -> None:
    # The central estimate is diagnostic — it must never coerce into a number a decision
    # layer could consume as if it were the trading conservative lower bound.
    summary = _uncertainty()
    with pytest.raises(TypeError):
        float(summary)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        int(summary)  # type: ignore[call-overload]


# --- convenience indexes are fully rebuildable ----------------------------------------------


def test_store_indexes_are_rebuildable_from_snapshots_alone() -> None:
    store = SnapshotStore()
    store.append(_snapshot())
    store.append(
        _snapshot(
            prediction_id="pred-2",
            vintage_type=VintageType.UPDATED,
            supersedes_prediction_id="pred-1",
            update_reason=UpdateReason.MARKET_STATE_REFRESH,
        )
    )
    rebuilt = SnapshotStore()
    for snapshot in store.all_vintages("pred-1"):
        rebuilt.append(snapshot)
    original_latest = store.latest_for("race-1", "market-1")
    rebuilt_latest = rebuilt.latest_for("race-1", "market-1")
    assert original_latest is not None and rebuilt_latest is not None
    assert rebuilt_latest.content_digest() == original_latest.content_digest()
    assert [s.prediction_id for s in rebuilt.all_vintages("pred-2")] == [
        s.prediction_id for s in store.all_vintages("pred-2")
    ]


# --- snapshot publication_eligibility must carry the PUBLICATION vocabulary (verifier) -------


def test_snapshot_refuses_internal_vocabulary_eligibility() -> None:
    from governance.output_rights import EligibilityVocabulary

    internal = EligibilityResult(
        status=EligibilityStatus.ELIGIBLE,
        reasons=(),
        rights_registry_version=_REGISTRY_VERSION,
        vocabulary=EligibilityVocabulary.INTERNAL_RESEARCH,
    )
    race = _race()
    with pytest.raises(SnapshotValidationError):
        PredictionSnapshot(
            prediction_id="pred-v",
            race_id="race-1",
            market_id="market-1",
            active_runner_set_hash=build_active_runner_set_hash([r.runner_id for r in race.runners]),
            generated_at=_clock(),
            decision_horizon="T-60m",
            market_state=_market_state(),
            probabilities=race,
            fair_odds=build_fair_odds(race),
            uncertainty=_uncertainty(),
            model_lineage_digest=_MODEL_DIGEST,
            feature_lineage_digest=_FEATURE_DIGEST,
            source_lineage_digest=_SOURCE_DIGEST,
            publication_eligibility=internal,
            schema_version="prediction-snapshot-v1",
            forecast_vintage_id="vintage-1",
            vintage_type=VintageType.INITIAL,
            supersedes_prediction_id=None,
            update_reason=None,
            available_to_consumer_at_utc=datetime(2026, 7, 16, 12, 0, 5, tzinfo=timezone.utc),
        )
