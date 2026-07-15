"""Unit tests for tools/check_facts_freshness.py."""
from __future__ import annotations

import textwrap
from datetime import date
from pathlib import Path
from typing import Any

from tools import check_facts_freshness as cff


def _reg(root: Path, body: str) -> Path:
    f = root / "facts.yaml"
    f.write_text(textwrap.dedent(body), encoding="utf-8")
    return f


def test_unpopulated_ok(tmp_path: Path) -> None:
    f = _reg(
        tmp_path,
        """
        - fact_id: BETFAIR-COMMISSION-RATE
          value: null
          recheck_by: null
        """,
    )
    assert cff.main(["--registry", str(f), "--as-of", "2026-07-15"]) == 0


def test_stale_fails(tmp_path: Path) -> None:
    f = _reg(
        tmp_path,
        """
        - fact_id: BETFAIR-COMMISSION-RATE
          value: 0.02
          recheck_by: 2026-01-01
        """,
    )
    assert cff.main(["--registry", str(f), "--as-of", "2026-07-15"]) == 1


def test_fresh_ok(tmp_path: Path) -> None:
    f = _reg(
        tmp_path,
        """
        - fact_id: BETFAIR-COMMISSION-RATE
          value: 0.02
          recheck_by: 2026-12-31
        """,
    )
    assert cff.main(["--registry", str(f), "--as-of", "2026-07-15"]) == 0


def test_value_without_recheck_fails(tmp_path: Path) -> None:
    f = _reg(
        tmp_path,
        """
        - fact_id: BETFAIR-COMMISSION-RATE
          value: 0.02
          recheck_by: null
        """,
    )
    assert cff.main(["--registry", str(f), "--as-of", "2026-07-15"]) == 1


def test_real_registry_is_fresh() -> None:
    # The bootstrap docs/facts.yaml is entirely unpopulated -> must pass.
    assert cff.main(["--registry", "docs/facts.yaml", "--as-of", "2026-07-15"]) == 0


def test_check_registry_pure() -> None:
    facts: list[dict[str, Any]] = [
        {"fact_id": "A", "value": None, "recheck_by": None},
        {"fact_id": "B", "value": 1, "recheck_by": date(2020, 1, 1)},
    ]
    errs = cff.check_registry(facts, date(2026, 7, 15))
    assert len(errs) == 1
    assert "B" in errs[0]
