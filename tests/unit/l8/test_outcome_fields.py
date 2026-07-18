"""Stage-2A: structural pre-lockbox field-access guard (completes SPEC-092's deferred
data-layer block; SPEC-020/021/023 knowledge-time discipline).

The guard makes accidental outcome contamination a hard error and produces a
replay-provable manifest of exactly which field classes a pre-lockbox reader touched.
The classification here MUST equal the human-owned governance spec
``specs/evidence/outcome-field-classification-v1.yaml`` (sync test below).
"""
from __future__ import annotations

import pathlib

import pytest
import yaml

from l8_evidence.outcome_fields import (
    CLASSIFICATION_VERSION,
    OutcomeFieldAccessError,
    OutcomeFieldClass,
    PreLockboxAccessRecorder,
    assert_pre_lockbox_readable,
    classify,
    is_outcome_sentinel_value,
    is_pre_lockbox_safe,
)

pytestmark = [pytest.mark.spec("SPEC-092"), pytest.mark.spec("SPEC-021")]

_SPEC = pathlib.Path("specs/evidence/outcome-field-classification-v1.yaml")


class TestClassification:
    def test_known_safe_fields(self) -> None:
        assert classify("rc", "batb") is OutcomeFieldClass.SAFE_BEFORE_LOCKBOX
        assert classify("marketDefinition", "marketTime") is OutcomeFieldClass.SAFE_BEFORE_LOCKBOX
        assert classify("marketDefinition", "numberOfActiveRunners") is OutcomeFieldClass.SAFE_BEFORE_LOCKBOX
        assert classify("top", "pt") is OutcomeFieldClass.SAFE_BEFORE_LOCKBOX

    def test_the_result_carrier_is_outcome_controlled(self) -> None:
        # runner.status carries WINNER/LOSER — the result itself
        assert classify("runner", "status") is OutcomeFieldClass.OUTCOME_CONTROLLED
        assert classify("marketDefinition", "bspReconciled") is OutcomeFieldClass.OUTCOME_CONTROLLED
        assert classify("runner", "removalDate") is OutcomeFieldClass.OUTCOME_CONTROLLED
        assert classify("runner", "adjustmentFactor") is OutcomeFieldClass.OUTCOME_CONTROLLED

    def test_post_settlement_only_field(self) -> None:
        assert classify("marketDefinition", "settledTime") is OutcomeFieldClass.POST_SETTLEMENT_ONLY

    def test_unknown_field_fails_closed(self) -> None:
        # A field never seen / never classified is UNKNOWN and NOT pre-lockbox-safe.
        assert classify("rc", "spn") is OutcomeFieldClass.UNKNOWN
        assert classify("marketDefinition", "totallyNewField") is OutcomeFieldClass.UNKNOWN
        assert classify("nonsense_level", "x") is OutcomeFieldClass.UNKNOWN
        assert is_pre_lockbox_safe("rc", "spn") is False

    def test_is_pre_lockbox_safe_only_true_for_safe_class(self) -> None:
        assert is_pre_lockbox_safe("rc", "ltp") is True
        assert is_pre_lockbox_safe("runner", "status") is False
        assert is_pre_lockbox_safe("marketDefinition", "settledTime") is False


class TestAssertGuard:
    def test_safe_field_passes(self) -> None:
        assert_pre_lockbox_readable("rc", "batb")  # no raise

    @pytest.mark.parametrize(
        "level,field",
        [("runner", "status"), ("marketDefinition", "settledTime"), ("marketDefinition", "bspReconciled"), ("rc", "spn")],
    )
    def test_non_safe_field_raises(self, level: str, field: str) -> None:
        with pytest.raises(OutcomeFieldAccessError):
            assert_pre_lockbox_readable(level, field, context="feature-build")


class TestValueSentinels:
    def test_status_closed_is_a_sentinel(self) -> None:
        assert is_outcome_sentinel_value("marketDefinition", "status", "CLOSED") is True
        assert is_outcome_sentinel_value("marketDefinition", "status", "OPEN") is False
        assert is_outcome_sentinel_value("marketDefinition", "status", "SUSPENDED") is False

    def test_inplay_true_is_a_sentinel(self) -> None:
        assert is_outcome_sentinel_value("marketDefinition", "inPlay", True) is True
        assert is_outcome_sentinel_value("marketDefinition", "inPlay", False) is False

    def test_runner_status_result_values_are_sentinels(self) -> None:
        assert is_outcome_sentinel_value("runner", "status", "WINNER") is True
        assert is_outcome_sentinel_value("runner", "status", "ACTIVE") is False


class TestAccessRecorder:
    def test_records_safe_accesses_and_is_replay_provable(self) -> None:
        rec = PreLockboxAccessRecorder()
        rec.record("rc", "batb")
        rec.record("rc", "batl")
        rec.record("rc", "batb")  # repeat
        manifest = rec.manifest()
        # every recorded field is SAFE by construction
        assert all(a.field_class is OutcomeFieldClass.SAFE_BEFORE_LOCKBOX for a in manifest)
        assert {(a.level, a.field) for a in manifest} == {("rc", "batb"), ("rc", "batl")}
        # replay-provable: same accesses -> same digest
        rec2 = PreLockboxAccessRecorder()
        rec2.record("rc", "batl")
        rec2.record("rc", "batb")
        assert rec.content_digest() == rec2.content_digest()
        assert rec.content_digest().startswith("sha256:")

    def test_recording_an_outcome_field_raises_and_is_not_recorded(self) -> None:
        rec = PreLockboxAccessRecorder()
        with pytest.raises(OutcomeFieldAccessError):
            rec.record("runner", "status")
        # the failed access left no trace and no contamination
        assert rec.manifest() == ()

    def test_manifest_never_contains_outcome_field(self) -> None:
        rec = PreLockboxAccessRecorder()
        for lvl, fld in [("rc", "ltp"), ("marketDefinition", "marketTime"), ("top", "pt")]:
            rec.record(lvl, fld)
        assert all(is_pre_lockbox_safe(a.level, a.field) for a in rec.manifest())


class TestSpecSync:
    def test_module_classification_matches_governance_spec(self) -> None:
        # The human-owned YAML is authoritative; the module must not silently diverge.
        spec = yaml.safe_load(_SPEC.read_text())
        assert spec["version"] == CLASSIFICATION_VERSION
        for row in spec["fields"]:
            assert classify(row["level"], row["field"]) is OutcomeFieldClass[row["class"]], (
                row["level"],
                row["field"],
            )

    def test_every_sentinel_in_spec_is_enforced(self) -> None:
        spec = yaml.safe_load(_SPEC.read_text())
        for s in spec["value_level_outcome_sentinels"]:
            for v in s["outcome_values"]:
                assert is_outcome_sentinel_value(s["level"], s["field"], v) is True
