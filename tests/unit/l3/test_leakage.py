"""BSP-leakage guard — static import-graph AND runtime assertion (SPEC-021).

Reconciled BSP MUST NOT be reachable from any pre-off feature. Enforced two ways:
  * static: no import path from ``l3_features`` reaches the grading-only BSP module;
  * runtime: a reconciled-BSP-tainted value passed as a feature input is rejected.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from l3_features.leakage import (
    _RECONCILED_BSP_TAINT,
    BSPLeakageError,
    assert_no_bsp,
    is_reconciled_bsp,
)
from l8_evidence.reconciled_bsp import RECONCILED_BSP_TAINT, ReconciledBSP
from tools.check_import_quarantine import find_violations

pytestmark = pytest.mark.spec("SPEC-021")

_ROOT = Path(__file__).resolve().parents[3]
_BSP_MODULE = "l8_evidence.reconciled_bsp"


class TestStaticImportGraph:
    def test_l3_features_cannot_reach_reconciled_bsp(self) -> None:
        violations = find_violations(_ROOT, forbid=_BSP_MODULE, from_pkgs=["l3_features"])
        assert violations == [], f"BSP reachable from l3_features: {violations}"

    def test_the_guard_would_catch_a_real_import(self, tmp_path: Path) -> None:
        # Sanity: the mechanism is not vacuous — a module that DOES import BSP is flagged.
        pkg = tmp_path / "l3_features"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "bad.py").write_text("import l8_evidence.reconciled_bsp\n", encoding="utf-8")
        (tmp_path / "l8_evidence").mkdir()
        (tmp_path / "l8_evidence" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "l8_evidence" / "reconciled_bsp.py").write_text("", encoding="utf-8")
        violations = find_violations(tmp_path, forbid=_BSP_MODULE, from_pkgs=["l3_features"])
        assert violations, "quarantine check failed to flag a real forbidden import"


class TestRuntimeAssertion:
    def test_reconciled_bsp_value_is_detected(self) -> None:
        bsp = ReconciledBSP(selection_id=111, bsp=Decimal("4.2"))
        assert is_reconciled_bsp(bsp) is True

    def test_plain_value_is_not_flagged(self) -> None:
        assert is_reconciled_bsp(Decimal("4.2")) is False
        assert is_reconciled_bsp(3) is False
        assert is_reconciled_bsp("scheduled_start") is False

    def test_assert_no_bsp_rejects_reconciled_bsp(self) -> None:
        bsp = ReconciledBSP(selection_id=111, bsp=Decimal("4.2"))
        with pytest.raises(BSPLeakageError):
            assert_no_bsp(bsp, field="fav_bsp")

    def test_assert_no_bsp_passes_clean_value(self) -> None:
        assert_no_bsp(Decimal("3.5"), field="ltp")  # no raise

    def test_taint_marker_matches_grading_module(self) -> None:
        # The runtime guard duplicates the taint string (it must NOT import the grading-only
        # module — that is the forbidden edge). This test is the anti-drift net: if either
        # literal is edited the guard would silently stop detecting real BSP. Importing both
        # here is safe — a test module is not part of l3_features, so no forbidden edge.
        assert _RECONCILED_BSP_TAINT == RECONCILED_BSP_TAINT
