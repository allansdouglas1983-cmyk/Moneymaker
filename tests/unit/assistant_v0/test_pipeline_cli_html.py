"""STAGE3-0003 §7/§9/§11/§12 — V0 pipeline + CLI + static HTML (red tests first).

The pipeline assembles a manual snapshot into the deterministic output (market probability
final; F2 diagnostic separate where a rating lookup resolves both players). The CLI produces
deterministic JSON with no network. The static HTML report renders from the JSON, carries
the RESEARCH / SHADOW ONLY banner, may show the outcome-blind cross-market AUDIT view
labelled "NOT USED IN THE PROBABILITY", and contains no bet/promotional language.
"""
from __future__ import annotations

from pathlib import Path

import json
from decimal import Decimal

from assistant_v0 import html_report as H
from assistant_v0 import manual_input as MI
from assistant_v0 import pipeline as P
from assistant_v0 import status as S


def _snap(**over: object) -> MI.ManualMarketSnapshot:
    base: dict[str, object] = dict(
        competitor_a="A Player", competitor_b="B Player",
        competitor_a_id=None, competitor_b_id=None,
        tour="ATP", scheduled_start_ms=2000, input_timestamp_ms=1000,
        source="MANUAL_BETFAIR_UI",
        back_a=Decimal("1.90"), back_a_size=Decimal("50"),
        lay_a=Decimal("1.95"), lay_a_size=Decimal("40"),
        back_b=Decimal("2.04"), back_b_size=Decimal("30"),
        lay_b=Decimal("2.12"), lay_b_size=Decimal("20"),
        market_status="OPEN", in_play=False, market_id="1.234", event_id="E1",
    )
    base.update(over)
    return MI.ManualMarketSnapshot(**base)  # type: ignore[arg-type]


def test_assemble_market_only_when_no_rating_lookup() -> None:
    out = P.assemble(_snap(), reference_time_ms=1000)
    assert out.status is S.AssistantStatus.MARKET_ONLY
    assert out.final_probability_source == "MARKET"
    assert out.f2_available is False


def test_assemble_model_view_when_ratings_resolve() -> None:
    def lookup(_tour: str, name: str) -> tuple[float, int] | None:
        return {"A Player": (1600.0, 40), "B Player": (1500.0, 30)}.get(name)
    out = P.assemble(_snap(), reference_time_ms=1000, rating_lookup=lookup)
    assert out.status is S.AssistantStatus.MODEL_VIEW_ONLY
    assert out.f2_available is True
    assert out.final_probability_source == "MARKET"          # F2 never final
    assert out.final_probability_a == out.market_probability_a


def test_assemble_identity_unresolved_keeps_market_only() -> None:
    def lookup(_tour: str, _name: str) -> tuple[float, int] | None:
        return None  # neither player resolves
    out = P.assemble(_snap(), reference_time_ms=1000, rating_lookup=lookup)
    assert out.f2_available is False
    assert out.status is S.AssistantStatus.MARKET_ONLY


def test_pipeline_to_pre_match_record_has_no_outcome() -> None:
    out = P.assemble(_snap(), reference_time_ms=1000)
    rec = P.to_pre_match_record(out, record_id="r1", created_at_ms=1000)
    assert rec.market_probability_a == out.market_probability_a
    assert not hasattr(rec, "winner")


def test_cli_produces_deterministic_json(tmp_path: Path) -> None:
    from assistant_v0 import cli
    snap_json = {
        "competitor_a": "A Player", "competitor_b": "B Player",
        "competitor_a_id": None, "competitor_b_id": None, "tour": "ATP",
        "scheduled_start_ms": 2000, "input_timestamp_ms": 1000, "source": "MANUAL_BETFAIR_UI",
        "back_a": "1.90", "back_a_size": "50", "lay_a": "1.95", "lay_a_size": "40",
        "back_b": "2.04", "back_b_size": "30", "lay_b": "2.12", "lay_b_size": "20",
        "market_status": "OPEN", "in_play": False, "market_id": "1.234", "event_id": "E1",
    }
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(snap_json))
    out1 = cli.run_snapshot_file(str(p), reference_time_ms=1000)
    out2 = cli.run_snapshot_file(str(p), reference_time_ms=1000)
    assert out1 == out2
    parsed = json.loads(out1)
    assert parsed["final_probability_source"] == "MARKET"
    assert parsed["status"] == "MARKET_ONLY"


def test_html_report_has_banner_and_no_bet_language() -> None:
    out = P.assemble(_snap(), reference_time_ms=1000)
    html = H.render_html(out.to_dict())
    assert "RESEARCH / SHADOW ONLY" in html
    assert "NO BET RECOMMENDATION" in html
    for promo in ("safe bet", "value bet", "guaranteed", "will win", "strong bet", "must back"):
        assert promo.lower() not in html.lower()


def test_html_report_xmarket_audit_view_is_labelled_not_used_in_probability() -> None:
    out = P.assemble(_snap(), reference_time_ms=1000)
    xmarket = {"total_games_present": True, "game_handicap_present": True,
               "synchronization": "USABLE", "quote_age_seconds": 42.0, "two_sided": True,
               "min_spread_ticks": 3, "redundancy_status": "INDEPENDENCE_UNRESOLVED",
               "settlement_status": "UNRESOLVED"}
    html = H.render_html(out.to_dict(), xmarket_view=xmarket)
    assert "RESEARCH AUDIT — NOT USED IN THE PROBABILITY" in html


def test_html_report_is_deterministic() -> None:
    out = P.assemble(_snap(), reference_time_ms=1000)
    assert H.render_html(out.to_dict()) == H.render_html(out.to_dict())
