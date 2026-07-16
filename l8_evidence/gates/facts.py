"""Evaluator-side facts freshness (SPEC-093, §13.5).

Deliberately self-contained in the money module and mutation-tested here;
``tools/check_facts_freshness.py`` remains the registry lint (ADR 0011 decision 12).

Registry-wide: ANY populated fact past its ``recheck_by`` — or populated without one —
fails the gate with FAIL_HARM. A fact *required by the gate under evaluation* (its
``used_by`` names the gate id or alias) that is unpopulated yields CONTINUE: the gate
cannot honestly be evaluated, but nothing has been demonstrated wrong.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from l8_evidence.gates.outcomes import GateEvaluationError


class FactsRegistryError(GateEvaluationError):
    """The facts registry is unreadable; evaluation refuses to start."""


@dataclass(frozen=True)
class Fact:
    fact_id: str
    populated: bool
    recheck_by: date | None
    misconfigured: bool = False
    used_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class FactsRegistry:
    facts: tuple[Fact, ...]
    digest: str


@dataclass(frozen=True)
class FactsAssessment:
    stale_or_misconfigured: tuple[str, ...]
    required_unpopulated: tuple[str, ...]


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _parse_fact(raw: Any, path: Path) -> Fact:
    if not isinstance(raw, dict):
        raise FactsRegistryError(f"{path}: fact entry is not a mapping: {raw!r}")
    fact_id = raw.get("fact_id")
    if not isinstance(fact_id, str) or not fact_id:
        raise FactsRegistryError(f"{path}: fact without a usable fact_id: {raw!r}")
    populated = raw.get("value") is not None
    recheck_raw = raw.get("recheck_by")
    recheck_by = _as_date(recheck_raw)
    # A populated fact must carry a valid recheck_by; unparseable counts as misconfigured.
    misconfigured = populated and recheck_by is None
    used_by_raw = raw.get("used_by") or []
    if not isinstance(used_by_raw, list):
        raise FactsRegistryError(f"{path}: {fact_id}: used_by must be a list")
    used_by = tuple(str(entry) for entry in used_by_raw)
    return Fact(
        fact_id=fact_id,
        populated=populated,
        recheck_by=recheck_by,
        misconfigured=misconfigured,
        used_by=used_by,
    )


def load_facts_registry(path: Path) -> FactsRegistry:
    """Parse the facts registry, bound to the digest of its exact bytes."""
    raw_bytes = path.read_bytes()
    digest = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    try:
        document = yaml.safe_load(raw_bytes.decode("utf-8"))
    except yaml.YAMLError as exc:
        raise FactsRegistryError(f"{path}: unparseable YAML: {exc}") from exc
    if not isinstance(document, list):
        raise FactsRegistryError(f"{path}: facts registry is not a YAML list")
    facts = tuple(_parse_fact(entry, path) for entry in document)
    return FactsRegistry(facts=facts, digest=digest)


def assess_facts(registry: FactsRegistry, gate_ids: frozenset[str], as_of: date) -> FactsAssessment:
    """Apply the §13.5 rules for one evaluation at an explicit as-of date."""
    stale: list[str] = []
    required_unpopulated: list[str] = []
    for fact in registry.facts:
        if fact.populated:
            if fact.misconfigured:
                stale.append(f"{fact.fact_id}: populated without a valid recheck_by")
            elif fact.recheck_by is not None and fact.recheck_by < as_of:
                stale.append(
                    f"{fact.fact_id}: stale (recheck_by {fact.recheck_by.isoformat()}"
                    f" < as-of {as_of.isoformat()})"
                )
        elif gate_ids & set(fact.used_by):
            required_unpopulated.append(
                f"{fact.fact_id}: required by this gate but not yet populated"
            )
    return FactsAssessment(
        stale_or_misconfigured=tuple(stale),
        required_unpopulated=tuple(required_unpopulated),
    )
