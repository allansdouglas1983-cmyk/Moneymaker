"""SPEC-095: CLV diagnostic family — signal, intended-order, realised-fill CLV and
execution-policy value.

Four distinct quantities (SPECIFICATION.md §8 / ``.claude/rules/evidence.md``): signal CLV,
intended-order CLV, realised-fill CLV, execution-policy value. Realised-fill CLV MUST NOT
exist for unfilled orders — assigning hypothetical taken prices is forbidden. Exactly two
closing benchmarks are retained (BSP, PRE_SUSPENSION_WAP) and are never merged. CLV MUST NOT
be a training target: this module imports nothing from ``l4_pricing`` (or any trading-state
package), and no public name in it uses ML-target/ML-label vocabulary.
"""
from __future__ import annotations

import inspect
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import pytest

from l8_evidence.clv import (
    CLVBatch,
    CLVBatchError,
    ClosingBenchmark,
    ClosingPrice,
    ClosingPriceError,
    ClvError,
    ExecutionCaptureDelta,
    ExecutionCaptureDeltaError,
    IntendedOrderCLV,
    RealisedFillCLV,
    SignalCLV,
    UnfilledOrder,
    UnfilledOrderError,
    UnfilledOutcome,
    realised_fill_clvs,
)

pytestmark = pytest.mark.spec("SPEC-095")

_REPO = Path(__file__).resolve().parents[3]


def _bsp(odds: Decimal) -> ClosingPrice:
    return ClosingPrice(benchmark=ClosingBenchmark.BSP, odds=odds)


def _wap(
    odds: Decimal, *, start: int = 90, end: int = 30
) -> ClosingPrice:
    return ClosingPrice(
        benchmark=ClosingBenchmark.PRE_SUSPENSION_WAP,
        odds=odds,
        window_start_seconds_before_suspension=start,
        window_end_seconds_before_suspension=end,
    )


# --- sign convention: hand-computed fixtures ------------------------------------------------


def test_clv_bps_hand_fixture_positive_when_taken_longer_than_close() -> None:
    # Taken 3.00 vs close 2.50: 1/2.50 - 1/3.00 = 0.4 - 0.333... = 0.0666... -> 666.67 bps.
    closing = _bsp(Decimal("2.5"))
    signal = SignalCLV(candidate_ref="race1-runner4", closing=closing, odds_at_signal=Decimal("3.0"))
    expected = (
        (Decimal(1) / Decimal("2.5")) - (Decimal(1) / Decimal("3.0"))
    ) * Decimal(10000)
    expected = expected.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    assert expected == Decimal("666.67")
    assert signal.clv_bps == expected
    assert signal.clv_bps == Decimal("666.67")
    assert signal.clv_bps > 0


def test_clv_bps_hand_fixture_negative_when_taken_shorter_than_close() -> None:
    # Taken 2.00 vs close 2.50: 1/2.50 - 1/2.00 = 0.4 - 0.5 = -0.1 -> -1000.00 bps exactly.
    closing = _bsp(Decimal("2.5"))
    intended = IntendedOrderCLV(order_ref="o-1", closing=closing, odds_intended=Decimal("2.0"))
    assert intended.clv_bps == Decimal("-1000.00")
    assert intended.clv_bps < 0


def test_clv_bps_zero_when_taken_equals_close() -> None:
    closing = _bsp(Decimal("2.5"))
    fill = RealisedFillCLV(
        order_ref="o-2", closing=closing, odds_matched=Decimal("2.5"), matched_stake_minor=500
    )
    assert fill.clv_bps == Decimal("0.00")


def test_odds_ratio_secondary_field_exact() -> None:
    closing = _bsp(Decimal("2.5"))
    signal = SignalCLV(candidate_ref="race1-runner4", closing=closing, odds_at_signal=Decimal("3.0"))
    assert signal.odds_ratio == Decimal("1.2")


# --- ClosingBenchmark: exactly two members ---------------------------------------------------


def test_closing_benchmark_has_exactly_two_members() -> None:
    assert {m.value for m in ClosingBenchmark} == {"BSP", "PRE_SUSPENSION_WAP"}
    assert len(ClosingBenchmark) == 2


# --- ClosingPrice: odds validation ------------------------------------------------------------


def test_closing_price_rejects_odds_not_greater_than_one() -> None:
    with pytest.raises(ClosingPriceError):
        _bsp(Decimal("1.0"))
    with pytest.raises(ClosingPriceError):
        _bsp(Decimal("0.5"))


def test_closing_price_rejects_float_odds() -> None:
    with pytest.raises(TypeError):
        ClosingPrice(benchmark=ClosingBenchmark.BSP, odds=2.5)  # type: ignore[arg-type]


