"""STAGE3-0005 §7 — annotation architecture proof (PEP-563 runtime-equivalence).

The mutation survivor packet classifies every ``X | Y`` (and other operator) mutant that lands
on a TYPE-ANNOTATION line as EQUIVALENT. That classification is only sound if annotations are
never evaluated at runtime. This test PROVES the two structural preconditions for the promoted
plumbing (``xmarket_contracts``) AND the synthetic coherence engine (``sport_tennis/coherence``):

1. Every production module activates postponed evaluation (``from __future__ import annotations``,
   PEP 563), so annotations are stored as strings and never evaluated when the module runs.
2. No module consumes annotations at runtime — no ``get_type_hints``, no ``__annotations__``
   access, no pydantic / typed-settings model, no ``eval`` of an annotation string. With no
   consumer, a mutated annotation operator cannot change any observable behaviour.

If either precondition were violated, the PEP-563 equivalence class would be UNSOUND and this
test must fail — forcing re-classification rather than silently trusting the label.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_PACKAGES = (_ROOT / "xmarket_contracts", _ROOT / "sport_tennis" / "coherence")

# Runtime annotation-consumption vectors that would make an annotation operator observable.
_FORBIDDEN_NAMES = {"get_type_hints"}
_FORBIDDEN_ATTRS = {"__annotations__"}
_FORBIDDEN_IMPORTS = {"pydantic"}


def _production_modules() -> list[Path]:
    mods: list[Path] = []
    for pkg in _PACKAGES:
        for path in sorted(pkg.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if path.name == "__init__.py" and not path.read_text(encoding="utf-8").strip():
                continue  # an empty package marker carries no annotations
            mods.append(path)
    return mods


def _has_future_annotations(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            if any(a.name == "annotations" for a in node.names):
                return True
    return False


@pytest.mark.parametrize("path", _production_modules(), ids=lambda p: str(p.name))
def test_postponed_annotations_active(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert _has_future_annotations(tree), f"{path} lacks `from __future__ import annotations`"


@pytest.mark.parametrize("path", _production_modules(), ids=lambda p: str(p.name))
def test_no_runtime_annotation_consumption(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            pytest.fail(f"{path.name}: runtime annotation consumption `{node.id}`")
        if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_NAMES | _FORBIDDEN_ATTRS:
            pytest.fail(f"{path.name}: runtime annotation consumption `.{node.attr}`")
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root not in _FORBIDDEN_IMPORTS, f"{path.name}: imports {alias.name}"
        if isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            assert root not in _FORBIDDEN_IMPORTS, f"{path.name}: imports from {node.module}"


def test_proof_covers_expected_modules() -> None:
    # Guard against the glob silently matching nothing (which would make the proof vacuous).
    names = {p.name for p in _production_modules()}
    assert {"parsers.py", "linkage.py", "synchronizer.py", "observation.py"} <= names
    assert {"scoring.py", "match.py", "pmf.py", "solver.py", "holdout.py",
            "formats.py", "format_evidence.py"} <= names
