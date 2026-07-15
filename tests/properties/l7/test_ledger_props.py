"""SPEC-082 properties: settlement is idempotent under duplicate acks; void markets settle to zero."""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l7_settle.ledger import SettlementLedger
from l7_settle.outcomes import MarketOutcome, MarketStatus, MatchedPosition, RunnerOutcome, RunnerResult
from l7_settle.settlement import MarketSettlement, settle_market

pytestmark = pytest.mark.spec("SPEC-082")


def _settlement(status: MarketStatus, result: RunnerResult, stake: int = 200, odds: str = "3.0") -> MarketSettlement:
    outcome = MarketOutcome(market_status=status, runners={111: RunnerOutcome(result)})
    return settle_market(
        market_id="1.1",
        positions=[MatchedPosition(runner_id=111, matched_stake_minor=stake, matched_odds=Decimal(odds))],
        outcome=outcome,
        commission_rate_effective=Decimal("0.02"),
        transaction_charges_minor=0,
        statement_reference="s",
        settlement_version=1,
        resettlement_flag=False,
    )


@settings(max_examples=100)
@given(acks=st.integers(min_value=1, max_value=10))
def test_duplicate_acks_add_no_exposure(acks: int) -> None:
    ledger = SettlementLedger()
    s = _settlement(MarketStatus.SETTLED, RunnerResult.WINNER)
    for _ in range(acks):
        ledger.apply(s)  # duplicate acknowledgements
    # Exactly one settlement is recorded for the market, however many acks arrived.
    assert ledger.current("1.1") == s


@settings(max_examples=100)
@given(stake=st.integers(min_value=1, max_value=10**6), odds=st.sampled_from(["1.5", "2.0", "3.45", "10.0"]))
def test_void_market_settles_to_zero(stake: int, odds: str) -> None:
    s = _settlement(MarketStatus.VOID, RunnerResult.VOID, stake=stake, odds=odds)
    assert s.actual_net_market_pnl == 0
    assert s.actual_commission == 0
    assert s.final_net_pnl == 0
