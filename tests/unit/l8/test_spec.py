"""SPEC-093: gate-spec loader — structure only, validated, digest-bound."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from l8_evidence.gates.outcomes import GateOutcome
from l8_evidence.gates.spec import GateKind, GateSpecError, load_gate_spec

pytestmark = pytest.mark.spec("SPEC-093")

_MINIMAL = """\
version: gates-v1
evaluator: gate-evaluator-v1
outcomes: [PASS, CONTINUE, FAIL_HARM, FAIL_FUTILITY]
gates:
  - gate_id: GATE-X
    title: a checklist gate
    kind: checklist
    items:
      - item_id: alpha
        requirement: something attestable
        on_false: FAIL_HARM
  - gate_id: GATE-Y
    alias: GATE-Y2
    title: an evidence gate
    kind: evidence
    decision: anytime_valid_bounds_v1
    items:
      - item_id: beta
        requirement: a precondition
        on_false: CONTINUE
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "gates.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_minimal_spec(tmp_path: Path) -> None:
    spec = load_gate_spec(_write(tmp_path, _MINIMAL))
    assert spec.version == "gates-v1"
    gate_x = spec.gate("GATE-X")
    assert gate_x.kind is GateKind.CHECKLIST
    assert gate_x.items[0].item_id == "alpha"
    assert gate_x.items[0].on_false is GateOutcome.FAIL_HARM
    gate_y = spec.gate("GATE-Y")
    assert gate_y.kind is GateKind.EVIDENCE
    assert gate_y.decision == "anytime_valid_bounds_v1"


def test_alias_resolves_to_the_same_gate(tmp_path: Path) -> None:
    spec = load_gate_spec(_write(tmp_path, _MINIMAL))
    assert spec.gate("GATE-Y2") is spec.gate("GATE-Y")
    assert spec.gate("GATE-Y2").gate_id == "GATE-Y"


def test_unknown_gate_raises(tmp_path: Path) -> None:
    spec = load_gate_spec(_write(tmp_path, _MINIMAL))
    with pytest.raises(GateSpecError):
        spec.gate("GATE-NOPE")


def test_digest_is_sha256_of_the_file_bytes(tmp_path: Path) -> None:
    path = _write(tmp_path, _MINIMAL)
    spec = load_gate_spec(path)
    assert spec.digest == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_numeric_leaf_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(GateSpecError):
        load_gate_spec(_write(tmp_path, _MINIMAL.replace("something attestable", "42")))


def test_float_leaf_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(GateSpecError):
        load_gate_spec(_write(tmp_path, _MINIMAL.replace("something attestable", "0.01")))


def test_on_false_pass_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(GateSpecError):
        load_gate_spec(_write(tmp_path, _MINIMAL.replace("on_false: FAIL_HARM", "on_false: PASS")))


def test_unknown_on_false_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(GateSpecError):
        load_gate_spec(_write(tmp_path, _MINIMAL.replace("on_false: FAIL_HARM", "on_false: MAYBE")))


def test_unknown_kind_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(GateSpecError):
        load_gate_spec(_write(tmp_path, _MINIMAL.replace("kind: checklist", "kind: vibes")))


def test_evidence_gate_without_decision_is_rejected(tmp_path: Path) -> None:
    broken = _MINIMAL.replace("    decision: anytime_valid_bounds_v1\n", "")
    with pytest.raises(GateSpecError):
        load_gate_spec(_write(tmp_path, broken))


def test_unknown_decision_is_rejected(tmp_path: Path) -> None:
    broken = _MINIMAL.replace("anytime_valid_bounds_v1", "llm_judgement_v1")
    with pytest.raises(GateSpecError):
        load_gate_spec(_write(tmp_path, broken))


def test_duplicate_gate_id_is_rejected(tmp_path: Path) -> None:
    broken = _MINIMAL.replace("gate_id: GATE-Y", "gate_id: GATE-X")
    with pytest.raises(GateSpecError):
        load_gate_spec(_write(tmp_path, broken))


def test_duplicate_item_id_within_a_gate_is_rejected(tmp_path: Path) -> None:
    dup = """\
      - item_id: alpha
        requirement: duplicated id
        on_false: CONTINUE
"""
    broken = _MINIMAL.replace("  - gate_id: GATE-Y", dup + "  - gate_id: GATE-Y")
    with pytest.raises(GateSpecError):
        load_gate_spec(_write(tmp_path, broken))


def test_wrong_outcome_set_is_rejected(tmp_path: Path) -> None:
    broken = _MINIMAL.replace(
        "outcomes: [PASS, CONTINUE, FAIL_HARM, FAIL_FUTILITY]", "outcomes: [PASS, FAIL]"
    )
    with pytest.raises(GateSpecError):
        load_gate_spec(_write(tmp_path, broken))


def test_unknown_computed_procedure_is_rejected(tmp_path: Path) -> None:
    broken = _MINIMAL.replace(
        "        on_false: FAIL_HARM",
        "        on_false: FAIL_HARM\n        computed: queue_simulator_v1",
    )
    with pytest.raises(GateSpecError):
        load_gate_spec(_write(tmp_path, broken))
