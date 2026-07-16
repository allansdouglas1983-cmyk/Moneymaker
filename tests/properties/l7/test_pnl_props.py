"""SPEC-082 properties for per-position P&L: closed-form agreement, monotonicities, bounds.

Added by the 2026-07-16 retrospective audit: `pnl.py` — the numerically riskiest part of
settlement (dead heats, reduction factors, rounding) — previously had only directed examples.

The generated domain (odds/factors with two decimal places, dead-heat counts <= 8) keeps every
intermediate value far from any half-unit rounding boundary relative to Decimal's 28-digit
context, so the monotonicity assertions cannot be flipped by representation error.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l7_settle.outcomes import MarketStatus, MatchedPosition, RunnerOutcome, RunnerResult
from l7_settle.pnl import effective_odds, position_pnl_minor

pytestmark = [pytest.mark.spec("SPEC-080"), pytest.mark.spec("SPEC-082")]

_STAKE = st.integers(min_value=1, max_value=1_000_000)
_ODDS = st.decimals(min_value=Decimal("1.01"), max_value=Decimal("1000"), places=2)
_RF = st.decimals(min_value=Decimal("0"), max_value=Decimal("0.9"), places=2)
_RFS = st.lists(_RF, min_size=0, max_size=4).map(tuple)
_DH = st.integers(min_value=1, max_value=8)


def _pos(stake: int, odds: Decimal, rfs: tuple[Decimal, ...] = ()) -> MatchedPosition:
    return MatchedPosition(
        runner_id=111, matched_stake_minor=stake, matched_odds=odds, applicable_reduction_factors=rfs
    )


def _closed_form(stake: int, odds: Decimal, rfs: tuple[Decimal, ...], dead_heat: int) -> int:
    """Independent re-derivation of the specified formula (same operation order as the spec)."""
    factor = Decimal(1)
    for reduction in rfs:
        factor *= Decimal(1) - reduction
    payout = Decimal(1) + (odds - Decimal(1)) * factor
    s = Decimal(stake)
    if dead_heat == 1:
        value = s * (payout - Decimal(1))
    else:
        d = Decimal(dead_heat)
        value = (s / d) * (payout - Decimal(1)) - s * (d - Decimal(1)) / d
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


@settings(max_examples=200)
@given(stake=_STAKE, odds=_ODDS, rfs=_RFS, dead_heat=_DH)
def test_winner_matches_closed_form(stake: int, odds: Decimal, rfs: tuple[Decimal, ...], dead_heat: int) -> None:
    got = position_pnl_minor(
        _pos(stake, odds, rfs), RunnerOutcome(RunnerResult.WINNER, dead_heat_count=dead_heat), MarketStatus.SETTLED
    )
    assert got == _closed_form(stake, odds, rfs, dead_heat)


@settings(max_examples=200)
@given(stake=_STAKE, odds=_ODDS, rfs=_RFS, dead_heat=_DH)
def test_loser_pnl_is_exactly_negative_stake(
    stake: int, odds: Decimal, rfs: tuple[Decimal, ...], dead_heat: int
) -> None:
    # Odds, reduction factors and dead-heat counts are irrelevant inputs for a loser.
    got = position_pnl_minor(
        _pos(stake, odds, rfs), RunnerOutcome(RunnerResult.LOSER, dead_heat_count=dead_heat), MarketStatus.SETTLED
    )
    assert got == -stake


@settings(max_examples=200)
@given(odds=_ODDS, rfs=_RFS, extra=_RF)
def test_adding_a_reduction_factor_never_increases_effective_odds(
    odds: Decimal, rfs: tuple[Decimal, ...], extra: Decimal
) -> None:
    assert effective_odds(odds, rfs + (extra,)) <= effective_odds(odds, rfs)


@settings(max_examples=200)
@given(odds=_ODDS, rfs=_RFS)
def test_effective_odds_are_order_independent(odds: Decimal, rfs: tuple[Decimal, ...]) -> None:
    assert effective_odds(odds, tuple(reversed(rfs))) == effective_odds(odds, rfs)


@settings(max_examples=200)
@given(stake=_STAKE, odds=_ODDS, rfs=_RFS, dead_heat=st.integers(min_value=1, max_value=7))
def test_deeper_dead_heat_never_pays_more(
    stake: int, odds: Decimal, rfs: tuple[Decimal, ...], dead_heat: int
) -> None:
    shallower = position_pnl_minor(
        _pos(stake, odds, rfs), RunnerOutcome(RunnerResult.WINNER, dead_heat_count=dead_heat), MarketStatus.SETTLED
    )
    deeper = position_pnl_minor(
        _pos(stake, odds, rfs),
        RunnerOutcome(RunnerResult.WINNER, dead_heat_count=dead_heat + 1),
        MarketStatus.SETTLED,
    )
    assert deeper <= shallower


@settings(max_examples=200)
@given(stake=_STAKE, odds=_ODDS, rfs=_RFS, dead_heat=_DH)
def test_winner_pnl_is_bounded(stake: int, odds: Decimal, rfs: tuple[Decimal, ...], dead_heat: int) -> None:
    got = position_pnl_minor(
        _pos(stake, odds, rfs), RunnerOutcome(RunnerResult.WINNER, dead_heat_count=dead_heat), MarketStatus.SETTLED
    )
    unreduced_max = int((Decimal(stake) * (odds - Decimal(1))).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    assert -stake <= got <= unreduced_max


@settings(max_examples=100)
@given(
    stake=_STAKE,
    odds=_ODDS,
    rfs=_RFS,
    dead_heat=_DH,
    status=st.sampled_from([MarketStatus.VOID, MarketStatus.ABANDONED]),
    result=st.sampled_from([RunnerResult.WINNER, RunnerResult.LOSER, RunnerResult.REMOVED, RunnerResult.VOID]),
)
def test_void_and_abandoned_markets_always_settle_to_zero(
    stake: int,
    odds: Decimal,
    rfs: tuple[Decimal, ...],
    dead_heat: int,
    status: MarketStatus,
    result: RunnerResult,
) -> None:
    got = position_pnl_minor(
        _pos(stake, odds, rfs), RunnerOutcome(result, dead_heat_count=dead_heat), MarketStatus(status)
    )
    assert got == 0
