"""SPEC-082 audit-gap ledger edges: conflict and duplicate handling *after* a resettlement.

Added by the 2026-07-16 retrospective audit: prior ledger tests only exercised version 1 -> 2
transitions from a fresh ledger; these pin the state machine's behaviour once a resettlement
has already been applied.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from l7_settle.ledger import SettlementConflict, SettlementLedger
from l7_settle.outcomes import MarketOutcome, MarketStatus, MatchedPosition, RunnerOutcome, RunnerResult
from l7_settle.settlement import MarketSettlement, settle_market

pytestmark = [pytest.mark.spec("SPEC-082")]


def _settlement(*, rate: str = "0.02", version: int = 1, resettlement: bool = False) -> MarketSettlement:
    outcome = MarketOutcome(
        market_status=MarketStatus.SETTLED, runners={111: RunnerOutcome(RunnerResult.WINNER)}
    )
    return settle_market(
        market_id="1.1",
        positions=[MatchedPosition(runner_id=111, matched_stake_minor=200, matched_odds=Decimal("3.0"))],
        outcome=outcome,
        commission_rate_effective=Decimal(rate),
        statement_reference="stmt-1",
        settlement_version=version,
        resettlement_flag=resettlement,
    )


def _ledger_after_resettlement() -> SettlementLedger:
    ledger = SettlementLedger()
    ledger.apply(_settlement(version=1))
    ledger.apply(_settlement(version=2, resettlement=True))
    return ledger


def test_duplicate_of_resettlement_is_idempotent() -> None:
    ledger = _ledger_after_resettlement()
    result = ledger.apply(_settlement(version=2, resettlement=True))
    assert result == _settlement(version=2, resettlement=True)
    assert ledger.current("1.1") == result


def test_conflicting_duplicate_at_resettled_version_is_refused() -> None:
    ledger = _ledger_after_resettlement()
    with pytest.raises(SettlementConflict):
        ledger.apply(_settlement(rate="0.05", version=2, resettlement=True))


def test_stale_original_version_is_refused_after_resettlement() -> None:
    ledger = _ledger_after_resettlement()
    with pytest.raises(SettlementConflict):
        ledger.apply(_settlement(version=1))
    assert ledger.current("1.1") == _settlement(version=2, resettlement=True)


def test_second_resettlement_supersedes_again() -> None:
    ledger = _ledger_after_resettlement()
    third = _settlement(rate="0.03", version=3, resettlement=True)
    assert ledger.apply(third) == third
    assert ledger.current("1.1") == third