# --- ClosingPrice: BSP carries no window ------------------------------------------------------


def test_bsp_rejects_a_window() -> None:
    with pytest.raises(ClosingPriceError):
        ClosingPrice(
            benchmark=ClosingBenchmark.BSP,
            odds=Decimal("2.5"),
            window_start_seconds_before_suspension=90,
            window_end_seconds_before_suspension=30,
        )
    with pytest.raises(ClosingPriceError):
        ClosingPrice(
            benchmark=ClosingBenchmark.BSP,
            odds=Decimal("2.5"),
            window_start_seconds_before_suspension=90,
        )


# --- ClosingPrice: PRE_SUSPENSION_WAP requires a well-formed window --------------------------


def test_wap_requires_both_window_fields() -> None:
    with pytest.raises(ClosingPriceError):
        ClosingPrice(benchmark=ClosingBenchmark.PRE_SUSPENSION_WAP, odds=Decimal("2.5"))
    with pytest.raises(ClosingPriceError):
        ClosingPrice(
            benchmark=ClosingBenchmark.PRE_SUSPENSION_WAP,
            odds=Decimal("2.5"),
            window_start_seconds_before_suspension=90,
        )
    with pytest.raises(ClosingPriceError):
        ClosingPrice(
            benchmark=ClosingBenchmark.PRE_SUSPENSION_WAP,
            odds=Decimal("2.5"),
            window_end_seconds_before_suspension=30,
        )


def test_wap_window_start_must_be_positive() -> None:
    with pytest.raises(ClosingPriceError):
        _wap(Decimal("2.5"), start=0, end=-10)


def test_wap_window_end_must_be_non_negative() -> None:
    with pytest.raises(ClosingPriceError):
        _wap(Decimal("2.5"), start=90, end=-1)


def test_wap_window_start_must_exceed_end() -> None:
    with pytest.raises(ClosingPriceError):
        _wap(Decimal("2.5"), start=30, end=30)
    with pytest.raises(ClosingPriceError):
        _wap(Decimal("2.5"), start=30, end=90)


def test_wap_window_valid_case_constructs() -> None:
    closing = _wap(Decimal("2.5"), start=90, end=30)
    assert closing.window_start_seconds_before_suspension == 90
    assert closing.window_end_seconds_before_suspension == 30


def test_wap_window_fields_reject_non_int() -> None:
    with pytest.raises(TypeError):
        ClosingPrice(
            benchmark=ClosingBenchmark.PRE_SUSPENSION_WAP,
            odds=Decimal("2.5"),
            window_start_seconds_before_suspension=90.0,  # type: ignore[arg-type]
            window_end_seconds_before_suspension=30,
        )


# --- RealisedFillCLV: unconstructable without a positive matched stake -----------------------


def test_realised_fill_clv_requires_positive_matched_stake() -> None:
    closing = _bsp(Decimal("2.5"))
    with pytest.raises(ClvError):
        RealisedFillCLV(
            order_ref="o-3", closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=0
        )
    with pytest.raises(ClvError):
        RealisedFillCLV(
            order_ref="o-3", closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=-500
        )


def test_realised_fill_clv_requires_int_stake_not_float() -> None:
    closing = _bsp(Decimal("2.5"))
    with pytest.raises(TypeError):
        RealisedFillCLV(
            order_ref="o-3", closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=500.0  # type: ignore[arg-type]
        )


def test_realised_fill_clv_constructs_with_positive_stake() -> None:
    closing = _bsp(Decimal("2.5"))
    fill = RealisedFillCLV(
        order_ref="o-3", closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=500
    )
    assert fill.matched_stake_minor == 500


# --- ExecutionCaptureDelta: same order_ref and same benchmark enforced ------------------------


def test_execution_policy_value_computes_realised_minus_intended() -> None:
    closing = _bsp(Decimal("2.5"))
    intended = IntendedOrderCLV(order_ref="o-4", closing=closing, odds_intended=Decimal("3.0"))
    realised = RealisedFillCLV(
        order_ref="o-4", closing=closing, odds_matched=Decimal("3.2"), matched_stake_minor=500
    )
    epv = ExecutionCaptureDelta(intended=intended, realised=realised)
    assert epv.value_bps == realised.clv_bps - intended.clv_bps
    assert epv.order_ref == "o-4"


def test_execution_policy_value_rejects_mismatched_order_ref() -> None:
    closing = _bsp(Decimal("2.5"))
    intended = IntendedOrderCLV(order_ref="o-5", closing=closing, odds_intended=Decimal("3.0"))
    realised = RealisedFillCLV(
        order_ref="o-6", closing=closing, odds_matched=Decimal("3.2"), matched_stake_minor=500
    )
    with pytest.raises(ExecutionCaptureDeltaError):
        ExecutionCaptureDelta(intended=intended, realised=realised)


