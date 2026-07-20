"""Unit tests for the mutation harness logic (tools/run_mutation.py).

Infrastructure — no @pytest.mark.spec. Tests the pure parse/evaluate/classify logic against
fixture cosmic-ray output (it does not run cosmic-ray).
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from tools import run_mutation as rm


def _record(module: str, operator: str, occurrence: int, outcome: str) -> list[Any]:
    return [
        {"job_id": "x", "mutations": [{"module_path": module, "operator_name": operator, "occurrence": occurrence, "start_pos": [10, 5]}]},
        {"worker_outcome": "normal", "test_outcome": outcome, "diff": "--- diff ---"},
    ]


def test_parse_dump_counts_and_survivors() -> None:
    dump = "\n".join(
        json.dumps(r)
        for r in (
            _record("l7_settle/ledger.py", "core/AddNot", 0, "survived"),
            _record("l7_settle/pnl.py", "core/NumberReplacer", 0, "killed"),
        )
    )
    summary = rm.parse_dump(dump)
    assert summary.total == 2
    assert summary.killed == 1
    assert len(summary.survivors) == 1
    assert summary.survivors[0].key == "l7_settle/ledger.py::core/AddNot::0"


def _survivor() -> rm.Survivor:
    return rm.Survivor(module_path="m.py", operator_name="op", occurrence=0, line=1, diff="")


def test_report_mode_never_flags() -> None:
    # In report mode neither flag is set; evaluate must not complain.
    assert rm.evaluate([_survivor()], {}, require_kill_non_equivalent=False, survivors_must_be_classified=False) == []


def test_unclassified_survivor_fails_enforcement() -> None:
    problems = rm.evaluate([_survivor()], {}, require_kill_non_equivalent=True, survivors_must_be_classified=True)
    assert problems and "unclassified" in problems[0]


def test_test_deficiency_classification_fails() -> None:
    classifications = {"m.py::op::0": {"classification": "test-deficiency", "approved_by": "h"}}
    problems = rm.evaluate([_survivor()], classifications, require_kill_non_equivalent=True, survivors_must_be_classified=True)
    assert problems and "not equivalent" in problems[0]


def test_equivalent_classification_passes() -> None:
    classifications = {"m.py::op::0": {"classification": "equivalent-mutant", "approved_by": "h"}}
    assert rm.evaluate([_survivor()], classifications, require_kill_non_equivalent=True, survivors_must_be_classified=True) == []


def test_unapproved_classification_fails() -> None:
    classifications = {"m.py::op::0": {"classification": "equivalent-mutant"}}  # no approved_by
    problems = rm.evaluate([_survivor()], classifications, require_kill_non_equivalent=True, survivors_must_be_classified=True)
    assert problems and "not human-approved" in problems[0]


def test_no_survivors_is_clean() -> None:
    assert rm.evaluate([], {}, require_kill_non_equivalent=True, survivors_must_be_classified=True) == []


def test_load_classifications(tmp_path: Path) -> None:
    path = tmp_path / "survivors.yaml"
    path.write_text(
        textwrap.dedent(
            """
            - module_path: m.py
              operator_name: op
              occurrence: 0
              classification: equivalent-mutant
              approved_by: h
            """
        ),
        encoding="utf-8",
    )
    loaded = rm.load_classifications(path)
    assert "m.py::op::0" in loaded


def test_load_classifications_empty(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("[]\n", encoding="utf-8")
    assert rm.load_classifications(path) == {}


def test_real_survivors_file_is_valid() -> None:
    """The real survivors file holds exactly the approved classification set, fully formed.

    TEST CORRECTION (founder-approved in session chat, 2026-07-16, with ADR 0010): the
    original assertion pinned the file to zero entries, written when no survivor had ever
    been classified. The l7_settle mutation pass (SPEC-080/082, SPECIFICATION.md §12.4/§15)
    produced eight behaviourally-unobservable equivalent mutants, approved by the founder;
    the pin now names that exact set, so an entry can neither appear nor vanish without a
    matching human-approved change here.

    TEST CORRECTION (founder-approved in session chat, 2026-07-17, with the F-13
    scoped permanent mutation gate directive): the seven l6_broker/retry.py
    equivalence classifications join the pinned set — the `make mutants-f13` gate
    requires every retry.py survivor killed or classified, and this pin keeps the
    classification set human-controlled exactly as before.

    TEST CORRECTION (founder round-2 §2C delegated class approval, applied 2026-07-19
    in commit 6d155d9, pin update omitted there by mistake): the single
    l7_settle/tennis_rules.py @unique-removal equivalent — approved under the
    delegated "@unique on a frozen, distinct-valued Enum" class and flagged for
    ratification in the recovery return — joins the pinned set. No other change.
    """
    repo = Path(__file__).resolve().parents[3]
    classifications = rm.load_classifications(repo / "specs" / "mutation-survivors.yaml")
    assert set(classifications) == {
        "l6_broker/retry.py::core/ReplaceBinaryOperator_Mul_Div::1",
        "l6_broker/retry.py::core/ReplaceBinaryOperator_Mul_Div::2",
        "l6_broker/retry.py::core/ReplaceComparisonOperator_Gt_GtE::0",
        "l6_broker/retry.py::core/ReplaceComparisonOperator_Gt_GtE::1",
        "l6_broker/retry.py::core/ReplaceTrueWithFalse::3",
        "l6_broker/retry.py::core/NumberReplacer::9",
        "l6_broker/retry.py::core/RemoveDecorator::0",
        "l7_settle/pnl.py::core/ReplaceComparisonOperator_Eq_Is::0",
        "l7_settle/pnl.py::core/ReplaceComparisonOperator_Eq_Is::1",
        "l7_settle/ledger.py::core/ReplaceComparisonOperator_Gt_NotEq::0",
        "l7_settle/settlement.py::core/ReplaceComparisonOperator_Eq_Is::0",
        "l7_settle/settlement.py::core/ReplaceComparisonOperator_Eq_Is::2",
        "l7_settle/settlement.py::core/ReplaceComparisonOperator_Eq_Is::3",
        "l7_settle/settlement.py::core/ReplaceComparisonOperator_LtE_Lt::0",
        "l7_settle/settlement.py::core/NumberReplacer::1",
        "l7_settle/tennis_rules.py::core/RemoveDecorator::0",
    }
    for key, entry in classifications.items():
        assert entry.get("classification") == "equivalent-mutant", key
        assert str(entry.get("rationale", "")).strip(), key
        assert str(entry.get("approved_by", "")).strip(), key


def test_test_command_targets_the_layer_suite_for_nested_targets() -> None:
    # l8_evidence/gates tests live under tests/{unit,properties}/l8 — the layer token comes
    # from the TOP-LEVEL package, not the leaf directory, or cosmic-ray falls back to the
    # whole suite per mutant.
    command = rm._test_command_for("l8_evidence/gates")
    assert "tests/unit/l8" in command
    assert "tests/properties/l8" in command
    assert command.startswith("python -m pytest ")


def test_test_command_is_unchanged_for_single_segment_targets() -> None:
    command = rm._test_command_for("l7_settle")
    assert "tests/unit/l7" in command
    assert "tests/properties/l7" in command
