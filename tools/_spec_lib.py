"""Shared helpers for the SPEC verification tooling.

Support/evidence criticality — no money logic. See docs/decisions/0001-verification-tooling.md.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def parse_manifest_text(text: str) -> list[dict[str, Any]]:
    """Parse manifest YAML text into a list of entry dicts."""
    raw: Any = yaml.safe_load(text)
    if not isinstance(raw, list):
        raise ValueError("expected a top-level YAML list")
    entries: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("every manifest entry must be a mapping")
        entries.append(item)
    return entries


def load_manifest(path: Path) -> list[dict[str, Any]]:
    """Load the spec manifest as a list of entry dicts."""
    return parse_manifest_text(path.read_text(encoding="utf-8"))


def index_manifest(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index entries by id, raising on a missing or duplicate id."""
    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        spec_id = entry.get("id")
        if not isinstance(spec_id, str) or not spec_id:
            raise ValueError("manifest entry without a string 'id'")
        if spec_id in index:
            raise ValueError(f"duplicate manifest id: {spec_id}")
        index[spec_id] = entry
    return index


def find_spec_markers_in_source(source: str) -> set[str]:
    """Return the SPEC-IDs referenced by ``@pytest.mark.spec(...)`` in ``source``."""
    ids: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ids
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "spec"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "mark"
        ):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    ids.add(arg.value)
    return ids


@dataclass
class CoverageInfo:
    """Which test files reference a SPEC-ID, and whether any is a property test."""

    files: set[str] = field(default_factory=set)
    has_property: bool = False


def is_property_file(path: Path, tests_dir: Path) -> bool:
    """True if ``path`` lives under a 'properties' directory within ``tests_dir``."""
    try:
        rel = path.relative_to(tests_dir)
    except ValueError:
        return "properties" in path.parts
    return "properties" in rel.parts


def collect_coverage(tests_dir: Path) -> dict[str, CoverageInfo]:
    """Map each SPEC-ID referenced under ``tests_dir`` to its coverage info."""
    coverage: dict[str, CoverageInfo] = {}
    if not tests_dir.exists():
        return coverage
    for py in sorted(tests_dir.rglob("*.py")):
        try:
            source = py.read_text(encoding="utf-8")
        except OSError:
            continue
        ids = find_spec_markers_in_source(source)
        if not ids:
            continue
        prop = is_property_file(py, tests_dir)
        name = str(py)
        for spec_id in ids:
            info = coverage.setdefault(spec_id, CoverageInfo())
            info.files.add(name)
            if prop:
                info.has_property = True
    return coverage
