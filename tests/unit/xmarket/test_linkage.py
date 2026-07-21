"""STAGE3-0002 §5/§17 — event linkage of derivative markets to Match-Odds (red tests first).

Derivatives (COMBINED_TOTAL / HANDICAP) are linked to their Match-Odds sibling by
**eventId**, never by display name (§5). Anomalies are made VISIBLE, never silently
resolved. Hermetic: operates on MarketRef catalogue dataclasses; no corpus I/O, no outcome.
"""
from __future__ import annotations

import pytest

from research.xmarket import linkage as L


def _ref(mid: str, event_id: str, mtype: str, mtime: int = 1000,
         name: str = "A v B") -> L.MarketRef:
    return L.MarketRef(market_id=mid, event_id=event_id, market_type=mtype,
                       market_time_ms=mtime, event_name=name)


# --------------------------------------------------------------------- catalogue dedup
def test_duplicate_packaging_is_collapsed_not_double_counted() -> None:
    refs = [_ref("1.1", "E1", "MATCH_ODDS"), _ref("1.1", "E1", "MATCH_ODDS")]
    cat = L.build_catalogue(refs)
    assert len(cat) == 1
    assert cat["1.1"].event_id == "E1"


def test_conflicting_definition_for_same_market_id_refuses() -> None:
    refs = [_ref("1.1", "E1", "MATCH_ODDS"), _ref("1.1", "E2", "MATCH_ODDS")]
    with pytest.raises(L.LinkageError):
        L.build_catalogue(refs)


def test_relisted_instances_stay_distinct() -> None:
    refs = [_ref("1.1", "E1", "COMBINED_TOTAL"), _ref("1.2", "E1", "COMBINED_TOTAL")]
    cat = L.build_catalogue(refs)
    assert set(cat) == {"1.1", "1.2"}


# ---------------------------------------------------------------------- link by event
def test_links_derivatives_to_mo_by_event_id() -> None:
    cat = L.build_catalogue([
        _ref("1.mo", "E1", "MATCH_ODDS"),
        _ref("1.tg", "E1", "COMBINED_TOTAL"),
        _ref("1.gh", "E1", "HANDICAP"),
    ])
    res = L.link_mo("1.mo", cat, mo_event_index=L.mo_event_index(cat, {"1.mo"}))
    assert res.total_games_market_id == "1.tg"
    assert res.game_handicap_market_id == "1.gh"
    assert res.anomalies == ()


def test_linkage_is_by_event_id_not_display_name() -> None:
    cat = L.build_catalogue([
        _ref("1.mo", "E1", "MATCH_ODDS", name="A v B"),
        _ref("1.tg", "E2", "COMBINED_TOTAL", name="A v B"),  # same name, other event
    ])
    res = L.link_mo("1.mo", cat, mo_event_index=L.mo_event_index(cat, {"1.mo"}))
    assert res.total_games_market_id is None


def test_multiple_match_odds_for_event_is_flagged() -> None:
    cat = L.build_catalogue([
        _ref("1.mo1", "E1", "MATCH_ODDS"),
        _ref("1.mo2", "E1", "MATCH_ODDS"),
        _ref("1.tg", "E1", "COMBINED_TOTAL"),
    ])
    idx = L.mo_event_index(cat, {"1.mo1", "1.mo2"})
    res = L.link_mo("1.mo1", cat, mo_event_index=idx)
    assert L.MULTIPLE_MATCH_ODDS_FOR_EVENT_UNRESOLVED in res.anomalies


def test_ambiguous_when_two_derivatives_share_role_and_event() -> None:
    cat = L.build_catalogue([
        _ref("1.mo", "E1", "MATCH_ODDS"),
        _ref("1.tg1", "E1", "COMBINED_TOTAL"),
        _ref("1.tg2", "E1", "COMBINED_TOTAL"),  # relisted duplicate role
    ])
    res = L.link_mo("1.mo", cat, mo_event_index=L.mo_event_index(cat, {"1.mo"}))
    assert L.AMBIGUOUS_EVENT_LINKAGE in res.anomalies
    assert res.total_games_market_id is None  # not silently picked


def test_marketTime_mismatch_is_visible() -> None:
    cat = L.build_catalogue([
        _ref("1.mo", "E1", "MATCH_ODDS", mtime=1000),
        _ref("1.tg", "E1", "COMBINED_TOTAL", mtime=9999),
    ])
    res = L.link_mo("1.mo", cat, mo_event_index=L.mo_event_index(cat, {"1.mo"}))
    assert res.total_games_market_id == "1.tg"
    assert res.market_time_mismatch is True


def test_derivative_without_committed_mo_event_is_not_linked() -> None:
    cat = L.build_catalogue([
        _ref("1.tg", "E9", "COMBINED_TOTAL"),
    ])
    idx = L.mo_event_index(cat, committed_mo_ids=set())
    unlinked = L.unlinked_derivatives(cat, idx)
    assert ("1.tg", L.NOT_LINKED_TO_MATCH_ODDS_EVENT) in unlinked


def test_role_classification_uses_parser_roles() -> None:
    cat = L.build_catalogue([
        _ref("1.mo", "E1", "MATCH_ODDS"),
        _ref("1.sw", "E1", "SET_WINNER"),
    ])
    res = L.link_mo("1.mo", cat, mo_event_index=L.mo_event_index(cat, {"1.mo"}))
    assert res.total_games_market_id is None
    assert res.game_handicap_market_id is None
    assert "1.sw" in res.auxiliary_market_ids
