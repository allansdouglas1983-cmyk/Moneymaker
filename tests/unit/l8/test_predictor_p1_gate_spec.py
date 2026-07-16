"""SPEC-046: specs/gates/predictor-p1.yaml — Gate P1 structure pinned while still planned.

The gate is NOT active (activation is a human decision permitted only after Gate 1 results
exist), but its decision structure is pre-registered now, structure-only with no numeric
leaves, and loadable by the SPEC-093 deterministic evaluator — an LLM never decides it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from l8_evidence.gates.outcomes import GateOutcome
from l8_evidence.gates.spec import GateKind, load_gate_spec

pytestmark = pytest.mark.spec("SPEC-046")

_SPEC_PATH = Path(__file__).resolve().parents[3] / "specs" / "gates" / "predictor-p1.yaml"


def _numeric_leaves(node: Any, path: str = "$") -> list[str]:
    if isinstance(node, dict):
        return [hit for k, v in node.items() for hit in _numeric_leaves(v, f"{path}.{k}")]
    if isinstance(node, list):
        return [hit for i, v in enumerate(node) for hit in _numeric_leaves(v, f"{path}[{i}]")]
    if isinstance(node, bool):
        return []
    if isinstance(node, (int, float)):
        return [f"{path} = {node!r}"]
    return []


def test_predictor_p1_contains_no_numeric_leaves() -> None:
    document = yaml.safe_load(_SPEC_PATH.read_text(encoding="utf-8"))
    assert _numeric_leaves(document) == []


def test_predictor_p1_loads_with_the_four_outcomes_and_single_gate() -> None:
    spec = load_gate_spec(_SPEC_PATH)
    assert spec.version == "predictor-p1"
    assert tuple(gate.gate_id for gate in spec.gates) == ("GATE-P1",)
    gate = spec.gate("GATE-P1")
    assert gate.kind is GateKind.EVIDENCE
    assert gate.decision == "anytime_valid_bounds_v1"


def test_no_item_declares_on_false_pass() -> None:
    spec = load_gate_spec(_SPEC_PATH)
    for item in spec.gate("GATE-P1").items:
        assert item.on_false is not GateOutcome.PASS


def test_futility_and_harm_flavours_match_spec_046() -> None:
    # FAIL_FUTILITY = insufficient predictive value; FAIL_HARM = commercial/licensing/
    # compliance infeasibility (SPEC-046 outcome semantics).
    spec = load_gate_spec(_SPEC_PATH)
    items = {item.item_id: item for item in spec.gate("GATE-P1").items}
    assert items["heldout_improvement_over_approved_baselines"].on_false is GateOutcome.FAIL_FUTILITY
    assert items["race_level_calibration_stable"].on_false is GateOutcome.FAIL_FUTILITY
    assert items["product_usefulness_defined_and_evidenced"].on_false is GateOutcome.FAIL_FUTILITY
    for harm_item in (
        "displayed_outputs_fully_licensed",
        "mixed_source_lineage_resolved",
        "no_guaranteed_profit_claims",
        "responsible_gambling_review_passed",
        "legal_review_passed",
        "transparent_scorecard_requirements_met",
        "snapshots_immutable_and_reproducible",
        "no_trading_secrets_exposed",
        "isolated_from_live_trading",
        "untouched_period_results_exist",
        "trial_ledger_current_and_multiplicity_accounted",
    ):
        assert items[harm_item].on_false is GateOutcome.FAIL_HARM, harm_item
