"""PERSONAL_TENNIS_ASSISTANT_V0 — market probability (STAGE3-0003 §4/§7).

The market probability is the ONLY final V0 decision probability. It is computed by the
governed info-price-v2 method (``sport_tennis.market_yardstick.market_probabilities_from_book``
— implied midpoint of best back/lay, normalised) over the two-sided Match-Odds book. A
suspended, in-play, or crossed book is UNAVAILABLE and yields no probability — never a
fabricated number. No LLM produces any value here.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from assistant_v0.manual_input import ManualMarketSnapshot
from assistant_v0.reason_codes import ReasonCode
from price_contracts.ladder import index_of
from sport_tennis.market_yardstick import BookLevel, market_probabilities_from_book

_SEL_A = 0
_SEL_B = 1


@dataclass(frozen=True)
class MarketResult:
    """Outcome-blind market assessment at the snapshot (final probability = market)."""

    available: bool
    p_a: float | None
    p_b: float | None
    p_a_interval: tuple[float, float] | None      # (implied-from-lay, implied-from-back)
    p_b_interval: tuple[float, float] | None
    best_back_a: Decimal
    best_lay_a: Decimal
    best_back_b: Decimal
    best_lay_b: Decimal
    quote_age_ms: int
    reason_codes: tuple[ReasonCode, ...]


def _crossed(back: Decimal, lay: Decimal) -> bool:
    # a normal book has best back price < best lay price; back >= lay is crossed/locked
    return back >= lay


def assess_market(snap: ManualMarketSnapshot, *, reference_time_ms: int) -> MarketResult:
    """Assess the manual snapshot's Match-Odds book and, when usable, compute the governed
    market probability per player."""
    quote_age = reference_time_ms - snap.input_timestamp_ms
    reasons: list[ReasonCode] = []
    unavailable = MarketResult(
        available=False, p_a=None, p_b=None, p_a_interval=None, p_b_interval=None,
        best_back_a=snap.back_a, best_lay_a=snap.lay_a,
        best_back_b=snap.back_b, best_lay_b=snap.lay_b,
        quote_age_ms=quote_age, reason_codes=(),
    )

    if snap.market_status != "OPEN":
        return _with(unavailable, (ReasonCode.MARKET_SUSPENDED, ReasonCode.MARKET_PRICE_UNAVAILABLE))
    if snap.in_play:
        return _with(unavailable, (ReasonCode.MARKET_IN_PLAY, ReasonCode.MARKET_PRICE_UNAVAILABLE))
    if _crossed(snap.back_a, snap.lay_a) or _crossed(snap.back_b, snap.lay_b):
        return _with(unavailable, (ReasonCode.CROSSED_BOOK, ReasonCode.MARKET_PRICE_UNAVAILABLE))

    book = {
        _SEL_A: BookLevel(back_tick=index_of(snap.back_a), lay_tick=index_of(snap.lay_a)),
        _SEL_B: BookLevel(back_tick=index_of(snap.back_b), lay_tick=index_of(snap.lay_b)),
    }
    probs = market_probabilities_from_book(book)
    p_a, p_b = probs[_SEL_A], probs[_SEL_B]
    reasons.append(ReasonCode.MARKET_PRICE_AVAILABLE)
    return MarketResult(
        available=True, p_a=p_a, p_b=p_b,
        p_a_interval=(1.0 / float(snap.lay_a), 1.0 / float(snap.back_a)),
        p_b_interval=(1.0 / float(snap.lay_b), 1.0 / float(snap.back_b)),
        best_back_a=snap.back_a, best_lay_a=snap.lay_a,
        best_back_b=snap.back_b, best_lay_b=snap.lay_b,
        quote_age_ms=quote_age, reason_codes=tuple(reasons),
    )


def _with(base: MarketResult, reasons: tuple[ReasonCode, ...]) -> MarketResult:
    return MarketResult(
        available=base.available, p_a=base.p_a, p_b=base.p_b,
        p_a_interval=base.p_a_interval, p_b_interval=base.p_b_interval,
        best_back_a=base.best_back_a, best_lay_a=base.best_lay_a,
        best_back_b=base.best_back_b, best_lay_b=base.best_lay_b,
        quote_age_ms=base.quote_age_ms, reason_codes=reasons,
    )
