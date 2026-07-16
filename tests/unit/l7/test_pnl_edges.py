"""SPEC-082 audit-gap P&L edges: multi-factor reductions, dead-heat x reduction combination,
three-way dead heats, a rounding-mode discriminator, ABANDONED, and constructor guards.

Added by the 2026-07-16 retrospective audit. All tests are additive.
"""
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


def test_two_reduction_factors_combine_multiplicatively() -> None:
    # Betfair semantics: E = 1 + (O-1) * (1-a) * (1-b), NOT an additive "Rule 4" deduction.
    # 1 + 3 * 0.9 * 0.8 = 3.16. (Additive would give 1 + 3 * 0.7 = 3.10.)
    assert effective_odds(Decimal("4.0"), [Decimal("0.1"), Decimal("0.2")]) == Decimal("3.16")
    got = position_pnl_minor(
        _pos(100, "4.0", ("0.1", "0.2")), RunnerOutcome(RunnerResult.WINNER), MarketStatus.SETTLED
    )
    assert got == 216  # 100 * (3.16 - 1)


def test_empty_reduction_factors_leave_odds_unchanged() -> None:
    assert effective_odds(Decimal("3.0"), []) == Decimal("3.0")


def test_dead_heat_combined_with_reduction_factor() -> None:
    # E = 1 + 2 * 0.9 = 2.8; two-way dead heat on 200:
    # (200/2) * (2.8 - 1) - 200 * 1/2 = 180 - 100 = 80.
    got = position_pnl_minor(
        _pos(200, "3.0", ("0.1",)),
        RunnerOutcome(RunnerResult.WINNER, dead_heat_count=2),
        MarketStatus.SETTLED,
    )
    assert got == 80


def test_three_way_dead_heat() -> None:
    # (300/3) * (4 - 1) - 300 * 2/3 = 300 - 200 = 100.
    got = position_pnl_minor(
        _pos(300, "4.0"), RunnerOutcome(RunnerResult.WINNER, dead_heat_count=3), MarketStatus.SETTLED
    )
    assert got == 100


def test_rounding_is_half_up_not_bankers() -> None:
    # 1 * (3.5 - 1) = 2.5. ROUND_HALF_UP -> 3; ROUND_HALF_EVEN would give 2 (2 is even).
    # This case actually discriminates the two modes (367.5 -> 368 does not, 368 being even).
    got = position_pnl_minor(_pos(1, "3.5"), RunnerOutcome(RunnerResult.WINNER), MarketStatus.SETTLED)
    assert got == 3


def test_abandoned_market_position_is_zero() -> None:
    got = position_pnl_minor(_pos(200, "3.0"), RunnerOutcome(RunnerResult.WINNER), MarketStatus.ABANDONED)
    assert got == 0


def test_dead_heat_count_below_one_is_rejected() -> None:
    with pytest.raises(ValueError):
        RunnerOutcome(RunnerResult.WINNER, dead_heat_count=0)
    with pytest.raises(ValueError):
        RunnerOutcome(RunnerResult.WINNER, dead_heat_count=-1)
