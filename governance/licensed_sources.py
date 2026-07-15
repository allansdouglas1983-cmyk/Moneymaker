"""SPEC-101: operational data sources must be licensed for use before live.

Gate -1 fails if any source used operationally (in the deployable/betting pipeline) is not
``permitted`` with the rights required for that use. Until a human reviews a source it is
``candidate`` with unverified rights (a legal determination, never fabricated).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_OPERATIONAL_USES = ("model_training", "automated_betting", "retention", "derived_models")


class LicensingError(Exception):
    """Raised when an operational data source lacks the rights required for its use."""


def load_registry(path: Path) -> list[dict[str, Any]]:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise LicensingError(f"{path}: licensed-source registry must be a YAML list")
    sources: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise LicensingError(f"{path}: every source entry must be a mapping")
        sources.append(item)
    return sources


def assert_operational_sources_licensed(
    sources: list[dict[str, Any]], *, required_uses: tuple[str, ...] = REQUIRED_OPERATIONAL_USES
) -> list[str]:
    """Return the ids of operational sources checked; raise if any lacks the required rights."""
    checked: list[str] = []
    problems: list[str] = []
    for source in sources:
        source_id = str(source.get("source_id", "<unknown>"))
        operational = source.get("operational")
        if not isinstance(operational, bool):
            # Fail closed: the operational flag is the gate's trigger, so an absent/ambiguous
            # value is an error, not "assume research-only".
            problems.append(f"{source_id}: 'operational' must be an explicit boolean")
            continue
        if not operational:
            continue
        checked.append(source_id)
        if source.get("status") != "permitted":
            problems.append(
                f"{source_id}: operational but status is {source.get('status')!r}, not 'permitted'"
            )
            continue
        permitted = source.get("permitted_uses") or {}
        missing = [use for use in required_uses if not permitted.get(use)]
        if missing:
            problems.append(f"{source_id}: operational but missing rights: {', '.join(missing)}")
    if problems:
        raise LicensingError("; ".join(problems))
    return checked
