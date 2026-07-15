"""Market-level settlement (SPEC-080) and edge cases (SPEC-082)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from l7_settle.outcomes import MarketOutcome, MarketStatus, MatchedPosition, RunnerOutcome, RunnerResult
from l7_settle.settlement import MarketSettlement, SettlementBlocked, settle_market

pytestmark = [pytest.mark.spec("SPEC-080"), pytest.mark.spec("SPEC-082")]


def _pos(runner_id: int, stake: int, odds: str) -> MatchedPosition:
    return MatchedPosition(runner_id=runner_id, matched_stake_minor=stake, matched_odds=Decimal(odds))


def _settle(
    positions: list[MatchedPosition],
    outcome: MarketOutcome,
    *,
    rate: str = "0.02",
    charges: int = 0,
    version: int = 1,
    resettlement: bool = False,
) -> MarketSettlement:
    return settle_market(
        market_id="1.1",
        positions=positions,
        outcome=outcome,
        commission_rate_effective=Decimal(rate),
        transaction_charges_minor=charges,
        statement_reference="stmt-1",
        settlement_version=version,
        resettlement_flag=resettlement,
    )


def _outcome(status: MarketStatus, runners: dict[int, RunnerOutcome]) -> MarketOutcome:
    return MarketOutcome(market_status=status, runners=runners)


def test_no_per_order_commission_field() -> None:
    # SPEC-080: commission_est must not exist as an authoritative per-order field.
    for forbidden in ("commission_est", "commission", "commission_minor"):
        assert not hasattr(MatchedPosition, forbidden)


def test_winning_market_applies_commission_on_net() -> None:
    # winner 200 @ 3.0 -> gross 400; commission 2% of 400 = 8; final = 400 - 8 = 392
    outcome = _outcome(MarketStatus.SETTLED, {111: RunnerOutcome(RunnerResult.WINNER), 222: RunnerOutcome(RunnerResult.LOSER)})
    s = _settle([_pos(111, 200, "3.0")], outcome)
    assert s.actual_net_market_pnl == 400
    assert s.actual_commission == 8
    assert s.final_net_pnl == 392


def test_losing_market_charges_no_commission() -> None:
    outcome = _outcome(MarketStatus.SETTLED, {111: RunnerOutcome(RunnerResult.LOSER), 222: RunnerOutcome(RunnerResult.WINNER)})
    s = _settle([_pos(111, 200, "3.0")], outcome)
    assert s.actual_net_market_pnl == -200
    assert s.actual_commission == 0
    assert s.final_net_pnl == -200


def test_transaction_charges_subtracted() -> None:
    outcome = _outcome(MarketStatus.SETTLED, {111: RunnerOutcome(RunnerResult.WINNER)})
    s = _settle([_pos(111, 200, "3.0")], outcome, charges=5)
    assert s.final_net_pnl == 400 - 8 - 5


def test_multiple_orders_on_one_runner_sum() -> None:
    outcome = _outcome(MarketStatus.SETTLED, {111: RunnerOutcome(RunnerResult.WINNER)})
    s = _settle([_pos(111, 200, "3.0"), _pos(111, 100, "3.0")], outcome)
    assert s.actual_net_market_pnl == 400 + 200  # 600


def test_void_market_is_all_zero() -> None:
    outcome = _outcome(MarketStatus.VOID, {111: RunnerOutcome(RunnerResult.VOID)})
    s = _settle([_pos(111, 200, "3.0")], outcome)
    assert s.actual_net_market_pnl == 0
    assert s.actual_commission == 0
    assert s.final_net_pnl == 0


def test_unknown_status_blocks_settlement() -> None:
    outcome = _outcome(MarketStatus.UNKNOWN, {111: RunnerOutcome(RunnerResult.UNKNOWN)})
    with pytest.raises(SettlementBlocked):
        _settle([_pos(111, 200, "3.0")], outcome)


def test_unknown_runner_status_blocks_settlement() -> None:
    outcome = _outcome(MarketStatus.SETTLED, {111: RunnerOutcome(RunnerResult.UNKNOWN)})
    with pytest.raises(SettlementBlocked):
        _settle([_pos(111, 200, "3.0")], outcome)


def test_void_market_still_incurs_transaction_charges() -> None:
    # Transaction charges are a placement cost, independent of the (void) outcome.
    outcome = _outcome(MarketStatus.VOID, {111: RunnerOutcome(RunnerResult.VOID)})
    s = _settle([_pos(111, 200, "3.0")], outcome, charges=5)
    assert s.actual_net_market_pnl == 0
    assert s.actual_commission == 0
    assert s.transaction_charges == 5
    assert s.final_net_pnl == -5


def test_settlement_is_hashable() -> None:
    outcome = _outcome(MarketStatus.SETTLED, {111: RunnerOutcome(RunnerResult.WINNER)})
    s = _settle([_pos(111, 200, "3.0")], outcome)
    assert hash(s) == hash(s)  # scenario dict excluded from __hash__; object is hashable


def test_scenario_matrix_present() -> None:
    outcome = _outcome(
        MarketStatus.SETTLED,
        {111: RunnerOutcome(RunnerResult.WINNER), 222: RunnerOutcome(RunnerResult.LOSER)},
    )
    s = _settle([_pos(111, 200, "3.0")], outcome)
    # If 111 wins: +400 ; if 222 wins: -200 (the back on 111 loses).
    assert s.gross_pnl_by_selection_scenario["111"] == 400
    assert s.gross_pnl_by_selection_scenario["222"] == -200
