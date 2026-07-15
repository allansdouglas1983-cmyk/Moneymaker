"""Settlement ledger (SPEC-082): idempotent duplicate acks, versioned resettlements."""
from __future__ import annotations

from decimal import Decimal

import pytest

from l7_settle.ledger import SettlementConflict, SettlementLedger
from l7_settle.outcomes import MarketOutcome, MarketStatus, MatchedPosition, RunnerOutcome, RunnerResult
from l7_settle.settlement import MarketSettlement, settle_market

pytestmark = pytest.mark.spec("SPEC-082")


def _settlement(*, version: int = 1, resettlement: bool = False, rate: str = "0.02") -> MarketSettlement:
    outcome = MarketOutcome(market_status=MarketStatus.SETTLED, runners={111: RunnerOutcome(RunnerResult.WINNER)})
    return settle_market(
        market_id="1.1",
        positions=[MatchedPosition(runner_id=111, matched_stake_minor=200, matched_odds=Decimal("3.0"))],
        outcome=outcome,
        commission_rate_effective=Decimal(rate),
        transaction_charges_minor=0,
        statement_reference="stmt-1",
        settlement_version=version,
        resettlement_flag=resettlement,
    )


def test_duplicate_ack_is_idempotent() -> None:
    ledger = SettlementLedger()
    s = _settlement()
    first = ledger.apply(s)
    second = ledger.apply(s)  # duplicate acknowledgement
    assert first is second or first == second
    assert ledger.current("1.1") == s


def test_conflicting_same_version_raises() -> None:
    ledger = SettlementLedger()
    ledger.apply(_settlement(version=1, rate="0.02"))
    with pytest.raises(SettlementConflict):
        ledger.apply(_settlement(version=1, rate="0.05"))  # same version, different content


def test_resettlement_supersedes() -> None:
    ledger = SettlementLedger()
    ledger.apply(_settlement(version=1))
    resettled = _settlement(version=2, resettlement=True, rate="0.05")
    assert ledger.apply(resettled) == resettled
    assert ledger.current("1.1") == resettled


def test_new_version_without_flag_raises() -> None:
    ledger = SettlementLedger()
    ledger.apply(_settlement(version=1))
    with pytest.raises(SettlementConflict):
        ledger.apply(_settlement(version=2, resettlement=False))


def test_stale_version_raises() -> None:
    ledger = SettlementLedger()
    ledger.apply(_settlement(version=2, resettlement=True))
    with pytest.raises(SettlementConflict):
        ledger.apply(_settlement(version=1))
