"""Market-level settlement (SPEC-080) with edge cases (SPEC-082).

Commission is charged on the **net market result**, never per order (there is no authoritative
per-order commission field anywhere). Unknown status blocks settlement; void/abandoned markets
settle every position to zero.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from l7_settle.outcomes import MarketOutcome, MarketStatus, MatchedPosition, RunnerOutcome, RunnerResult
from l7_settle.pnl import position_pnl_minor

_ONE = Decimal(1)


class SettlementBlocked(Exception):
    """Raised when settlement cannot proceed because a market/runner status is UNKNOWN."""


@dataclass(frozen=True)
class MarketSettlement:
    market_id: str
    gross_pnl_by_selection_scenario: dict[str, int]
    actual_net_market_pnl: int
    commission_rate_effective: Decimal
    actual_commission: int
    transaction_charges: int
    final_net_pnl: int
    statement_reference: str
    settlement_version: int
    resettlement_flag: bool


def _runner_outcome(outcome: MarketOutcome, runner_id: int) -> RunnerOutcome:
    existing = outcome.runners.get(runner_id)
    if existing is not None:
        return existing
    # A position on a runner absent from the outcome cannot be settled — treat as unknown.
    return RunnerOutcome(result=RunnerResult.UNKNOWN)


def _commission_minor(rate: Decimal, net_minor: int) -> int:
    # Commission is charged only on net winnings (SPEC-080).
    if net_minor <= 0:
        return 0
    return int((rate * Decimal(net_minor)).quantize(_ONE, rounding=ROUND_HALF_UP))


def _scenario_matrix(positions: Sequence[MatchedPosition], outcome: MarketOutcome) -> dict[str, int]:
    runner_ids: set[int] = {p.runner_id for p in positions}
    for runner_id, runner_outcome in outcome.runners.items():
        if runner_outcome.result != RunnerResult.REMOVED:
            runner_ids.add(runner_id)
    matrix: dict[str, int] = {}
    for winner in sorted(runner_ids):
        total = 0
        for position in positions:
            actual = outcome.runners.get(position.runner_id)
            if actual is not None and actual.result == RunnerResult.REMOVED:
                hypothetical = RunnerOutcome(result=RunnerResult.REMOVED, reduction_factor=actual.reduction_factor)
            elif position.runner_id == winner:
                hypothetical = RunnerOutcome(result=RunnerResult.WINNER)
            else:
                hypothetical = RunnerOutcome(result=RunnerResult.LOSER)
            total += position_pnl_minor(position, hypothetical, MarketStatus.SETTLED)
        matrix[str(winner)] = total
    return matrix


def settle_market(
    *,
    market_id: str,
    positions: Sequence[MatchedPosition],
    outcome: MarketOutcome,
    commission_rate_effective: Decimal,
    transaction_charges_minor: int = 0,
    statement_reference: str,
    settlement_version: int = 1,
    resettlement_flag: bool = False,
) -> MarketSettlement:
    if outcome.market_status == MarketStatus.UNKNOWN:
        raise SettlementBlocked(f"{market_id}: market status is UNKNOWN")
    for runner_id in {p.runner_id for p in positions}:
        if _runner_outcome(outcome, runner_id).result == RunnerResult.UNKNOWN:
            raise SettlementBlocked(f"{market_id}: runner {runner_id} status is UNKNOWN")

    voided = outcome.market_status in (MarketStatus.VOID, MarketStatus.ABANDONED)

    net = 0
    for position in positions:
        net += position_pnl_minor(position, _runner_outcome(outcome, position.runner_id), outcome.market_status)

    commission = 0 if voided else _commission_minor(commission_rate_effective, net)
    charges = 0 if voided else transaction_charges_minor
    scenarios: dict[str, int] = {} if voided else _scenario_matrix(positions, outcome)

    return MarketSettlement(
        market_id=market_id,
        gross_pnl_by_selection_scenario=scenarios,
        actual_net_market_pnl=net,
        commission_rate_effective=commission_rate_effective,
        actual_commission=commission,
        transaction_charges=charges,
        final_net_pnl=net - commission - charges,
        statement_reference=statement_reference,
        settlement_version=settlement_version,
        resettlement_flag=resettlement_flag,
    )
