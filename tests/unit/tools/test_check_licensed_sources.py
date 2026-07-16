"""SPEC-101: the Gate -1 licensing check is a standalone, CI-invocable tool.

2026-07-16 retrospective audit, finding A5: enforcement previously rode on one unit test
inside the pytest run; there was no purpose-built gate command like SPEC-100's. This tool
gives the licensing rule the same shape: a dedicated checker, run explicitly by make verify
and CI.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tools import check_licensed_sources as cls_tool

pytestmark = pytest.mark.spec("SPEC-101")


def _registry(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "licensed-sources.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_candidate_only_registry_passes(tmp_path: Path) -> None:
    path = _registry(
        tmp_path,
        """
        - source_id: betfair-historical
          operational: false
          status: candidate
        """,
    )
    assert cls_tool.main(["--registry", str(path)]) == 0


def test_operational_without_rights_fails(tmp_path: Path) -> None:
    path = _registry(
        tmp_path,
        """
        - source_id: sneaky-feed
          operational: true
          status: candidate
        """,
    )
    assert cls_tool.main(["--registry", str(path)]) == 1


def test_operational_with_full_rights_passes(tmp_path: Path) -> None:
    path = _registry(
        tmp_path,
        """
        - source_id: licensed-feed
          operational: true
          status: permitted
          permitted_uses:
            model_training: true
            automated_betting: true
            retention: true
            derived_models: true
        """,
    )
    assert cls_tool.main(["--registry", str(path)]) == 0


def test_missing_registry_fails_closed(tmp_path: Path) -> None:
    assert cls_tool.main(["--registry", str(tmp_path / "absent.yaml")]) == 1


def test_real_repo_registry_passes() -> None:
    assert cls_tool.main(["--registry", "docs/licensed-sources.yaml"]) == 0
