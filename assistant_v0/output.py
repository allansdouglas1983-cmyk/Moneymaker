"""PERSONAL_TENNIS_ASSISTANT_V0 — output contract (STAGE3-0003 §7).

The final V0 decision probability is the MARKET probability, always. The F2-v1 diagnostic is
carried separately and labelled; it never becomes the final probability. The output contains
NO edge / expected-value / stake / tip / recommended-side / profit field — those are not
representable. Fair odds shown are 1/market-probability (labelled). Serialization is
deterministic. No LLM produces any number here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from assistant_v0.f2_diagnostic import F2Diagnostic
from assistant_v0.manual_input import ManualMarketSnapshot
from assistant_v0.market_probability import MarketResult
from assistant_v0.reason_codes import ReasonCode
from assistant_v0.status import (
    ECONOMIC_POSTURE,
    STATUS_REGISTRY_VERSION,
    AssistantStatus,
    data_status,
)

FINAL_PROBABILITY_SOURCE = "MARKET"
INFO_PRICE_METHOD = "info-price-v2"
# display band for labelling model-vs-market agreement (a display label, not a policy)
AGREEMENT_BAND = 0.05


@dataclass(frozen=True)
class AssistantOutput:
    """The deterministic V0 output for one manual snapshot. Outcome-blind and bet-free."""

    # match / provenance
    competitor_a: str
    competitor_b: str
    tour: str
    market_id: str | None
    event_id: str | None
    scheduled_start_ms: int
    market_timestamp_ms: int
    quote_age_ms: int
    # market view (the final probability)
    final_probability_source: str
    final_probability_a: float | None
    final_probability_b: float | None
    market_probability_a: float | None
    market_probability_b: float | None
    market_fair_odds_a: float | None
    market_fair_odds_b: float | None
    best_back_a: str
    best_lay_a: str
    best_back_b: str
    best_lay_b: str
    market_prob_interval_a: tuple[float, float] | None
    market_prob_interval_b: tuple[float, float] | None
    info_price_method: str
    # F2-v1 diagnostic (separate, labelled, never final)
    f2_available: bool
    f2_probability_a: float | None
    f2_probability_b: float | None
    f2_label: str | None
    f2_history_count_a: int | None
    f2_history_count_b: int | None
    model_market_disagreement_a: float | None
    model_market_disagreement_b: float | None
    # status / reasons / provenance
    status: AssistantStatus
    economic_posture: AssistantStatus
    reason_codes: tuple[ReasonCode, ...]
    data_digest: str
    model_view_digest: str
    policy_digest: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["economic_posture"] = self.economic_posture.value
        d["reason_codes"] = [c.value for c in self.reason_codes]
        d["market_prob_interval_a"] = list(self.market_prob_interval_a) if self.market_prob_interval_a else None
        d["market_prob_interval_b"] = list(self.market_prob_interval_b) if self.market_prob_interval_b else None
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def _policy_digest() -> str:
    blob = json.dumps({
        "status_registry": STATUS_REGISTRY_VERSION,
        "info_price_method": INFO_PRICE_METHOD,
        "final_probability_source": FINAL_PROBABILITY_SOURCE,
        "agreement_band": AGREEMENT_BAND,
    }, sort_keys=True)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def _model_view_digest(f2: F2Diagnostic) -> str:
    blob = json.dumps({
        "available": f2.available, "p_a": f2.p_a, "label": f2.label,
        "hist_a": f2.history_count_a, "hist_b": f2.history_count_b, "reason": f2.reason,
    }, sort_keys=True)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def build_output(snap: ManualMarketSnapshot, market: MarketResult, f2: F2Diagnostic, *,
                 reference_time_ms: int) -> AssistantOutput:
    """Assemble the deterministic V0 output. Market probability is final; F2 is a labelled
    diagnostic; no bet/edge/EV/stake/tip field exists."""
    status = data_status(input_valid=True, market_valid=market.available,
                         f2_available=f2.available)

    reasons: list[ReasonCode] = list(market.reason_codes)
    if f2.available:
        reasons.append(ReasonCode.MODEL_HISTORY_AVAILABLE)
        reasons.append(ReasonCode.MODEL_NOT_MARKET_PROVEN)
    else:
        reasons.append(ReasonCode.MODEL_HISTORY_INSUFFICIENT)

    dis_a: float | None = None
    dis_b: float | None = None
    if market.available and f2.available and market.p_a is not None and f2.p_a is not None:
        dis_a = f2.p_a - market.p_a
        dis_b = (f2.p_b - market.p_b) if (f2.p_b is not None and market.p_b is not None) else None
        reasons.append(ReasonCode.MODEL_MARKET_AGREEMENT if abs(dis_a) < AGREEMENT_BAND
                       else ReasonCode.MODEL_MARKET_DISAGREEMENT)

    # V0 is always research-only, never a bet
    reasons.append(ReasonCode.RESEARCH_ONLY_NO_BET)

    fair_a = (1.0 / market.p_a) if (market.available and market.p_a) else None
    fair_b = (1.0 / market.p_b) if (market.available and market.p_b) else None

    return AssistantOutput(
        competitor_a=snap.competitor_a, competitor_b=snap.competitor_b, tour=snap.tour,
        market_id=snap.market_id, event_id=snap.event_id,
        scheduled_start_ms=snap.scheduled_start_ms, market_timestamp_ms=snap.input_timestamp_ms,
        quote_age_ms=market.quote_age_ms,
        final_probability_source=FINAL_PROBABILITY_SOURCE,
        final_probability_a=market.p_a, final_probability_b=market.p_b,
        market_probability_a=market.p_a, market_probability_b=market.p_b,
        market_fair_odds_a=fair_a, market_fair_odds_b=fair_b,
        best_back_a=str(market.best_back_a), best_lay_a=str(market.best_lay_a),
        best_back_b=str(market.best_back_b), best_lay_b=str(market.best_lay_b),
        market_prob_interval_a=market.p_a_interval, market_prob_interval_b=market.p_b_interval,
        info_price_method=INFO_PRICE_METHOD,
        f2_available=f2.available, f2_probability_a=f2.p_a, f2_probability_b=f2.p_b,
        f2_label=f2.label, f2_history_count_a=f2.history_count_a,
        f2_history_count_b=f2.history_count_b,
        model_market_disagreement_a=dis_a, model_market_disagreement_b=dis_b,
        status=status, economic_posture=ECONOMIC_POSTURE, reason_codes=tuple(reasons),
        data_digest=snap.content_digest(), model_view_digest=_model_view_digest(f2),
        policy_digest=_policy_digest(),
    )
