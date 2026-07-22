"""STAGE3-0004 §10/§14 — PROMOTED event linkage (red tests first)."""
from __future__ import annotations

import pytest

from xmarket_contracts import linkage as L


def _ref(mid: str, ev: str, mt: str, mtime: int = 1000, name: str = "A v B") -> L.MarketRef:
    return L.MarketRef(market_id=mid, event_id=ev, market_type=mt, market_time_ms=mtime, event_name=name)


def test_duplicate_packaging_collapses() -> None:
    cat = L.build_catalogue([_ref("1.1", "E1", "MATCH_ODDS"), _ref("1.1", "E1", "MATCH_ODDS")])
    assert len(cat) == 1


def test_conflicting_definition_refuses() -> None:
    with pytest.raises(L.LinkageError):
        L.build_catalogue([_ref("1.1", "E1", "MATCH_ODDS"), _ref("1.1", "E2", "MATCH_ODDS")])


def test_relisted_instances_stay_distinct() -> None:
    cat = L.build_catalogue([_ref("1.1", "E1", "COMBINED_TOTAL"), _ref("1.2", "E1", "COMBINED_TOTAL")])
    assert set(cat) == {"1.1", "1.2"}


def test_links_by_event_id_not_name() -> None:
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS"), _ref("1.tg", "E1", "COMBINED_TOTAL"),
                             _ref("1.gh", "E1", "HANDICAP")])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert res.total_games_market_id == "1.tg" and res.game_handicap_market_id == "1.gh"
    assert res.anomalies == ()


def test_same_name_different_event_does_not_link() -> None:
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS", name="A v B"),
                             _ref("1.tg", "E2", "COMBINED_TOTAL", name="A v B")])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert res.total_games_market_id is None


def test_multiple_mo_flagged() -> None:
    cat = L.build_catalogue([_ref("1.mo1", "E1", "MATCH_ODDS"), _ref("1.mo2", "E1", "MATCH_ODDS"),
                             _ref("1.tg", "E1", "COMBINED_TOTAL")])
    res = L.link_mo("1.mo1", cat, L.mo_event_index(cat, {"1.mo1", "1.mo2"}))
    assert L.MULTIPLE_MATCH_ODDS_FOR_EVENT_UNRESOLVED in res.anomalies


def test_ambiguous_same_role_not_silently_picked() -> None:
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS"), _ref("1.t1", "E1", "COMBINED_TOTAL"),
                             _ref("1.t2", "E1", "COMBINED_TOTAL")])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert L.AMBIGUOUS_EVENT_LINKAGE in res.anomalies
    assert res.total_games_market_id is None


def test_market_time_mismatch_visible() -> None:
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS", mtime=1000),
                             _ref("1.tg", "E1", "COMBINED_TOTAL", mtime=9999)])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert res.market_time_mismatch is True


def test_unlinked_derivative_tagged() -> None:
    cat = L.build_catalogue([_ref("1.tg", "E9", "COMBINED_TOTAL")])
    assert ("1.tg", L.NOT_LINKED_TO_MATCH_ODDS_EVENT) in L.unlinked_derivatives(cat, L.mo_event_index(cat, set()))


def test_auxiliary_uses_parser_roles() -> None:
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS"), _ref("1.sw", "E1", "SET_WINNER")])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert res.total_games_market_id is None and "1.sw" in res.auxiliary_market_ids
