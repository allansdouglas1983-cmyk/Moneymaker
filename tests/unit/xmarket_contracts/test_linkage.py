"""STAGE3-0004 §10/§14 — PROMOTED event linkage (red tests first)."""
from __future__ import annotations

import dataclasses

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


# ---------------------------------------------------------------------------
# STAGE3-0006 §8 mutation-kill tests (behavioural survivors, section C).
# committed_mo_ids is passed as an ordered list for L69/L71: mo_event_index only
# iterates it (no set-only semantics), so this exercises the identical code path
# deterministically instead of relying on randomised set-iteration order.
# ---------------------------------------------------------------------------

def _fresh_str(s: str) -> str:
    """A fresh, non-interned str object equal in value to ``s``."""
    return s.encode().decode()


def _fresh_int(n: int) -> int:
    """A fresh, non-interned int object equal in value to ``n``."""
    return int(str(n))


def test_market_ref_frozen_and_hashable() -> None:
    """L29 MarketRef @dataclass(frozen=True) ReplaceTrueWithFalse::0."""
    ref = _ref("1.1", "E1", "MATCH_ODDS")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.market_id = "x"  # type: ignore[misc]
    assert isinstance(hash(ref), int)


def test_link_result_frozen_and_hashable() -> None:
    """L40 LinkResult @dataclass(frozen=True) ReplaceTrueWithFalse::1."""
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS")])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.mo_market_id = "x"  # type: ignore[misc]
    assert isinstance(hash(res), int)


def test_mo_event_index_none_event_committed_mo_skipped() -> None:
    """L68 `if ref is None or ref.event_id is None: continue` ReplaceOrWithAnd::0 — `and`
    would index a committed MO whose event_id is None under a None key."""
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS"),
                             L.MarketRef("1.none", None, "MATCH_ODDS", 1000)])
    assert L.mo_event_index(cat, {"1.none"}) == {}


def test_mo_event_index_break_would_truncate_committed_loop() -> None:
    """L69 `continue` ContinueWithBreak::0 — an absent committed id precedes a valid one;
    `break` would drop the valid MO."""
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS")])
    assert L.mo_event_index(cat, ["1.skip", "1.mo"]) == {"E1": ["1.mo"]}


def test_mo_event_index_sorts_ids_per_event() -> None:
    """L71 `for ev in idx: idx[ev].sort()` ZeroIterationForLoop::2 — ids appended in
    reverse; skipping the sort would leave them reversed."""
    cat = L.build_catalogue([_ref("1.mo1", "E1", "MATCH_ODDS"), _ref("1.mo2", "E1", "MATCH_ODDS")])
    assert L.mo_event_index(cat, ["1.mo2", "1.mo1"]) == {"E1": ["1.mo1", "1.mo2"]}


def test_multiple_mo_not_flagged_at_zero_count() -> None:
    """L84 `len(...) > 1` Gt_NotEq::0 — `0 != 1` would falsely flag MULTIPLE when the
    event index is empty."""
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS"), _ref("1.tg", "E1", "COMBINED_TOTAL")])
    res = L.link_mo("1.mo", cat, {})
    assert L.MULTIPLE_MATCH_ODDS_FOR_EVENT_UNRESOLVED not in res.anomalies


def test_sibling_event_below_mo_event_not_linked() -> None:
    """L88 `r.event_id == event_id` Eq_LtE::0 — MO@"E2", TG@"E1": `"E1" <= "E2"` would
    wrongly link a different event's sibling."""
    cat = L.build_catalogue([_ref("1.mo", "E2", "MATCH_ODDS"), _ref("1.tg", "E1", "COMBINED_TOTAL")])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert res.total_games_market_id is None


def test_sibling_event_equal_nonidentical_links() -> None:
    """L88 `r.event_id == event_id` Eq_Is::0 — equal-but-non-identical event strings must
    link; `is` would miss the sibling."""
    cat = L.build_catalogue([_ref("1.mo", _fresh_str("E1"), "MATCH_ODDS"),
                             _ref("1.tg", _fresh_str("E1"), "COMBINED_TOTAL")])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert res.total_games_market_id == "1.tg"


