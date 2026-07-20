"""Stage 2G Slice 3 — the evaluation script's F2-v1 comparator is pinned to the FROZEN
per-tour configuration (founder pre-result controls §1, 2026-07-20).

The frozen selection (F2_EVALUATION_REPORT.json `selected_k`; rule per
f2-global-elo-registration-v1.yaml `k_selection`) is ATP K=24.0, WTA K=32.0, and
calibrated-F2 comparisons use the calibration-policy-v2 frozen affine vintage. A run
with any other comparator is INVALID_COMPARATOR_CONFIGURATION and is never evidence.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

_REPO = Path(__file__).resolve().parents[3]


def _load_script() -> ModuleType:
    path = _REPO / "docs/evidence/stage2g-dp1-development/scripts/dp1_run.py"
    spec = importlib.util.spec_from_file_location("dp1_run", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dp1_run"] = module  # dataclasses resolve cls.__module__ via sys.modules
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop("dp1_run", None)
    return module


def test_comparator_k_matches_the_frozen_per_tour_selection() -> None:
    module = _load_script()
    frozen = json.loads(
        (_REPO / "docs/evidence/stage2b-f0-f2-runs/F2_EVALUATION_REPORT.json").read_text()
    )
    expected = {tour: frozen[tour]["selected_k"] for tour in ("ATP", "WTA")}
    assert expected == {"ATP": 24.0, "WTA": 32.0}  # the frozen record itself
    assert getattr(module, "FROZEN_F2_K_BY_TOUR", None) == expected, (
        "the evaluation script must carry the exact frozen per-tour K selection — "
        "K=24 applied to WTA is INVALID_COMPARATOR_CONFIGURATION, not a simplification"
    )
    assert not hasattr(module, "FROZEN_F2_K"), (
        "the single-K constant must be gone; a pooled K cannot express the frozen comparator"
    )


def test_comparator_affine_vintage_matches_calibration_policy_v2() -> None:
    module = _load_script()
    assert getattr(module, "FROZEN_F2_AFFINE_BY_TOUR", None) == {
        "ATP": {"intercept": 0.025399, "temperature": 1.218638},
        "WTA": {"intercept": 0.029204, "temperature": 1.150681},
    }, "calibrated-F2 series must use the frozen calibration-policy-v2 vintage exactly"


def test_script_asserts_the_comparator_at_runtime() -> None:
    """The script must self-refuse a comparator drift (not rely on this test alone)."""
    module = _load_script()
    assert hasattr(module, "assert_frozen_comparator"), (
        "dp1_run must expose assert_frozen_comparator() and call it in main() before "
        "any evaluation work"
    )
    module.assert_frozen_comparator()  # must pass against the frozen report
