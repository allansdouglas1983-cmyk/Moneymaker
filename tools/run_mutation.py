"""Mutation testing harness (cosmic-ray) for the money modules (SPECIFICATION.md §12.4, §15).

CI `mutants-critical` runs:
  run_mutation.py --target l8_evidence/gates l7_settle --require-kill-non-equivalent --survivors-must-be-classified
  run_mutation.py --target l5b_risk --report

A surviving mutant is allowed only if classified in the survivors file (default
`specs/mutation-survivors.yaml`) as `equivalent-mutant` / `unreachable-defensive` /
`tooling-limitation`, with a rationale and human approval. Under `--require-kill-non-equivalent`
an unclassified or `test-deficiency` survivor fails — add a test that kills it. `--report` lists
survivors without enforcing. Targets with no Python modules are skipped (0 mutants).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_ACCEPTABLE = {"equivalent-mutant", "unreachable-defensive", "tooling-limitation"}


@dataclass(frozen=True)
class Survivor:
    module_path: str
    operator_name: str
    occurrence: int
    line: int
    diff: str

    @property
    def key(self) -> str:
        return f"{self.module_path}::{self.operator_name}::{self.occurrence}"


@dataclass(frozen=True)
class MutationSummary:
    total: int
    killed: int
    survivors: list[Survivor]


def parse_dump(dump_text: str) -> MutationSummary:
    """Parse `cosmic-ray dump` output (one ``[work_item, work_result]`` JSON line per job)."""
    total = 0
    killed = 0
    survivors: list[Survivor] = []
    for raw in dump_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        record: Any = json.loads(line)
        if not isinstance(record, list) or len(record) != 2:
            continue
        work_item, work_result = record
        if not isinstance(work_result, dict):
            continue
        outcome = work_result.get("test_outcome")
        if outcome is None:
            continue
        total += 1
        if outcome == "killed":
            killed += 1
        if outcome != "survived":
            continue
        mutations = work_item.get("mutations") if isinstance(work_item, dict) else None
        if not mutations:
            continue
        mutation = mutations[0]
        start = mutation.get("start_pos") or [0, 0]
        survivors.append(
            Survivor(
                module_path=str(mutation.get("module_path", "")),
                operator_name=str(mutation.get("operator_name", "")),
                occurrence=int(mutation.get("occurrence", 0)),
                line=int(start[0]) if start else 0,
                diff=str(work_result.get("diff", "")).strip(),
            )
        )
    return MutationSummary(total=total, killed=killed, survivors=survivors)


def load_classifications(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise ValueError(f"{path}: survivors file must be a YAML list")
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"{path}: each survivor entry must be a mapping")
        key = f"{item.get('module_path')}::{item.get('operator_name')}::{item.get('occurrence')}"
        result[key] = item
    return result


def evaluate(
    survivors: Sequence[Survivor],
    classifications: dict[str, dict[str, Any]],
    *,
    require_kill_non_equivalent: bool,
    survivors_must_be_classified: bool,
) -> list[str]:
    problems: list[str] = []
    for survivor in survivors:
        entry = classifications.get(survivor.key)
        if entry is None:
            if survivors_must_be_classified or require_kill_non_equivalent:
                problems.append(f"unclassified surviving mutant: {survivor.key} (line {survivor.line})")
            continue
        classification = str(entry.get("classification", ""))
        if require_kill_non_equivalent and classification not in _ACCEPTABLE:
            problems.append(
                f"surviving mutant {survivor.key} classified {classification!r} is not equivalent — "
                "kill it with a test"
            )
        if not entry.get("approved_by"):
            problems.append(f"surviving mutant {survivor.key} classification is not human-approved")
    return problems


def _has_python(target: Path) -> bool:
    if target.is_dir():
        return any(target.rglob("*.py"))
    return target.suffix == ".py"


def _test_command_for(target: str) -> str:
    # Layer token from the TOP-LEVEL package (l8_evidence/gates -> l8), so nested money
    # modules still get their focused suite instead of the whole-repo fallback.
    token = Path(target).parts[0].split("_")[0]
    dirs = [d for d in (f"tests/unit/{token}", f"tests/properties/{token}") if (_ROOT / d).exists()]
    if dirs:
        return "python -m pytest " + " ".join(dirs) + " -x -q"
    return "python -m pytest -x -q"


def _run_cosmic_ray(target: str, test_command: str, timeout: float, workdir: Path) -> MutationSummary:
    config = workdir / "config.toml"
    session = workdir / "session.sqlite"
    config.write_text(
        "[cosmic-ray]\n"
        f'module-path = "{target}"\n'
        f"timeout = {timeout}\n"
        "excluded-modules = []\n"
        f'test-command = "{test_command}"\n'
        "[cosmic-ray.distributor]\n"
        'name = "local"\n',
        encoding="utf-8",
    )
    subprocess.run(["cosmic-ray", "init", str(config), str(session)], cwd=str(_ROOT), check=True)
    subprocess.run(["cosmic-ray", "exec", str(config), str(session)], cwd=str(_ROOT), check=True)
    dump = subprocess.run(
        ["cosmic-ray", "dump", str(session)], cwd=str(_ROOT), check=True, capture_output=True, text=True
    )
    return parse_dump(dump.stdout)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Mutation testing harness (cosmic-ray).")
    parser.add_argument("--target", nargs="+", required=True)
    parser.add_argument("--require-kill-non-equivalent", action="store_true")
    parser.add_argument("--survivors-must-be-classified", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--classifications", default="specs/mutation-survivors.yaml", type=Path)
    parser.add_argument("--test-command", default=None)
    parser.add_argument("--timeout", default=60.0, type=float)
    args = parser.parse_args(argv)

    all_survivors: list[Survivor] = []
    for target in args.target:
        if not _has_python(_ROOT / target):
            print(f"[mutation] {target}: no Python modules to mutate — skipped")
            continue
        test_command = args.test_command or _test_command_for(target)
        with tempfile.TemporaryDirectory() as tmp:
            summary = _run_cosmic_ray(target, test_command, args.timeout, Path(tmp))
        print(
            f"[mutation] {target}: {summary.total} mutant(s), {summary.killed} killed, "
            f"{len(summary.survivors)} survived"
        )
        all_survivors.extend(summary.survivors)

    if args.report:
        for survivor in all_survivors:
            print(f"  SURVIVED {survivor.key} (line {survivor.line})")
        print(f"[mutation] report: {len(all_survivors)} surviving mutant(s)")
        return 0

    path: Path = args.classifications
    classifications = load_classifications(path if path.is_absolute() else _ROOT / path)
    problems = evaluate(
        all_survivors,
        classifications,
        require_kill_non_equivalent=args.require_kill_non_equivalent,
        survivors_must_be_classified=args.survivors_must_be_classified,
    )
    if problems:
        print(f"[mutation] FAIL ({len(problems)} problem(s)):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"[mutation] OK: {len(all_survivors)} survivor(s), all classified and approved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
