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
    repo = Path(__file__).resolve().parents[3]
    assert rm.load_classifications(repo / "specs" / "mutation-survivors.yaml") == {}
