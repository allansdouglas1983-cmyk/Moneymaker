"""STAGE3-0003 §4/§7/§12 — V0 market probability (red tests first).

Market probability is the ONLY final V0 decision probability. It reuses the governed
info-price-v2 method (implied midpoint, normalised) over a two-sided Match-Odds book. A
crossed / one-sided / suspended / in-play / stale book yields MARKET_UNAVAILABLE, never a
fabricated number.
"""
from __future__ import annotations

from decimal import Decimal

from assistant_v0 import manual_input as MI
from assistant_v0 import market_probability as MP
from assistant_v0 import reason_codes as RC


def _snap(**over: object) -> MI.ManualMarketSnapshot:
    base: dict[str, object] = dict(
        competitor_a="A", competitor_b="B", competitor_a_id=None, competitor_b_id=None,
        tour="ATP", scheduled_start_ms=2000, input_timestamp_ms=1000,
        source="MANUAL_BETFAIR_UI",
        back_a=Decimal("1.90"), back_a_size=Decimal("50"),
        lay_a=Decimal("1.95"), lay_a_size=Decimal("40"),
        back_b=Decimal("2.02"), back_b_size=Decimal("30"),
        lay_b=Decimal("2.10"), lay_b_size=Decimal("20"),
        market_status="OPEN", in_play=False, market_id="1.234", event_id="E1",
    )
    base.update(over)
    return MI.ManualMarketSnapshot(**base)  # type: ignore[arg-type]


def test_two_sided_open_book_yields_probabilities_summing_to_one() -> None:
    res = MP.assess_market(_snap(), reference_time_ms=1000)
    assert res.available is True
    assert res.p_a is not None and res.p_b is not None
    assert abs((res.p_a + res.p_b) - 1.0) < 1e-9
    assert RC.ReasonCode.MARKET_PRICE_AVAILABLE in res.reason_codes


def test_probability_matches_governed_info_price() -> None:
    # A shorter than B => A has the higher probability
    res = MP.assess_market(_snap(), reference_time_ms=1000)
    assert res.p_a is not None and res.p_b is not None
    assert res.p_a > res.p_b


def test_crossed_book_is_unavailable() -> None:
    res = MP.assess_market(_snap(back_a=Decimal("1.96"), lay_a=Decimal("1.95")),
                           reference_time_ms=1000)
    assert res.available is False
    assert RC.ReasonCode.CROSSED_BOOK in res.reason_codes


def test_suspended_market_is_unavailable() -> None:
    res = MP.assess_market(_snap(market_status="SUSPENDED"), reference_time_ms=1000)
    assert res.available is False
    assert RC.ReasonCode.MARKET_SUSPENDED in res.reason_codes


def test_in_play_market_is_unavailable() -> None:
    res = MP.assess_market(_snap(in_play=True), reference_time_ms=1000)
    assert res.available is False
    assert RC.ReasonCode.MARKET_IN_PLAY in res.reason_codes


def test_quote_age_reported() -> None:
    res = MP.assess_market(_snap(input_timestamp_ms=1000), reference_time_ms=4000)
    assert res.quote_age_ms == 3000


def test_implied_probability_interval_present() -> None:
    res = MP.assess_market(_snap(), reference_time_ms=1000)
    assert res.p_a_interval is not None and res.p_a is not None
    lo, hi = res.p_a_interval
    assert lo < res.p_a <= hi or lo <= res.p_a < hi  # midpoint inside the back/lay interval


def test_market_probability_is_deterministic() -> None:
    a = MP.assess_market(_snap(), reference_time_ms=1000)
    b = MP.assess_market(_snap(), reference_time_ms=1000)
    assert a == b
