"""PERSONAL_TENNIS_ASSISTANT_V0 — assembly pipeline (STAGE3-0003 §7).

Assembles a validated manual snapshot into the deterministic V0 output: the market
probability (final) plus the separate, labelled F2-v1 diagnostic where an injected rating
lookup resolves both players. No network; no execution import; no LLM number.
"""
from __future__ import annotations

from typing import Callable

from assistant_v0 import f2_diagnostic as f2
from assistant_v0.manual_input import ManualMarketSnapshot
from assistant_v0.market_probability import assess_market
from assistant_v0.output import AssistantOutput, build_output
from assistant_v0.shadow_ledger import PreMatchRecord

# (tour, competitor_display_name) -> (rating, prior_match_count) or None if unresolved.
RatingLookup = Callable[[str, str], "tuple[float, int] | None"]


def _f2_for_match(snap: ManualMarketSnapshot,
                  rating_lookup: RatingLookup | None) -> f2.F2Diagnostic:
    if rating_lookup is None:
        return f2.unavailable(f2.MODEL_HISTORY_INSUFFICIENT)
    a = rating_lookup(snap.tour, snap.competitor_a)
    b = rating_lookup(snap.tour, snap.competitor_b)
    if a is None or b is None:
        return f2.unavailable(f2.IDENTITY_UNRESOLVED)
    return f2.f2_view_from_ratings(a[0], a[1], b[0], b[1])


def assemble(snap: ManualMarketSnapshot, *, reference_time_ms: int,
             rating_lookup: RatingLookup | None = None) -> AssistantOutput:
    """Manual snapshot -> deterministic V0 output. Market probability is final; F2 is a
    separate labelled diagnostic where both players resolve with sufficient history."""
    market = assess_market(snap, reference_time_ms=reference_time_ms)
    f2_view = _f2_for_match(snap, rating_lookup)
    return build_output(snap, market, f2_view)


def to_pre_match_record(out: AssistantOutput, *, record_id: str,
                        created_at_ms: int) -> PreMatchRecord:
    """Project a V0 output into an append-only pre-match ledger record (no outcome)."""
    return PreMatchRecord(
        record_id=record_id, snapshot_digest=out.data_digest, tour=out.tour,
        competitor_a=out.competitor_a, competitor_b=out.competitor_b,
        market_probability_a=out.market_probability_a,
        market_probability_b=out.market_probability_b,
        f2_probability_a=out.f2_probability_a, f2_probability_b=out.f2_probability_b,
        status=out.status.value, reason_codes=tuple(c.value for c in out.reason_codes),
        data_digest=out.data_digest, policy_digest=out.policy_digest,
        model_view_digest=out.model_view_digest, created_at_ms=created_at_ms,
    )
