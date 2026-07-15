"""Unit tests for tools/emit_traceability.py."""
from __future__ import annotations

from typing import Any

import pytest

from tools import _spec_lib
from tools import emit_traceability as et


def test_render_contains_ids_and_criticality() -> None:
    entries: list[dict[str, Any]] = [
        {
            "id": "SPEC-050",
            "component": "l5_decision",
            "criticality": "money",
            "enforcement_state": "active",
            "introduced_in_phase": 1,
        }
    ]
    coverage: dict[str, _spec_lib.CoverageInfo] = {
        "SPEC-050": _spec_lib.CoverageInfo(files={"tests/properties/test_ev.py"}, has_property=True)
    }
    md = et.render_markdown(entries, coverage)
    assert "SPEC-050" in md
    assert "money" in md
    assert "|" in md


def test_main_runs_on_real_manifest(capsys: pytest.CaptureFixture[str]) -> None:
    rc = et.main(["--manifest", "docs/spec-manifest.yaml", "--tests-dir", "tests"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "SPEC-001" in out
    assert "SPEC-100" in out
