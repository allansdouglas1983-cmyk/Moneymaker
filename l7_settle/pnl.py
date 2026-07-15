"""Per-position gross P&L (SPEC-080/082).

Exact ``Decimal`` arithmetic; each bet is rounded to minor units with ``ROUND_HALF_UP``
(Betfair settles per bet). BACK only (v1 has no lay). Reduction factors use Betfair semantics,
not bookmaker "Rule 4".
"""
from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from l7_settle.outcomes import MarketStatus, MatchedPosition, RunnerOutcome, RunnerResult

_ONE = Decimal(1)


def effective_odds(odds: Decimal, reduction_factors: Sequence[Decimal]) -> Decimal:
    """Odds after the winnings reductions of runners removed after this bet matched."""
    factor = _ONE
    for reduction in reduction_factors:
        factor *= _ONE - reduction
    return _ONE + (odds - _ONE) * factor


def _round_minor(value: Decimal) -> int:
    return int(value.quantize(_ONE, rounding=ROUND_HALF_UP))


def position_pnl_minor(
    position: MatchedPosition, runner_outcome: RunnerOutcome, market_status: MarketStatus
) -> int:
    """Gross P&L (minor units) for one BACK position under a runner outcome."""
    if market_status in (MarketStatus.VOID, MarketStatus.ABANDONED):
        return 0
    result = runner_outcome.result
    if result == RunnerResult.UNKNOWN:
        raise ValueError("cannot compute P&L for an UNKNOWN runner result")
    if result in (RunnerResult.VOID, RunnerResult.REMOVED):
        return 0
    stake = Decimal(position.matched_stake_minor)
    if result == RunnerResult.LOSER:
        return _round_minor(-stake)
    # WINNER, possibly part of a dead heat.
    payout_odds = effective_odds(position.matched_odds, position.applicable_reduction_factors)
    dead_heat = runner_outcome.dead_heat_count
    if dead_heat == 1:
        return _round_minor(stake * (payout_odds - _ONE))
    divisor = Decimal(dead_heat)
    winning_portion = (stake / divisor) * (payout_odds - _ONE)
    losing_portion = stake * (divisor - _ONE) / divisor
    return _round_minor(winning_portion - losing_portion)