def test_sole_zero_candidates_not_ambiguous() -> None:
    """L100 `len(cands) > 1` Gt_NotEq::1 / Gt_Lt::1 / Gt_LtE::1 / AddNot::6 — a role with
    zero candidates (no Game Handicap) must not be flagged AMBIGUOUS."""
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS"), _ref("1.tg", "E1", "COMBINED_TOTAL")])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert L.AMBIGUOUS_EVENT_LINKAGE not in res.anomalies


def test_none_market_type_sibling_does_not_raise() -> None:
    """L111 `... and market_role(r.market_type) not in ...` AndWithOr::3 — `or` would call
    market_role(None) and raise; baseline skips the None-typed sibling."""
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS"), L.MarketRef("1.x", "E1", None, 1000)])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert res.mo_market_id == "1.mo"


def test_market_time_mismatch_false_when_equal() -> None:
    """L114 `mismatch = False` FalseWithTrue::0 and L116 NotEq_GtE::2 — equal linked/mo
    times must leave mismatch False (mutants force True)."""
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS", mtime=1000),
                             _ref("1.tg", "E1", "COMBINED_TOTAL", mtime=1000)])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert res.market_time_mismatch is False


def test_market_time_mismatch_true_when_linked_below_mo() -> None:
    """L116 `catalogue[linked].market_time_ms != mo.market_time_ms` NotEq_Gt::2 — linked
    (1000) < mo (9999): `1000 > 9999` is False and `>` would miss the mismatch."""
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS", mtime=9999),
                             _ref("1.tg", "E1", "COMBINED_TOTAL", mtime=1000)])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert res.market_time_mismatch is True


def test_market_time_mismatch_false_equal_nonidentical() -> None:
    """L116 `... != ...` NotEq_IsNot::2 — equal-but-non-identical times must be no mismatch;
    `is not` would force True."""
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS", mtime=1000),
                             _ref("1.tg", "E1", "COMBINED_TOTAL", mtime=_fresh_int(1000))])
    res = L.link_mo("1.mo", cat, L.mo_event_index(cat, {"1.mo"}))
    assert res.market_time_mismatch is False


def test_unlinked_break_would_skip_nonstr_then_derivative() -> None:
    """L132 `continue` ContinueWithBreak::1 — a non-str-typed ref precedes an unlinked
    derivative; `break` would drop the derivative."""
    cat = L.build_catalogue([L.MarketRef("1.x", "E9", None, 1000),
                             _ref("1.tg", "E9", "COMBINED_TOTAL")])
    assert ("1.tg", L.NOT_LINKED_TO_MATCH_ODDS_EVENT) in L.unlinked_derivatives(cat, {})


def test_unlinked_break_would_skip_mo_then_derivative() -> None:
    """L134 `continue` ContinueWithBreak::2 — a non-identifying (MO) ref precedes an
    unlinked derivative; `break` would drop the derivative."""
    cat = L.build_catalogue([_ref("1.mo", "E9", "MATCH_ODDS"), _ref("1.tg", "E9", "COMBINED_TOTAL")])
    assert ("1.tg", L.NOT_LINKED_TO_MATCH_ODDS_EVENT) in L.unlinked_derivatives(cat, {})


def test_linked_derivative_not_tagged_unlinked() -> None:
    """L135 `ref.event_id is None or ref.event_id not in mo_event_index` Is_IsNot::4 /
    AddNot::10 — a linked derivative (event present in the index) must not be tagged."""
    cat = L.build_catalogue([_ref("1.mo", "E1", "MATCH_ODDS"), _ref("1.tg", "E1", "COMBINED_TOTAL")])
    idx = L.mo_event_index(cat, {"1.mo"})
    assert ("1.tg", L.NOT_LINKED_TO_MATCH_ODDS_EVENT) not in L.unlinked_derivatives(cat, idx)
