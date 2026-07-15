"""SPEC-100: research/scraping/ has no import path into the betting-capable modules."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.check_import_quarantine import find_violations

pytestmark = pytest.mark.spec("SPEC-100")

_REPO = Path(__file__).resolve().parents[3]
_ROOTS = ["l5_decision", "l5b_risk", "l6_broker"]


def test_real_repo_has_no_scraping_import_path() -> None:
    assert find_violations(_REPO, "research.scraping", _ROOTS) == []


def test_quarantine_would_catch_a_violation(tmp_path: Path) -> None:
    # Non-vacuity: plant a betting-module import of research.scraping and confirm it is caught.
    scraping = tmp_path / "research" / "scraping"
    scraping.mkdir(parents=True)
    (tmp_path / "research" / "__init__.py").write_text("", encoding="utf-8")
    (scraping / "__init__.py").write_text("", encoding="utf-8")
    (scraping / "rp.py").write_text("value = 1\n", encoding="utf-8")
    broker = tmp_path / "l6_broker"
    broker.mkdir()
    (broker / "__init__.py").write_text("", encoding="utf-8")
    (broker / "place.py").write_text("import research.scraping.rp\n", encoding="utf-8")
    assert find_violations(tmp_path, "research.scraping", _ROOTS)
