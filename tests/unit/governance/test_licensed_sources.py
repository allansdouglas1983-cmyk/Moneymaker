"""SPEC-101: operational data sources must be licensed for use before live."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from governance.licensed_sources import (
    LicensingError,
    assert_operational_sources_licensed,
    load_registry,
)

pytestmark = pytest.mark.spec("SPEC-101")

_REPO = Path(__file__).resolve().parents[3]


def _permitted() -> dict[str, bool]:
    return {
        "offline_research": True,
        "model_training": True,
        "automated_betting": True,
        "cloud_processing": True,
        "retention": True,
        "derived_models": True,
    }


def test_research_only_source_passes() -> None:
    sources: list[dict[str, Any]] = [
        {"source_id": "rp", "status": "candidate", "operational": False, "permitted_uses": {}}
    ]
    assert assert_operational_sources_licensed(sources) == []


def test_operational_candidate_source_fails() -> None:
    sources: list[dict[str, Any]] = [
        {"source_id": "feed", "status": "candidate", "operational": True, "permitted_uses": _permitted()}
    ]
    with pytest.raises(LicensingError):
        assert_operational_sources_licensed(sources)


def test_operational_permitted_but_missing_right_fails() -> None:
    uses = _permitted()
    uses["automated_betting"] = False
    sources: list[dict[str, Any]] = [
        {"source_id": "feed", "status": "permitted", "operational": True, "permitted_uses": uses}
    ]
    with pytest.raises(LicensingError):
        assert_operational_sources_licensed(sources)


def test_fully_permitted_operational_source_passes() -> None:
    sources: list[dict[str, Any]] = [
        {"source_id": "feed", "status": "permitted", "operational": True, "permitted_uses": _permitted()}
    ]
    assert assert_operational_sources_licensed(sources) == ["feed"]


def test_repo_registry_loads_and_is_clean() -> None:
    sources = load_registry(_REPO / "docs" / "licensed-sources.yaml")
    # Bootstrap: no source is operational yet, so the gate passes.
    assert assert_operational_sources_licensed(sources) == []
