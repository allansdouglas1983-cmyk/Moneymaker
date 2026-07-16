"""SPEC-093: the verdict is four-valued and never a boolean — enforced by construction."""
from __future__ import annotations

import dataclasses
import json
from datetime import date

import pytest

from l8_evidence.gates.outcomes import EVALUATOR_VERSION, GateOutcome, GateResult

pytestmark = pytest.mark.spec("SPEC-093")

_SHA = "sha256:" + "a" * 64


def _result(outcome: GateOutcome) -> GateResult:
    return GateResult(
        gate_id="GATE-1",
        experiment_id="exp-0001",
        outcome=outcome,
        reasons=("reason-one", "reason-two"),
        data_manifest=_SHA,
        model_manifest=_SHA,
        spec_version="gates-v1",
        spec_digest=_SHA,
        facts_digest=_SHA,
        evaluator_version=EVALUATOR_VERSION,
        as_of=date(2026, 7, 16),
    )


def test_outcome_is_exactly_four_valued() -> None:
    assert {o.name for o in GateOutcome} == {"PASS", "CONTINUE", "FAIL_HARM", "FAIL_FUTILITY"}


@pytest.mark.parametrize("outcome", list(GateOutcome))
def test_outcome_is_never_truth_testable(outcome: GateOutcome) -> None:
    with pytest.raises(TypeError):
        bool(outcome)


@pytest.mark.parametrize("outcome", list(GateOutcome))
def test_result_is_never_truth_testable(outcome: GateOutcome) -> None:
    with pytest.raises(TypeError):
        bool(_result(outcome))


def test_result_cannot_drive_an_if_statement() -> None:
    result = _result(GateOutcome.FAIL_HARM)
    with pytest.raises(TypeError):
        if result:  # the point is that truth-testing must raise, so the branch is unreachable
            raise AssertionError("unreachable")


def test_result_is_frozen() -> None:
    result = _result(GateOutcome.CONTINUE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.outcome = GateOutcome.PASS  # type: ignore[misc]


def test_evaluator_version_is_pinned() -> None:
    assert EVALUATOR_VERSION == "gate-evaluator-v1"


def test_canonical_json_round_trips_all_fields() -> None:
    result = _result(GateOutcome.FAIL_FUTILITY)
    payload = json.loads(result.canonical_json())
    assert payload == {
        "as_of": "2026-07-16",
        "data_manifest": _SHA,
        "evaluator_version": "gate-evaluator-v1",
        "experiment_id": "exp-0001",
        "facts_digest": _SHA,
        "gate_id": "GATE-1",
        "model_manifest": _SHA,
        "outcome": "FAIL_FUTILITY",
        "reasons": ["reason-one", "reason-two"],
        "spec_digest": _SHA,
        "spec_version": "gates-v1",
    }


def test_canonical_json_is_sorted_and_compact() -> None:
    text = _result(GateOutcome.PASS).canonical_json()
    keys = list(json.loads(text).keys())
    assert keys == sorted(keys)
    assert ": " not in text and ", " not in text
