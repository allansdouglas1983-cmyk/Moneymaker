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


_SKIP_MARKERS = {"skip", "skipif", "xfail"}


def _mark_name(node: ast.AST) -> str | None:
    """If ``node`` is a ``<...>.mark.NAME`` attribute or call, return NAME."""
    target: ast.AST = node.func if isinstance(node, ast.Call) else node
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Attribute)
        and target.value.attr == "mark"
    ):
        return target.attr
    return None


def _spec_ids_of(node: ast.AST) -> set[str]:
    """SPEC-IDs from a single ``pytest.mark.spec(...)`` call node."""
    ids: set[str] = set()
    if isinstance(node, ast.Call) and _mark_name(node) == "spec":
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                ids.add(arg.value)
    return ids


def _is_skip_decorator(decorator: ast.expr) -> bool:
    return _mark_name(decorator) in _SKIP_MARKERS


def _module_skipped(tree: ast.Module) -> bool:
    """True if a module-level ``pytestmark`` applies skip/xfail to the whole module."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
        ):
            for inner in ast.walk(node.value):
                if _mark_name(inner) in _SKIP_MARKERS:
                    return True
    return False


def _collect_spec_ids(node: ast.AST, ids: set[str]) -> None:
    """Recurse into ``node``, pruning any function/class scope marked skip/xfail."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if any(_is_skip_decorator(d) for d in child.decorator_list):
                continue
            _collect_spec_ids(child, ids)
        else:
            for inner in ast.walk(child):
                ids |= _spec_ids_of(inner)


def find_spec_markers_in_source(source: str) -> set[str]:
    """Return the SPEC-IDs referenced by ``@pytest.mark.spec(...)`` in ``source``.

    Markers on tests that are also marked ``skip``/``skipif``/``xfail`` (function-, class-,
    or module-level) are ignored: a skipped test verifies nothing (ADR 0001 amendment).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    if _module_skipped(tree):
        return set()
    ids: set[str] = set()
    _collect_spec_ids(tree, ids)
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
