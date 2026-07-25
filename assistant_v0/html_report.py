"""PERSONAL_TENNIS_ASSISTANT_V0 — static local HTML report (STAGE3-0003 §9B/§11).

Renders a deterministic, self-contained static HTML page from the V0 output dict. No server,
no accounts, no billing, no API credentials, no network. Carries a large RESEARCH / SHADOW
ONLY — NO BET RECOMMENDATION banner. May show the outcome-blind cross-market AUDIT view,
explicitly labelled "RESEARCH AUDIT — NOT USED IN THE PROBABILITY". No bet/promotional
language; the market probability is the only final probability; F2 is a labelled diagnostic.
"""
from __future__ import annotations

import html
from typing import Any

BANNER = "RESEARCH / SHADOW ONLY — NO BET RECOMMENDATION"
XMARKET_LABEL = "RESEARCH AUDIT — NOT USED IN THE PROBABILITY"
CROSS_MARKET_DIAGNOSTIC_BANNER = "CROSS-MARKET RESEARCH DIAGNOSTIC — NOT USED IN THE FINAL PROBABILITY"


def _esc(v: object) -> str:
    return html.escape("" if v is None else str(v))


def _rows(pairs: list[tuple[str, object]]) -> str:
    return "".join(f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>" for k, v in pairs)


def render_html(output: dict[str, Any], *, xmarket_view: dict[str, Any] | None = None,
                cross_market_diagnostic: dict[str, Any] | None = None) -> str:
    """Return a deterministic static HTML report for one V0 output. The optional cross-market
    research diagnostic (STAGE3-0004 §13) is DISPLAY-ONLY under its own banner and never
    affects the final (market-only) probability."""
    match = _rows([
        ("Competitor A", output.get("competitor_a")),
        ("Competitor B", output.get("competitor_b")),
        ("Tour", output.get("tour")),
        ("Market ID", output.get("market_id")),
        ("Event ID", output.get("event_id")),
        ("Scheduled start (ms)", output.get("scheduled_start_ms")),
        ("Market timestamp (ms)", output.get("market_timestamp_ms")),
        ("Quote age (ms)", output.get("quote_age_ms")),
    ])
    market = _rows([
        ("Final probability source", output.get("final_probability_source")),
        ("Market probability A", output.get("market_probability_a")),
        ("Market probability B", output.get("market_probability_b")),
        ("Market fair odds A", output.get("market_fair_odds_a")),
        ("Market fair odds B", output.get("market_fair_odds_b")),
        ("Best back / lay A", f"{output.get('best_back_a')} / {output.get('best_lay_a')}"),
        ("Best back / lay B", f"{output.get('best_back_b')} / {output.get('best_lay_b')}"),
        ("Implied interval A", output.get("market_prob_interval_a")),
        ("Implied interval B", output.get("market_prob_interval_b")),
        ("Info-price method", output.get("info_price_method")),
    ])
    f2 = _rows([
        ("F2 available", output.get("f2_available")),
        ("F2 label", output.get("f2_label")),
        ("F2 probability A", output.get("f2_probability_a")),
        ("F2 probability B", output.get("f2_probability_b")),
        ("F2 history A / B", f"{output.get('f2_history_count_a')} / {output.get('f2_history_count_b')}"),
        ("Model−market disagreement A", output.get("model_market_disagreement_a")),
    ])
    diagnostics = _rows([
        ("Status", output.get("status")),
        ("Economic posture", output.get("economic_posture")),
        ("Reason codes", ", ".join(output.get("reason_codes", []))),
    ])
    provenance = _rows([
        ("Data digest", output.get("data_digest")),
        ("Model-view digest", output.get("model_view_digest")),
        ("Policy digest", output.get("policy_digest")),
    ])

    diagnostic_section = ""
    if cross_market_diagnostic is not None:
        drows = _rows([(k, v) for k, v in sorted(cross_market_diagnostic.items())])
        diagnostic_section = (
            f'<section class="xmarket"><h2>Cross-market research diagnostic</h2>'
            f'<p class="label">{_esc(CROSS_MARKET_DIAGNOSTIC_BANNER)}</p>'
            f'<table>{drows}</table></section>'
        )

    xmarket_section = ""
    if xmarket_view is not None:
        xrows = _rows([(k, v) for k, v in sorted(xmarket_view.items())])
        xmarket_section = (
            f'<section class="xmarket"><h2>Cross-market audit view</h2>'
            f'<p class="label">{_esc(XMARKET_LABEL)}</p><table>{xrows}</table></section>'
        )

    style = (
        "body{font-family:sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem}"
        ".banner{background:#7a1f1f;color:#fff;font-weight:bold;text-align:center;"
        "padding:1rem;border-radius:6px;letter-spacing:.03em}"
        "table{border-collapse:collapse;width:100%;margin:.5rem 0 1.5rem}"
        "th,td{border:1px solid #ccc;padding:.35rem .6rem;text-align:left;font-size:.95rem}"
        "th{background:#f4f4f4;width:42%}.label{color:#7a1f1f;font-weight:bold}"
        "h2{margin-top:1.5rem;font-size:1.05rem}"
    )
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>Personal Tennis Assistant V0 — research/shadow only</title>"
        f"<style>{style}</style></head><body>"
        f'<div class="banner">{_esc(BANNER)}</div>'
        f"<section><h2>Match</h2><table>{match}</table></section>"
        f"<section><h2>Market probability (final)</h2><table>{market}</table></section>"
        f"<section><h2>F2-v1 diagnostic (separate — not market-proven)</h2><table>{f2}</table></section>"
        f"<section><h2>Status &amp; reasons</h2><table>{diagnostics}</table></section>"
        f"{diagnostic_section}"
        f"{xmarket_section}"
        f"<section><h2>Provenance</h2><table>{provenance}</table></section>"
        "</body></html>"
    )