def test_execution_policy_value_rejects_mismatched_benchmark_kind() -> None:
    # Same order, but intended evaluated against BSP and realised against WAP: refused —
    # the two benchmark families are never compared against each other.
    intended = IntendedOrderCLV(
        order_ref="o-7", closing=_bsp(Decimal("2.5")), odds_intended=Decimal("3.0")
    )
    realised = RealisedFillCLV(
        order_ref="o-7",
        closing=_wap(Decimal("2.6")),
        odds_matched=Decimal("3.2"),
        matched_stake_minor=500,
    )
    with pytest.raises(ExecutionCaptureDeltaError):
        ExecutionCaptureDelta(intended=intended, realised=realised)


def test_execution_policy_value_rejects_same_benchmark_kind_different_observation() -> None:
    # Same order, both BSP, but different odds observed: still refused — BSP for one race
    # cannot be silently paired against BSP from a materially different observation.
    intended = IntendedOrderCLV(
        order_ref="o-8", closing=_bsp(Decimal("2.5")), odds_intended=Decimal("3.0")
    )
    realised = RealisedFillCLV(
        order_ref="o-8",
        closing=_bsp(Decimal("2.6")),
        odds_matched=Decimal("3.2"),
        matched_stake_minor=500,
    )
    with pytest.raises(ExecutionCaptureDeltaError):
        ExecutionCaptureDelta(intended=intended, realised=realised)


def test_execution_policy_value_rejects_different_wap_windows() -> None:
    intended = IntendedOrderCLV(
        order_ref="o-9",
        closing=_wap(Decimal("2.5"), start=90, end=30),
        odds_intended=Decimal("3.0"),
    )
    realised = RealisedFillCLV(
        order_ref="o-9",
        closing=_wap(Decimal("2.5"), start=60, end=10),
        odds_matched=Decimal("3.2"),
        matched_stake_minor=500,
    )
    with pytest.raises(ExecutionCaptureDeltaError):
        ExecutionCaptureDelta(intended=intended, realised=realised)


# --- UnfilledOrder: the honest artifact -------------------------------------------------------


def test_unfilled_order_requires_nonempty_ref() -> None:
    with pytest.raises(UnfilledOrderError):
        UnfilledOrder(order_ref="", outcome=UnfilledOutcome.LAPSED)


@pytest.mark.parametrize("outcome", list(UnfilledOutcome))
def test_unfilled_order_constructs_for_every_outcome(outcome: UnfilledOutcome) -> None:
    order = UnfilledOrder(order_ref="o-10", outcome=outcome)
    assert order.outcome is outcome


def test_unfilled_outcome_has_no_catch_all_member() -> None:
    names = {m.name for m in UnfilledOutcome}
    assert names == {"LAPSED", "CANCELLED", "EXPIRED_UNMATCHED"}
    for forbidden in ("UNKNOWN", "OTHER", "HYPOTHETICAL"):
        assert forbidden not in names


# --- CLVBatch / realised_fill_clvs: unfilled orders preserved, never priced ------------------


def test_realised_fill_clvs_preserves_unfilled_with_honest_counts() -> None:
    closing = _bsp(Decimal("2.5"))
    fills = (
        RealisedFillCLV(
            order_ref="f-1", closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=200
        ),
        RealisedFillCLV(
            order_ref="f-2", closing=closing, odds_matched=Decimal("2.8"), matched_stake_minor=300
        ),
    )
    unfilled = (
        UnfilledOrder(order_ref="u-1", outcome=UnfilledOutcome.LAPSED),
        UnfilledOrder(order_ref="u-2", outcome=UnfilledOutcome.CANCELLED),
        UnfilledOrder(order_ref="u-3", outcome=UnfilledOutcome.EXPIRED_UNMATCHED),
    )
    batch = realised_fill_clvs(fills, unfilled)
    assert batch.realised == fills
    assert batch.unfilled == unfilled
    assert batch.filled_count == 2
    assert batch.unfilled_count == 3
    assert batch.total_count == 5


def test_realised_fill_clvs_empty_inputs_produce_zero_counts() -> None:
    batch = realised_fill_clvs((), ())
    assert batch.filled_count == 0
    assert batch.unfilled_count == 0
    assert batch.total_count == 0


def test_realised_fill_clvs_rejects_duplicate_order_ref_among_fills() -> None:
    closing = _bsp(Decimal("2.5"))
    fills = (
        RealisedFillCLV(
            order_ref="dup", closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=200
        ),
        RealisedFillCLV(
            order_ref="dup", closing=closing, odds_matched=Decimal("2.8"), matched_stake_minor=300
        ),
    )
    with pytest.raises(CLVBatchError):
        realised_fill_clvs(fills, ())


