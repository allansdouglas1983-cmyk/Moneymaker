"""SPEC-093: the frozen specs/gates/v1.yaml — structure only, no numeric leaves (§9.3)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from l8_evidence.gates.outcomes import GateOutcome
from l8_evidence.gates.spec import GateKind, load_gate_spec

pytestmark = pytest.mark.spec("SPEC-093")

_SPEC_PATH = Path(__file__).resolve().parents[3] / "specs" / "gates" / "v1.yaml"

_GATE_IDS = (
    "GATE--1A",
    "GATE-0A",
    "GATE-1",
    "GATE-2",
    "GATE--1B",
    "GATE-3",
    "GATE-4",
    "GATE-5",
    "GATE-6",
)


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


def test_frozen_spec_contains_no_numeric_leaves() -> None:
    document = yaml.safe_load(_SPEC_PATH.read_text(encoding="utf-8"))
    assert _numeric_leaves(document) == []


def test_frozen_spec_loads_and_pins_the_nine_gates() -> None:
    spec = load_gate_spec(_SPEC_PATH)
    assert spec.version == "gates-v1"
    assert tuple(gate.gate_id for gate in spec.gates) == _GATE_IDS


def test_gate_0b_is_an_alias_of_gate_3() -> None:
    spec = load_gate_spec(_SPEC_PATH)
    assert spec.gate("GATE-0B") is spec.gate("GATE-3")


def test_evidence_gates_use_the_anytime_valid_decision() -> None:
    spec = load_gate_spec(_SPEC_PATH)
    evidence_ids = {g.gate_id for g in spec.gates if g.kind is GateKind.EVIDENCE}
    assert evidence_ids == {"GATE-1", "GATE-2", "GATE-4", "GATE-5"}
    for gate_id in sorted(evidence_ids):
        assert spec.gate(gate_id).decision == "anytime_valid_bounds_v1"


def test_no_item_declares_on_false_pass() -> None:
    spec = load_gate_spec(_SPEC_PATH)
    for gate in spec.gates:
        for item in gate.items:
            assert item.on_false is not GateOutcome.PASS


def test_payback_is_a_computed_item_on_gate_minus_1b() -> None:
    spec = load_gate_spec(_SPEC_PATH)
    items = {item.item_id: item for item in spec.gate("GATE--1B").items}
    payback = items["payback_within_precommitted_horizon"]
    assert payback.computed == "payback_v1"
    assert payback.on_false is GateOutcome.FAIL_FUTILITY


def test_lockbox_contamination_is_harm_on_gate_1() -> None:
    spec = load_gate_spec(_SPEC_PATH)
    items = {item.item_id: item for item in spec.gate("GATE-1").items}
    assert items["lockbox_uncontaminated"].on_false is GateOutcome.FAIL_HARM
