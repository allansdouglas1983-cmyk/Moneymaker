"""SPEC-080 properties: commission is on net winnings only, and monotone in the rate."""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l7_settle.outcomes import MarketOutcome, MarketStatus, MatchedPosition, RunnerOutcome, RunnerResult
from l7_settle.settlement import MarketSettlement, settle_market

pytestmark = pytest.mark.spec("SPEC-080")

_ODDS = st.sampled_from(["1.5", "2.0", "3.0", "3.45", "5.0", "10.0"])
_STAKE = st.integers(min_value=1, max_value=1_000_000)
_RATE = st.decimals(min_value=Decimal("0"), max_value=Decimal("0.2"), places=3)


def _settle(stake: int, odds: str, result: RunnerResult, rate: Decimal, charges: int = 0) -> MarketSettlement:
    outcome = MarketOutcome(market_status=MarketStatus.SETTLED, runners={111: RunnerOutcome(result)})
    return settle_market(
        market_id="1.1",
        positions=[MatchedPosition(runner_id=111, matched_stake_minor=stake, matched_odds=Decimal(odds))],
        outcome=outcome,
        commission_rate_effective=rate,
        transaction_charges_minor=charges,
        statement_reference="s",
        settlement_version=1,
        resettlement_flag=False,
    )


@settings(max_examples=200)
@given(stake=_STAKE, odds=_ODDS, rate=_RATE, charges=st.integers(min_value=0, max_value=10_000))
def test_settlement_identity(stake: int, odds: str, rate: Decimal, charges: int) -> None:
    s = _settle(stake, odds, RunnerResult.WINNER, rate, charges)
    assert s.final_net_pnl == s.actual_net_market_pnl - s.actual_commission - s.transaction_charges


@settings(max_examples=200)
@given(stake=_STAKE, odds=_ODDS, rate=_RATE)
def test_loser_never_charged_commission(stake: int, odds: str, rate: Decimal) -> None:
    s = _settle(stake, odds, RunnerResult.LOSER, rate)
    assert s.actual_net_market_pnl < 0
    assert s.actual_commission == 0


@settings(max_examples=200)
@given(stake=_STAKE, odds=_ODDS, r1=_RATE, r2=_RATE)
def test_commission_monotone_in_rate(stake: int, odds: str, r1: Decimal, r2: Decimal) -> None:
    lo, hi = sorted((r1, r2))
    s_lo = _settle(stake, odds, RunnerResult.WINNER, lo)
    s_hi = _settle(stake, odds, RunnerResult.WINNER, hi)
    # Winner -> net > 0, so a higher commission rate never increases the final P&L.
    assert s_hi.final_net_pnl <= s_lo.final_net_pnl
