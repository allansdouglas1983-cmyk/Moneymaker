"""Unit tests for tools/check_import_quarantine.py (SPEC-100 enforcement mechanism)."""
from __future__ import annotations

import textwrap
from pathlib import Path

from tools import check_import_quarantine as ciq


def _mod(root: Path, dotted: str, body: str) -> None:
    """Create a first-party module at ``dotted`` under ``root`` (with packages)."""
    parts = dotted.split(".")
    directory = root
    for seg in parts[:-1]:
        directory = directory / seg
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").write_text("", encoding="utf-8")
    (directory / f"{parts[-1]}.py").write_text(textwrap.dedent(body), encoding="utf-8")


def test_clean_tree_ok(tmp_path: Path) -> None:
    _mod(tmp_path, "l5_decision.ev", "import math\n")
    _mod(tmp_path, "research.scraping.rp", "value = 1\n")
    assert ciq.find_violations(tmp_path, "research.scraping", ["l5_decision"]) == []


def test_direct_forbidden_import_detected(tmp_path: Path) -> None:
    _mod(tmp_path, "research.scraping.rp", "value = 1\n")
    _mod(tmp_path, "l6_broker.place", "from research.scraping import rp\n")
    violations = ciq.find_violations(tmp_path, "research.scraping", ["l6_broker"])
    assert violations
    assert "l6_broker" in violations[0]


def test_from_research_import_scraping_detected(tmp_path: Path) -> None:
    _mod(tmp_path, "research.scraping.rp", "value = 1\n")
    _mod(tmp_path, "l6_broker.place", "from research import scraping\n")
    assert ciq.find_violations(tmp_path, "research.scraping", ["l6_broker"])


def test_transitive_forbidden_detected(tmp_path: Path) -> None:
    _mod(tmp_path, "research.scraping.rp", "value = 1\n")
    _mod(tmp_path, "l5_decision.helper", "import research.scraping.rp\n")
    _mod(tmp_path, "l5_decision.ev", "from l5_decision import helper\n")
    violations = ciq.find_violations(tmp_path, "research.scraping", ["l5_decision"])
    assert violations


def test_main_returns_codes(tmp_path: Path) -> None:
    _mod(tmp_path, "research.scraping.rp", "value = 1\n")
    _mod(tmp_path, "l6_broker.place", "import research.scraping.rp\n")
    rc_bad = ciq.main(
        ["--root", str(tmp_path), "--forbid", "research.scraping", "--from", "l6_broker"]
    )
    assert rc_bad == 1
    _mod(tmp_path, "l6_broker.place", "import math\n")
    rc_ok = ciq.main(
        ["--root", str(tmp_path), "--forbid", "research.scraping", "--from", "l6_broker"]
    )
    assert rc_ok == 0
