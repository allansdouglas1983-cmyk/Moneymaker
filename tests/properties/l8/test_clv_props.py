"""SPEC-095 properties: CLV diagnostic family sign convention, benchmark separation,
unfilled-order honesty, and determinism.

Every property here is stated purely in terms of the four typed CLV quantities and the two
retained closing benchmarks — there is no float representing a price anywhere, and no
property here ever assigns a hypothetical taken price to an unfilled order.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l8_evidence.clv import (
    CLVBatchError,
    ClosingBenchmark,
    ClosingPrice,
    ClosingPriceError,
    ExecutionCaptureDelta,
    ExecutionCaptureDeltaError,
    IntendedOrderCLV,
    RealisedFillCLV,
    SignalCLV,
    UnfilledOrder,
    UnfilledOutcome,
    realised_fill_clvs,
)

pytestmark = pytest.mark.spec("SPEC-095")

_ODDS = st.decimals(min_value=Decimal("1.01"), max_value=Decimal("1000"), places=2)


def _bsp(odds: Decimal) -> ClosingPrice:
    return ClosingPrice(benchmark=ClosingBenchmark.BSP, odds=odds)


# --- sign convention: strict monotone relationship to (odds_taken - odds_close) --------------


@given(odds_taken=_ODDS, odds_close=_ODDS)
@settings(max_examples=200)
def test_clv_bps_sign_matches_taken_vs_close(odds_taken: Decimal, odds_close: Decimal) -> None:
    closing = _bsp(odds_close)
    signal = SignalCLV(candidate_ref="c", closing=closing, odds_at_signal=odds_taken)
    if odds_taken > odds_close:
        assert signal.clv_bps > 0
    elif odds_taken < odds_close:
        assert signal.clv_bps < 0
    else:
        assert signal.clv_bps == Decimal("0.00")


@given(odds_taken=_ODDS, odds_close=_ODDS)
@settings(max_examples=200)
def test_clv_bps_is_negation_symmetric_under_swap(odds_taken: Decimal, odds_close: Decimal) -> None:
    """Swapping which price is "taken" and which is "close" negates the bps sign convention,
    since the formula is antisymmetric in (odds_taken, odds_close)."""
    forward = IntendedOrderCLV(order_ref="o", closing=_bsp(odds_close), odds_intended=odds_taken)
    backward = IntendedOrderCLV(order_ref="o", closing=_bsp(odds_taken), odds_intended=odds_close)
    assert forward.clv_bps == -backward.clv_bps


# --- odds_ratio: exact secondary representation ----------------------------------------------


@given(odds_taken=_ODDS, odds_close=_ODDS)
@settings(max_examples=200)
def test_odds_ratio_matches_direct_division(odds_taken: Decimal, odds_close: Decimal) -> None:
    fill = RealisedFillCLV(
        order_ref="o", closing=_bsp(odds_close), odds_matched=odds_taken, matched_stake_minor=100
    )
    assert fill.odds_ratio == odds_taken / odds_close


# --- determinism: content_digest is a pure function of stored fields --------------------------


@given(odds_taken=_ODDS, odds_close=_ODDS, stake=st.integers(min_value=1, max_value=10_000_00))
@settings(max_examples=100)
def test_content_digest_is_deterministic(odds_taken: Decimal, odds_close: Decimal, stake: int) -> None:
    closing = _bsp(odds_close)
    fill_a = RealisedFillCLV(
        order_ref="o", closing=closing, odds_matched=odds_taken, matched_stake_minor=stake
    )
    fill_b = RealisedFillCLV(
        order_ref="o", closing=closing, odds_matched=odds_taken, matched_stake_minor=stake
    )
    assert fill_a.content_digest() == fill_b.content_digest()


# --- ExecutionCaptureDelta: value_bps is exactly realised - intended, whenever construction ---
# --- succeeds; construction never succeeds across differing closing observations ------------


@given(odds_intended=_ODDS, odds_matched=_ODDS, odds_close=_ODDS, stake=st.integers(min_value=1, max_value=100_000))
@settings(max_examples=200)
def test_execution_policy_value_equals_difference_when_closings_match(
    odds_intended: Decimal, odds_matched: Decimal, odds_close: Decimal, stake: int
) -> None:
    closing = _bsp(odds_close)
    intended = IntendedOrderCLV(order_ref="o", closing=closing, odds_intended=odds_intended)
    realised = RealisedFillCLV(
        order_ref="o", closing=closing, odds_matched=odds_matched, matched_stake_minor=stake
    )
    epv = ExecutionCaptureDelta(intended=intended, realised=realised)
    assert epv.value_bps == realised.clv_bps - intended.clv_bps


@given(odds_a=_ODDS, odds_b=_ODDS, stake=st.integers(min_value=1, max_value=100_000))
@settings(max_examples=200)
def test_execution_policy_value_refuses_differing_bsp_observations(
    odds_a: Decimal, odds_b: Decimal, stake: int
) -> None:
    if odds_a == odds_b:
        return
    intended = IntendedOrderCLV(order_ref="o", closing=_bsp(odds_a), odds_intended=Decimal("2.0"))
    realised = RealisedFillCLV(
        order_ref="o", closing=_bsp(odds_b), odds_matched=Decimal("2.0"), matched_stake_minor=stake
    )
    with pytest.raises(ExecutionCaptureDeltaError):
        ExecutionCaptureDelta(intended=intended, realised=realised)


# --- WAP window: valid iff start > 0 and end >= 0 and start > end ---------------------------


@given(
    start=st.integers(min_value=-1000, max_value=1000),
    end=st.integers(min_value=-1000, max_value=1000),
)
@settings(max_examples=200)
def test_wap_window_construction_matches_validity_predicate(start: int, end: int) -> None:
    is_valid = start > 0 and end >= 0 and start > end
    if is_valid:
        closing = ClosingPrice(
            benchmark=ClosingBenchmark.PRE_SUSPENSION_WAP,
            odds=Decimal("2.5"),
            window_start_seconds_before_suspension=start,
            window_end_seconds_before_suspension=end,
        )
        assert closing.window_start_seconds_before_suspension == start
        assert closing.window_end_seconds_before_suspension == end
    else:
        with pytest.raises(ClosingPriceError):
            ClosingPrice(
                benchmark=ClosingBenchmark.PRE_SUSPENSION_WAP,
                odds=Decimal("2.5"),
                window_start_seconds_before_suspension=start,
                window_end_seconds_before_suspension=end,
            )


# --- CLVBatch: counts always sum honestly, unfilled never dropped ---------------------------


@given(
    n_fills=st.integers(min_value=0, max_value=10),
    n_unfilled=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100)
def test_clv_batch_counts_always_sum(n_fills: int, n_unfilled: int) -> None:
    closing = _bsp(Decimal("2.5"))
    fills = tuple(
        RealisedFillCLV(
            order_ref=f"f-{i}", closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=100
        )
        for i in range(n_fills)
    )
    unfilled = tuple(
        UnfilledOrder(order_ref=f"u-{i}", outcome=UnfilledOutcome.LAPSED) for i in range(n_unfilled)
    )
    batch = realised_fill_clvs(fills, unfilled)
    assert batch.filled_count == n_fills
    assert batch.unfilled_count == n_unfilled
    assert batch.total_count == n_fills + n_unfilled
    assert len(batch.realised) == n_fills
    assert len(batch.unfilled) == n_unfilled


@given(shared_count=st.integers(min_value=1, max_value=5))
@settings(max_examples=50)
def test_clv_batch_refuses_overlapping_order_refs(shared_count: int) -> None:
    closing = _bsp(Decimal("2.5"))
    shared_refs = [f"shared-{i}" for i in range(shared_count)]
    fills = tuple(
        RealisedFillCLV(
            order_ref=ref, closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=100
        )
        for ref in shared_refs
    )
    unfilled = tuple(UnfilledOrder(order_ref=ref, outcome=UnfilledOutcome.CANCELLED) for ref in shared_refs)
    with pytest.raises(CLVBatchError):
        realised_fill_clvs(fills, unfilled)
