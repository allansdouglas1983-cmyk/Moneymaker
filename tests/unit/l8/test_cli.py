"""SPEC-093: the pinned `gate evaluate` CLI contract — exit codes and canonical output."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from l8_evidence.gates.cli import main

pytestmark = pytest.mark.spec("SPEC-093")

_DATA = "sha256:" + "1" * 64
_MODEL = "sha256:" + "2" * 64

_GATES = """\
version: gates-v1
evaluator: gate-evaluator-v1
outcomes: [PASS, CONTINUE, FAIL_HARM, FAIL_FUTILITY]
gates:
  - gate_id: GATE-C
    title: checklist
    kind: checklist
    items:
      - item_id: harm_item
        requirement: must hold
        on_false: FAIL_HARM
      - item_id: futility_item
        requirement: must hold
        on_false: FAIL_FUTILITY
"""

_FACTS_FRESH = """\
- fact_id: SOME-FACT
  value: "5"
  recheck_by: 2099-01-01
  used_by: [GATE-C]
"""

_FACTS_STALE = """\
- fact_id: SOME-FACT
  value: "5"
  recheck_by: 2026-01-01
  used_by: [GATE-C]
"""


def _experiment(harm_item: str = "true", futility_item: str = "true") -> str:
    return (
        "experiment_id: exp-1\n"
        "gate: GATE-C\n"
        "attestations:\n"
        f"  harm_item: {harm_item}\n"
        f"  futility_item: {futility_item}\n"
    )


def _setup(tmp_path: Path, experiment: str, facts: str = _FACTS_FRESH) -> list[str]:
    (tmp_path / "gates.yaml").write_text(_GATES, encoding="utf-8")
    (tmp_path / "facts.yaml").write_text(facts, encoding="utf-8")
    root = tmp_path / "experiments"
    root.mkdir()
    (root / "exp-1.yaml").write_text(experiment, encoding="utf-8")
    return [
        "evaluate",
        "--spec", str(tmp_path / "gates.yaml"),
        "--experiment", "exp-1",
        "--experiment-root", str(root),
        "--data-manifest", _DATA,
        "--model-manifest", _MODEL,
        "--facts-registry", str(tmp_path / "facts.yaml"),
        "--as-of", "2026-07-16",
    ]


def test_pass_exits_zero_and_prints_canonical_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_setup(tmp_path, _experiment())) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "PASS"
    assert payload["gate_id"] == "GATE-C"
    assert payload["experiment_id"] == "exp-1"
    assert payload["data_manifest"] == _DATA
    assert payload["model_manifest"] == _MODEL
    assert payload["as_of"] == "2026-07-16"
    assert payload["evaluator_version"] == "gate-evaluator-v1"


def test_continue_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = "experiment_id: exp-1\ngate: GATE-C\nattestations:\n  harm_item: true\n"
    assert main(_setup(tmp_path, missing)) == 1
    assert json.loads(capsys.readouterr().out)["outcome"] == "CONTINUE"


def test_fail_harm_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(_setup(tmp_path, _experiment(harm_item="false"))) == 2
    assert json.loads(capsys.readouterr().out)["outcome"] == "FAIL_HARM"


def test_fail_futility_exits_three(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(_setup(tmp_path, _experiment(futility_item="false"))) == 3
    assert json.loads(capsys.readouterr().out)["outcome"] == "FAIL_FUTILITY"


def test_stale_fact_fails_harm_via_the_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(_setup(tmp_path, _experiment(), facts=_FACTS_STALE)) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "FAIL_HARM"
    assert "SOME-FACT" in " ".join(payload["reasons"])


def test_malformed_manifest_is_exit_four(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = _setup(tmp_path, _experiment())
    argv[argv.index(_DATA)] = "not-a-manifest"
    assert main(argv) == 4
    captured = capsys.readouterr()
    assert captured.out == ""  # an error is never a verdict


def test_missing_experiment_file_is_exit_four(tmp_path: Path) -> None:
    argv = _setup(tmp_path, _experiment())
    argv[argv.index("exp-1")] = "exp-does-not-exist"
    assert main(argv) == 4


def test_experiment_id_mismatch_is_exit_four(tmp_path: Path) -> None:
    argv = _setup(tmp_path, _experiment().replace("experiment_id: exp-1", "experiment_id: exp-9"))
    assert main(argv) == 4


def test_unparseable_spec_is_exit_four(tmp_path: Path) -> None:
    argv = _setup(tmp_path, _experiment())
    (tmp_path / "gates.yaml").write_text("version: gates-v1\ngates: {not: [valid", encoding="utf-8")
    assert main(argv) == 4


def test_as_of_is_echoed_and_respected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = _setup(tmp_path, _experiment(), facts=_FACTS_STALE)
    argv[argv.index("2026-07-16")] = "2025-06-01"  # before recheck_by: fact not yet stale
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out)["as_of"] == "2025-06-01"


def test_byte_identical_output_for_identical_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = _setup(tmp_path, _experiment())
    assert main(argv) == 0
    first = capsys.readouterr().out
    assert main(argv) == 0
    second = capsys.readouterr().out
    assert first == second
