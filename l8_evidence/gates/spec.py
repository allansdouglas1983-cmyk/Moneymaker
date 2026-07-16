"""Gate-spec loader (SPEC-093, ADR 0011 decisions 1-3).

``specs/gates/v1.yaml`` holds decision STRUCTURE only. The loader refuses any numeric
leaf anywhere in the document (§9.3 — no borrowed thresholds live in the structure), and
binds the parsed spec to a sha256 digest of the exact file bytes.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from l8_evidence.gates.outcomes import GateEvaluationError, GateOutcome

_REQUIRED_OUTCOMES = ("PASS", "CONTINUE", "FAIL_HARM", "FAIL_FUTILITY")
_KNOWN_DECISIONS = frozenset({"anytime_valid_bounds_v1"})
_KNOWN_COMPUTED = frozenset({"payback_v1"})


class GateSpecError(GateEvaluationError):
    """The gate spec is malformed; evaluation refuses to start."""


class GateKind(Enum):
    CHECKLIST = "checklist"
    EVIDENCE = "evidence"


@dataclass(frozen=True)
class GateItem:
    item_id: str
    on_false: GateOutcome
    computed: str | None = None


@dataclass(frozen=True)
class GateDefinition:
    gate_id: str
    kind: GateKind
    items: tuple[GateItem, ...]
    decision: str | None = None
    alias: str | None = None


@dataclass(frozen=True)
class GateSpec:
    version: str
    digest: str
    gates: tuple[GateDefinition, ...]

    def gate(self, gate_id: str) -> GateDefinition:
        """Resolve a gate by id or alias; unknown ids are an error, never a verdict."""
        for gate in self.gates:
            if gate.gate_id == gate_id or gate.alias == gate_id:
                return gate
        raise GateSpecError(f"unknown gate id: {gate_id!r}")


def _numeric_leaves(node: Any, path: str) -> list[str]:
    if isinstance(node, dict):
        return [hit for key, value in node.items() for hit in _numeric_leaves(value, f"{path}.{key}")]
    if isinstance(node, list):
        return [hit for i, value in enumerate(node) for hit in _numeric_leaves(value, f"{path}[{i}]")]
    if isinstance(node, bool):
        return []
    if isinstance(node, (int, float)):
        return [f"{path} = {node!r}"]
    return []


def _parse_item(raw: Any, gate_id: str) -> GateItem:
    if not isinstance(raw, dict):
        raise GateSpecError(f"{gate_id}: item is not a mapping: {raw!r}")
    item_id = raw.get("item_id")
    if not isinstance(item_id, str) or not item_id:
        raise GateSpecError(f"{gate_id}: item without a usable item_id: {raw!r}")
    on_false_raw = raw.get("on_false")
    try:
        on_false = GateOutcome(on_false_raw)
    except ValueError as exc:
        raise GateSpecError(f"{gate_id}.{item_id}: unknown on_false {on_false_raw!r}") from exc
    if on_false is GateOutcome.PASS:
        raise GateSpecError(f"{gate_id}.{item_id}: a false item can never produce PASS")
    computed = raw.get("computed")
    if computed is not None and computed not in _KNOWN_COMPUTED:
        raise GateSpecError(f"{gate_id}.{item_id}: unknown computed procedure {computed!r}")
    return GateItem(item_id=item_id, on_false=on_false, computed=computed)


def _parse_gate(raw: Any) -> GateDefinition:
    if not isinstance(raw, dict):
        raise GateSpecError(f"gate entry is not a mapping: {raw!r}")
    gate_id = raw.get("gate_id")
    if not isinstance(gate_id, str) or not gate_id:
        raise GateSpecError(f"gate without a usable gate_id: {raw!r}")
    kind_raw = raw.get("kind")
    try:
        kind = GateKind(kind_raw)
    except ValueError as exc:
        raise GateSpecError(f"{gate_id}: unknown kind {kind_raw!r}") from exc
    decision = raw.get("decision")
    if kind is GateKind.EVIDENCE and decision not in _KNOWN_DECISIONS:
        raise GateSpecError(f"{gate_id}: evidence gate requires a known decision, got {decision!r}")
    if kind is GateKind.CHECKLIST and decision is not None:
        raise GateSpecError(f"{gate_id}: checklist gate must not declare a decision")
    items_raw = raw.get("items")
    if not isinstance(items_raw, list) or not items_raw:
        raise GateSpecError(f"{gate_id}: gate requires a non-empty items list")
    items = tuple(_parse_item(item, gate_id) for item in items_raw)
    item_ids = [item.item_id for item in items]
    if len(set(item_ids)) != len(item_ids):
        raise GateSpecError(f"{gate_id}: duplicate item_id")
    alias = raw.get("alias")
    if alias is not None and not isinstance(alias, str):
        raise GateSpecError(f"{gate_id}: alias must be a string, got {alias!r}")
    return GateDefinition(gate_id=gate_id, kind=kind, items=items, decision=decision, alias=alias)


def load_gate_spec(path: Path) -> GateSpec:
    """Parse and validate a gate spec, bound to the digest of its exact bytes."""
    raw_bytes = path.read_bytes()
    digest = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    try:
        document = yaml.safe_load(raw_bytes.decode("utf-8"))
    except yaml.YAMLError as exc:
        raise GateSpecError(f"{path}: unparseable YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise GateSpecError(f"{path}: gate spec is not a mapping")
    numeric = _numeric_leaves(document, "$")
    if numeric:
        raise GateSpecError(f"{path}: numeric leaves are forbidden in the gate spec: {numeric}")
    version = document.get("version")
    if not isinstance(version, str) or not version:
        raise GateSpecError(f"{path}: missing version")
    outcomes = document.get("outcomes")
    if outcomes != list(_REQUIRED_OUTCOMES):
        raise GateSpecError(f"{path}: outcomes must be exactly {list(_REQUIRED_OUTCOMES)}")
    gates_raw = document.get("gates")
    if not isinstance(gates_raw, list) or not gates_raw:
        raise GateSpecError(f"{path}: gates must be a non-empty list")
    gates = tuple(_parse_gate(gate) for gate in gates_raw)
    names = [name for gate in gates for name in (gate.gate_id, gate.alias) if name is not None]
    if len(set(names)) != len(names):
        raise GateSpecError(f"{path}: duplicate gate_id or alias")
    return GateSpec(version=version, digest=digest, gates=gates)
