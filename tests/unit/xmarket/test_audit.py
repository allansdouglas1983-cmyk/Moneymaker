"""STAGE3-0002 §9-§16 — audit orchestrator + audit-only data contract (red tests first).

Ties catalogue + F0 anchor + reconstruction into a per-MO-market MarketAuditRecord that
carries NO outcome field (§16), and aggregates the feasibility observables. Hermetic:
synthetic messages + catalogue; no corpus, no outcome read.
"""
from __future__ import annotations

from typing import Any

from research.xmarket import audit as A
from research.xmarket.linkage import MarketRef, build_catalogue, mo_event_index


# ------------------------------------------------------------------------- fixtures
def _md(mid: str, pt: int, mtype: str, event: str = "E1", status: str = "OPEN",
        in_play: bool = False, mtime: int = 2000) -> dict[str, Any]:
    return {"pt": pt, "mc": [{"id": mid, "marketDefinition": {
        "marketType": mtype, "eventId": event, "status": status, "inPlay": in_play,
        "marketTime": mtime, "crossMatching": False, "numberOfActiveRunners": 110}}]}


def _rc(mid: str, pt: int, sel: int, hc: float, *, bb: tuple[float, float] | None = None,
        bl: tuple[float, float] | None = None, tv: float = 0.0) -> dict[str, Any]:
    ch: dict[str, Any] = {"id": sel, "hc": hc, "ltp": 0.0, "tv": tv}
    if bb is not None:
        ch["batb"] = [[0, bb[0], bb[1]]]
    if bl is not None:
        ch["batl"] = [[0, bl[0], bl[1]]]
    return {"pt": pt, "mc": [{"id": mid, "rc": [ch]}]}


def _two_sided_tg(mid: str, event: str = "E1") -> list[dict[str, Any]]:
    return [
        _md(mid, 100, "COMBINED_TOTAL", event),
        _rc(mid, 200, 111, 20.5, bb=(1.90, 50.0), bl=(1.95, 40.0), tv=500.0),
        _rc(mid, 300, 222, 20.5, bb=(2.05, 30.0), bl=(2.10, 20.0), tv=400.0),
    ]


def _two_sided_gh(mid: str, event: str = "E1") -> list[dict[str, Any]]:
    return [
        _md(mid, 100, "HANDICAP", event),
        _rc(mid, 250, 333, -4.5, bb=(1.80, 25.0), bl=(1.85, 20.0), tv=300.0),
        _rc(mid, 250, 444, 4.5, bb=(2.10, 15.0), bl=(2.20, 10.0), tv=250.0),
    ]


def _catalogue() -> dict[str, MarketRef]:
    return build_catalogue([
        MarketRef("1.mo", "E1", "MATCH_ODDS", 2000),
        MarketRef("1.tg", "E1", "COMBINED_TOTAL", 2000),
        MarketRef("1.gh", "E1", "HANDICAP", 2000),
    ])


def _messages() -> dict[str, list[dict[str, Any]]]:
    return {"1.tg": _two_sided_tg("1.tg"), "1.gh": _two_sided_gh("1.gh")}


def _audit_one(cohort: str = "STRICT", tour: str = "ATP",
               cutoff_anchor: int = 1000) -> A.MarketAuditRecord:
    cat = _catalogue()
    idx = mo_event_index(cat, {"1.mo"})
    msgs = _messages()
    return A.audit_one_market(
        mo_market_id="1.mo", commit_pt_ms=cutoff_anchor, cohort=cohort, tour=tour,
        calendar_day="2026-06-03", catalogue=cat, mo_index=idx,
        message_provider=lambda m: msgs.get(m, []),
    )


