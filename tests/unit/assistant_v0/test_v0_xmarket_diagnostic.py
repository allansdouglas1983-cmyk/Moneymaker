"""STAGE3-0004 §13 — V0 cross-market research DIAGNOSTIC display (red tests first).

V0 may display the outcome-blind cross-market research diagnostic (availability, quote age,
synchronization status, market-type presence, settlement-semantics status, origin-unresolved
warning, research-only summary) under the banner "CROSS-MARKET RESEARCH DIAGNOSTIC — NOT
USED IN THE FINAL PROBABILITY". It may NOT display latent serve strength, inferred total-games
expectation, a coherence edge, a cross-market tip, or a probability adjustment. The final V0
probability remains market-only and is unaffected by the diagnostic.
"""
from __future__ import annotations

from decimal import Decimal

from assistant_v0 import html_report as H
from assistant_v0 import manual_input as MI
from assistant_v0 import pipeline as P


def _snap() -> MI.ManualMarketSnapshot:
    return MI.ManualMarketSnapshot(
        competitor_a="A", competitor_b="B", competitor_a_id=None, competitor_b_id=None,
        tour="ATP", scheduled_start_ms=2000, input_timestamp_ms=1000, source="MANUAL_BETFAIR_UI",
        back_a=Decimal("1.90"), back_a_size=Decimal("50"), lay_a=Decimal("1.95"), lay_a_size=Decimal("40"),
        back_b=Decimal("2.04"), back_b_size=Decimal("30"), lay_b=Decimal("2.12"), lay_b_size=Decimal("20"),
        market_status="OPEN", in_play=False, market_id="1.234", event_id="E1")


def _diag() -> dict[str, object]:
    return {
        "derivative_availability": "TOTAL_GAMES_PRESENT+GAME_HANDICAP_PRESENT",
        "quote_age_seconds": 42.0,
        "synchronization_status": "USABLE",
        "market_type_presence": ["COMBINED_TOTAL", "HANDICAP"],
        "settlement_semantics_status": "VERIFIED_CONTRACTUALLY_DIFFERENT_BUT_USABLE_WITH_EXCLUSIONS",
        "origin_unresolved_warning": "ORIGIN_UNRESOLVED — derivative order origin is unobservable",
        "research_only_summary": "coherence layer not implemented; blocked by EXT-XMARKET-003",
    }


def test_diagnostic_banner_present() -> None:
    html = H.render_html(P.assemble(_snap(), reference_time_ms=1000).to_dict(),
                         cross_market_diagnostic=_diag())
    assert "CROSS-MARKET RESEARCH DIAGNOSTIC — NOT USED IN THE FINAL PROBABILITY" in html


def test_diagnostic_does_not_show_latent_coherence_or_tip() -> None:
    html = H.render_html(P.assemble(_snap(), reference_time_ms=1000).to_dict(),
                         cross_market_diagnostic=_diag()).lower()
    for forbidden in ("serve strength", "latent", "coherence edge", "coherence score",
                      "cross-market tip", "probability adjustment", "expected total games",
                      "inferred total"):
        assert forbidden not in html


def test_final_probability_unaffected_by_diagnostic() -> None:
    out = P.assemble(_snap(), reference_time_ms=1000)
    d = out.to_dict()
    # rendering the diagnostic does not change the output object or its final probability
    assert d["final_probability_source"] == "MARKET"
    assert d["final_probability_a"] == d["market_probability_a"]


def test_diagnostic_is_optional_and_absent_by_default() -> None:
    html = H.render_html(P.assemble(_snap(), reference_time_ms=1000).to_dict())
    assert "CROSS-MARKET RESEARCH DIAGNOSTIC" not in html


def test_diagnostic_render_is_deterministic() -> None:
    d = P.assemble(_snap(), reference_time_ms=1000).to_dict()
    assert H.render_html(d, cross_market_diagnostic=_diag()) == H.render_html(d, cross_market_diagnostic=_diag())