def test_realised_fill_clvs_rejects_duplicate_order_ref_among_unfilled() -> None:
    unfilled = (
        UnfilledOrder(order_ref="dup", outcome=UnfilledOutcome.LAPSED),
        UnfilledOrder(order_ref="dup", outcome=UnfilledOutcome.CANCELLED),
    )
    with pytest.raises(CLVBatchError):
        realised_fill_clvs((), unfilled)


def test_realised_fill_clvs_rejects_order_ref_in_both_fills_and_unfilled() -> None:
    closing = _bsp(Decimal("2.5"))
    fills = (
        RealisedFillCLV(
            order_ref="shared", closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=200
        ),
    )
    unfilled = (UnfilledOrder(order_ref="shared", outcome=UnfilledOutcome.LAPSED),)
    with pytest.raises(CLVBatchError):
        realised_fill_clvs(fills, unfilled)


def test_clv_batch_direct_construction_validates_counts() -> None:
    closing = _bsp(Decimal("2.5"))
    fill = RealisedFillCLV(
        order_ref="f-1", closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=200
    )
    with pytest.raises(CLVBatchError):
        CLVBatch(realised=(fill,), unfilled=(), filled_count=0, unfilled_count=0, total_count=0)
    with pytest.raises(CLVBatchError):
        CLVBatch(realised=(), unfilled=(), filled_count=0, unfilled_count=0, total_count=1)


# --- determinism: content_digest ---------------------------------------------------------------


def test_content_digest_deterministic_for_identical_values() -> None:
    closing_a = _bsp(Decimal("2.5"))
    closing_b = _bsp(Decimal("2.5"))
    assert closing_a.content_digest() == closing_b.content_digest()

    fill_a = RealisedFillCLV(
        order_ref="f-1", closing=closing_a, odds_matched=Decimal("3.0"), matched_stake_minor=200
    )
    fill_b = RealisedFillCLV(
        order_ref="f-1", closing=closing_b, odds_matched=Decimal("3.0"), matched_stake_minor=200
    )
    assert fill_a.content_digest() == fill_b.content_digest()


def test_content_digest_differs_for_different_values() -> None:
    closing = _bsp(Decimal("2.5"))
    fill_a = RealisedFillCLV(
        order_ref="f-1", closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=200
    )
    fill_b = RealisedFillCLV(
        order_ref="f-1", closing=closing, odds_matched=Decimal("3.0"), matched_stake_minor=201
    )
    assert fill_a.content_digest() != fill_b.content_digest()


# --- no hypothetical-price parameter anywhere (signature scan) -------------------------------


def test_no_public_callable_accepts_a_hypothetical_price_parameter() -> None:
    import l8_evidence.clv as module

    forbidden_substrings = ("hypothetical", "assumed_price", "estimated_price", "implied_taken")
    for name in module.__all__:
        obj = getattr(module, name)
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        try:
            sig = inspect.signature(obj)
        except (TypeError, ValueError):
            continue
        for param_name in sig.parameters:
            lowered = param_name.lower()
            assert not any(f in lowered for f in forbidden_substrings), (
                f"{name}'s parameter {param_name!r} looks like a hypothetical-price "
                "parameter; SPEC-095 forbids assigning hypothetical taken prices"
            )


def test_module_source_has_no_hypothetical_price_identifier() -> None:
    import l8_evidence.clv as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    for forbidden in ("hypothetical_price", "hypothetical_odds", "assumed_taken_price"):
        assert forbidden not in source


# --- CLV is not a training target: no target/label vocabulary, no l4_pricing import ----------


def test_no_public_name_uses_target_or_label_vocabulary() -> None:
    import l8_evidence.clv as module

    for name in module.__all__:
        lowered = name.lower()
        assert "target" not in lowered, f"{name!r} uses ML-target vocabulary"
        assert "label" not in lowered, f"{name!r} uses ML-label vocabulary"


@pytest.mark.parametrize(
    "forbidden",
    ["l4_pricing", "l5_decision", "l5b_risk", "l6_broker", "l7_settle"],
)
def test_clv_module_never_reaches_trading_or_pricing_state(forbidden: str) -> None:
    from tools.check_import_quarantine import find_violations

    violations = find_violations(_REPO, forbidden, ["l8_evidence.clv"])
    assert violations == [], (
        f"l8_evidence.clv must never reach {forbidden!r} — CLV is a diagnostic, never a "
        f"training target (SPEC-095):\n" + "\n".join(violations)
    )