# ------------------------------------------------------------- data-contract (§16)
def test_record_has_no_outcome_field() -> None:
    rec = _audit_one()
    banned = {"winner", "result", "settled", "settled_time", "pnl", "profit", "loss",
              "outcome", "won", "runner_result", "bsp", "close", "closing", "roi", "clv", "ev"}
    seen = {f.name.lower() for f in type(rec).__dataclass_fields__.values()}
    for sub in (rec.total_games, rec.game_handicap):
        if sub is not None:
            seen |= {f.name.lower() for f in type(sub).__dataclass_fields__.values()}
    assert not (seen & banned), f"outcome-shaped field present: {seen & banned}"


def test_clean_pair_is_usable_within_cutoff() -> None:
    rec = _audit_one()
    assert rec.total_games is not None and rec.total_games.exclusion_reason is None
    assert rec.game_handicap is not None and rec.game_handicap.exclusion_reason is None
    assert A.derivative_usable(rec.total_games, cutoff_s=15)
    assert A.record_has_identifying(rec, cutoff_s=15)


def test_quote_age_cutoff_excludes_stale_book() -> None:
    rec = _audit_one(cutoff_anchor=1_000_000)
    assert rec.total_games is not None and rec.total_games.exclusion_reason is None
    assert not A.derivative_usable(rec.total_games, cutoff_s=15)
    assert not A.record_has_identifying(rec, cutoff_s=15)


# ---------------------------------------------------------------- aggregation (§9)
def _sample_records() -> list[A.MarketAuditRecord]:
    return [
        _audit_one(cohort="STRICT", tour="ATP"),
        _audit_one(cohort="STRICT", tour="WTA"),
        _audit_one(cohort="PRIMARY_ONLY_TIER", tour="ATP"),
    ]


def test_n_primary_identifying_by_cutoff_cohort_tour() -> None:
    recs = _sample_records()
    table = A.n_primary_identifying(recs, cutoffs_s=[15, 30])
    assert table[15]["TOTAL"] == 3
    assert table[15]["STRICT"] == 2
    assert table[15]["ATP"] == 2
    assert table[30]["TOTAL"] == 3


def test_funnel_counts_every_refusal_reason() -> None:
    cat = build_catalogue([
        MarketRef("1.mo", "E1", "MATCH_ODDS", 2000),
        MarketRef("1.tg", "E1", "COMBINED_TOTAL", 2000),
    ])
    idx = mo_event_index(cat, {"1.mo"})
    tg = _two_sided_tg("1.tg") + [_md("1.tg", 900, "COMBINED_TOTAL", status="SUSPENDED")]
    rec = A.audit_one_market("1.mo", 1000, "STRICT", "ATP", "2026-06-03", cat, idx,
                             lambda m: {"1.tg": tg}.get(m, []))
    funnel = A.refusal_funnel([rec])
    assert funnel["DERIVATIVE_SUSPENDED_AT_F0"] >= 1
    assert funnel["GAME_HANDICAP_ABSENT"] >= 1


def test_determinism_same_inputs_same_records() -> None:
    a = _audit_one()
    b = _audit_one()
    assert repr(a) == repr(b)


# --------------------------------------------------------- redundancy / sensitivity
def test_independent_update_status_present_when_derivatives_self_quote() -> None:
    recs = _sample_records()
    status = A.independent_update_status(recs, cutoff_s=15)
    assert status.usable_with_independent_volume >= 1
    assert status.verdict in {"SELF_QUOTES_PRESENT", "LIMITED_SELF_QUOTES"}


def test_spread_tick_sensitivity_packet_is_monotone() -> None:
    recs = _sample_records()
    packet = A.spread_tick_sensitivity(recs, cutoff_s=15, max_ticks_grid=[1, 2, 5])
    assert packet[1] <= packet[2] <= packet[5]


def test_selection_bias_coverage_by_cohort_tour() -> None:
    recs = _sample_records()
    cov = A.coverage_comparison(recs, cutoff_s=15)
    assert cov["by_cohort"]["STRICT"]["covered"] == 2
    assert cov["by_tour"]["ATP"]["covered"] == 2
    assert cov["overall"]["denominator"] == 3
