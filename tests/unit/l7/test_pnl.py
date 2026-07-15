"""Per-position gross P&L (SPEC-080/082): win/lose/void, reduction factors, dead heats, rounding."""
from __future__ import annotations

from decimal import Decimal

import pytest

from l7_settle.outcomes import MarketStatus, MatchedPosition, RunnerOutcome, RunnerResult
from l7_settle.pnl import effective_odds, position_pnl_minor

pytestmark = [pytest.mark.spec("SPEC-080"), pytest.mark.spec("SPEC-082")]


def _pos(stake: int, odds: str, rfs: tuple[str, ...] = ()) -> MatchedPosition:
    return MatchedPosition(
        runner_id=111,
        matched_stake_minor=stake,
        matched_odds=Decimal(odds),
        applicable_reduction_factors=tuple(Decimal(r) for r in rfs),
    )


def _out(result: RunnerResult, dead_heat: int = 1, rf: str | None = None) -> RunnerOutcome:
    return RunnerOutcome(result=result, dead_heat_count=dead_heat, reduction_factor=None if rf is None else Decimal(rf))


def test_winner_simple() -> None:
    assert position_pnl_minor(_pos(200, "3.0"), _out(RunnerResult.WINNER), MarketStatus.SETTLED) == 400


def test_loser() -> None:
    assert position_pnl_minor(_pos(200, "3.0"), _out(RunnerResult.LOSER), MarketStatus.SETTLED) == -200


def test_void_market_is_zero() -> None:
    assert position_pnl_minor(_pos(200, "3.0"), _out(RunnerResult.WINNER), MarketStatus.VOID) == 0


def test_removed_runner_is_zero() -> None:
    assert position_pnl_minor(_pos(200, "3.0"), _out(RunnerResult.REMOVED, rf="0.5"), MarketStatus.SETTLED) == 0


def test_reduction_factor_reduces_winnings() -> None:
    # E = 1 + (3-1)*(1-0.1) = 2.8 ; profit = 200*1.8 = 360
    assert effective_odds(Decimal("3.0"), [Decimal("0.1")]) == Decimal("2.8")
    assert position_pnl_minor(_pos(200, "3.0", ("0.1",)), _out(RunnerResult.WINNER), MarketStatus.SETTLED) == 360


def test_dead_heat_two_way() -> None:
    # S/D*(E-1) - S*(D-1)/D = 100*2 - 100 = 100
    assert position_pnl_minor(_pos(200, "3.0"), _out(RunnerResult.WINNER, dead_heat=2), MarketStatus.SETTLED) == 100


def test_rounding_half_up_to_minor_units() -> None:
    # 150 * (3.45 - 1) = 150 * 2.45 = 367.5 -> 368
    assert position_pnl_minor(_pos(150, "3.45"), _out(RunnerResult.WINNER), MarketStatus.SETTLED) == 368
