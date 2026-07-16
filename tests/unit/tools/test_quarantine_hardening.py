"""SPEC-100 hardening: dynamic imports are visible to the quarantine; unparseable files fail
closed.

2026-07-16 retrospective audit, findings A1/A4: ``importlib.import_module("research.scraping.rp")``
inside a betting-capable module was invisible to the AST checker (proven with a working PoC),
and a first-party file that failed to parse was silently treated as import-free.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from tools import check_import_quarantine as ciq


def _mod(root: Path, dotted: str, body: str) -> None:
    parts = dotted.split(".")
    directory = root
    for seg in parts[:-1]:
        directory = directory / seg
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").write_text("", encoding="utf-8")
    (directory / f"{parts[-1]}.py").write_text(textwrap.dedent(body), encoding="utf-8")


def test_importlib_import_module_literal_is_detected(tmp_path: Path) -> None:
    _mod(tmp_path, "research.scraping.rp", "value = 1\n")
    _mod(
        tmp_path,
        "l6_broker.place",
        """
        import importlib
        mod = importlib.import_module("research.scraping.rp")
        """,
    )
    assert ciq.find_violations(tmp_path, "research.scraping", ["l6_broker"])


def test_dunder_import_literal_is_detected(tmp_path: Path) -> None:
    _mod(tmp_path, "research.scraping.rp", "value = 1\n")
    _mod(tmp_path, "l6_broker.place", 'mod = __import__("research.scraping")\n')
    assert ciq.find_violations(tmp_path, "research.scraping", ["l6_broker"])


def test_aliased_import_module_is_detected(tmp_path: Path) -> None:
    _mod(tmp_path, "research.scraping.rp", "value = 1\n")
    _mod(
        tmp_path,
        "l6_broker.place",
        """
        from importlib import import_module as loader
        mod = loader("research.scraping.rp")
        """,
    )
    assert ciq.find_violations(tmp_path, "research.scraping", ["l6_broker"])


def test_non_literal_dynamic_import_fails_closed(tmp_path: Path) -> None:
    # A dynamic import whose target cannot be resolved statically is itself a violation in
    # quarantined-from code: the checker cannot prove it safe, so it refuses to bless it.
    _mod(
        tmp_path,
        "l6_broker.place",
        """
        import importlib

        def load(name):
            return importlib.import_module(name)
        """,
    )
    violations = ciq.find_violations(tmp_path, "research.scraping", ["l6_broker"])
    assert violations
    assert any("dynamic" in v for v in violations)


def test_dynamic_import_outside_reach_is_ignored(tmp_path: Path) -> None:
    # Fail-closed is scoped to modules actually reachable from --from: an unrelated tool
    # using importlib does not fail the betting-path quarantine.
    _mod(tmp_path, "l6_broker.place", "import math\n")
    _mod(
        tmp_path,
        "tools_local.loader",
        """
        import importlib

        def load(name):
            return importlib.import_module(name)
        """,
    )
    assert ciq.find_violations(tmp_path, "research.scraping", ["l6_broker"]) == []


def test_unparseable_reachable_module_fails_closed(tmp_path: Path) -> None:
    _mod(tmp_path, "l6_broker.bad", "def broken(:\n")
    violations = ciq.find_violations(tmp_path, "research.scraping", ["l6_broker"])
    assert violations
    assert any("parse" in v.lower() for v in violations)


def test_clean_tree_remains_ok(tmp_path: Path) -> None:
    _mod(tmp_path, "l6_broker.place", "import math\n")
    _mod(tmp_path, "research.scraping.rp", "value = 1\n")
    assert ciq.find_violations(tmp_path, "research.scraping", ["l6_broker"]) == []
