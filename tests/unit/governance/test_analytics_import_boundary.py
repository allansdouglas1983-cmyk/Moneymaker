"""ADR 0013 / SPEC-045 architecture boundary, continuously enforced (founder direction,
2026-07-16): prediction/analytics contract modules must never import trading decision state,
broker code, risk state, account state or settlement commands.

Runs the real transitive import-graph checker (which also sees literal dynamic imports and
fails closed on unparseable files) over the ACTUAL repository on every test run — the absence
of coupling is enforced, not merely observed once. The module list auto-extends: any listed
analytics module that exists is checked; adding a new analytics module to the repo without
listing it here should be caught in review, and the SPEC-045 slice will add the
analytics_contracts package to this list when it lands.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.check_import_quarantine import find_violations

pytestmark = pytest.mark.spec("SPEC-045")

_REPO = Path(__file__).resolve().parents[3]

# Read-only analytics/prediction consumer surface (extends as slices land).
_ANALYTICS_MODULES = (
    "analytics_contracts",
    "sport_core",
    "l4_pricing.probability_outputs",
    "governance.output_rights",
    "l8_evidence.prediction_snapshots",
    "l8_evidence.predictor_metrics",
    "l8_evidence.explanation_inputs",
    "l8_evidence.trial_ledger",
    "l8_evidence.lockbox",
    "l8_evidence.paired_inference",
    "l8_evidence.sample_size",
    "l8_evidence.clv",
    "l8_evidence.calibration",
)

# Trading state the analytics consumer must never reach (directly or transitively).
_FORBIDDEN_TRADING_TARGETS = (
    "l5_decision",
    "l5b_risk",
    "l6_broker",
    "l7_settle",
)


@pytest.mark.parametrize("forbidden", _FORBIDDEN_TRADING_TARGETS)
def test_analytics_modules_never_reach_trading_state(forbidden: str) -> None:
    violations = find_violations(_REPO, forbidden, list(_ANALYTICS_MODULES))
    assert violations == [], (
        f"analytics/prediction modules must not reach {forbidden!r} "
        f"(ADR 0013 read-only consumer boundary):\n" + "\n".join(violations)
    )


def test_boundary_check_is_not_vacuous() -> None:
    # At least one listed analytics module must actually exist in the repo, otherwise the
    # parametrised checks above would pass on an empty from-set.
    existing = [
        m for m in _ANALYTICS_MODULES if (_REPO / (m.replace(".", "/") + ".py")).exists()
        or (_REPO / m.replace(".", "/")).is_dir()
    ]
    assert existing, "no analytics modules found — the boundary test would be vacuous"
