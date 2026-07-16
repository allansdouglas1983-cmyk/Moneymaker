"""SPEC-093/§13.5: evaluator-side facts freshness — stale facts fail the gate."""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from l8_evidence.gates.facts import Fact, FactsRegistry, assess_facts, load_facts_registry

pytestmark = pytest.mark.spec("SPEC-093")

_AS_OF = date(2026, 7, 16)

_REGISTRY = """\
- fact_id: FRESH-FACT
  value: "5"
  recheck_by: 2027-01-01
  used_by: [GATE-1]

- fact_id: STALE-FACT
  value: "2"
  recheck_by: 2026-01-01
  used_by: [GATE-2]

- fact_id: MISCONFIGURED-FACT
  value: "3"
  used_by: [GATE-2]

- fact_id: BAD-DATE-FACT
  value: "4"
  recheck_by: not-a-date
  used_by: []

- fact_id: UNPOPULATED-FACT
  value: null
  recheck_by: null
  used_by: [GATE-3, GATE-0B]
"""


def _load(tmp_path: Path) -> FactsRegistry:
    path = tmp_path / "facts.yaml"
    path.write_text(_REGISTRY, encoding="utf-8")
    return load_facts_registry(path)


def test_registry_digest_is_sha256_of_the_bytes(tmp_path: Path) -> None:
    path = tmp_path / "facts.yaml"
    path.write_text(_REGISTRY, encoding="utf-8")
    registry = load_facts_registry(path)
    assert registry.digest == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_stale_and_misconfigured_facts_are_flagged_registry_wide(tmp_path: Path) -> None:
    assessment = assess_facts(_load(tmp_path), gate_ids=frozenset({"GATE-1"}), as_of=_AS_OF)
    joined = " ".join(assessment.stale_or_misconfigured)
    assert "STALE-FACT" in joined
    assert "MISCONFIGURED-FACT" in joined
    assert "BAD-DATE-FACT" in joined
    assert "FRESH-FACT" not in joined
    assert "UNPOPULATED-FACT" not in joined


def test_fresh_registry_passes(tmp_path: Path) -> None:
    registry = FactsRegistry(
        facts=(Fact(fact_id="F", populated=True, recheck_by=date(2027, 1, 1), used_by=("GATE-1",)),),
        digest="sha256:" + "0" * 64,
    )
    assessment = assess_facts(registry, gate_ids=frozenset({"GATE-1"}), as_of=_AS_OF)
    assert assessment.stale_or_misconfigured == ()
    assert assessment.required_unpopulated == ()


def test_recheck_on_the_as_of_day_is_not_stale() -> None:
    registry = FactsRegistry(
        facts=(Fact(fact_id="F", populated=True, recheck_by=_AS_OF, used_by=()),),
        digest="sha256:" + "0" * 64,
    )
    assessment = assess_facts(registry, gate_ids=frozenset({"GATE-1"}), as_of=_AS_OF)
    assert assessment.stale_or_misconfigured == ()


def test_recheck_the_day_before_as_of_is_stale() -> None:
    registry = FactsRegistry(
        facts=(Fact(fact_id="F", populated=True, recheck_by=date(2026, 7, 15), used_by=()),),
        digest="sha256:" + "0" * 64,
    )
    assessment = assess_facts(registry, gate_ids=frozenset({"GATE-1"}), as_of=_AS_OF)
    assert "F" in " ".join(assessment.stale_or_misconfigured)


def test_unpopulated_fact_required_by_the_gate_is_flagged(tmp_path: Path) -> None:
    assessment = assess_facts(_load(tmp_path), gate_ids=frozenset({"GATE-3", "GATE-0B"}), as_of=_AS_OF)
    assert "UNPOPULATED-FACT" in " ".join(assessment.required_unpopulated)


def test_unpopulated_fact_for_another_gate_is_not_flagged(tmp_path: Path) -> None:
    assessment = assess_facts(_load(tmp_path), gate_ids=frozenset({"GATE-1"}), as_of=_AS_OF)
    assert assessment.required_unpopulated == ()


def test_alias_membership_counts_as_required(tmp_path: Path) -> None:
    # The registry names GATE-0B; evaluating GATE-3 under its alias set must see it.
    assessment = assess_facts(_load(tmp_path), gate_ids=frozenset({"GATE-0B"}), as_of=_AS_OF)
    assert "UNPOPULATED-FACT" in " ".join(assessment.required_unpopulated)
