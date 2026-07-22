"""STAGE3-0004 §10/§14 — PROMOTED as-of-F0 synchronizer (red tests first).

Hardened production re-home. A derivative's book is rebuilt ONLY from messages with
publish_time <= the F0 decision timestamp; no post-F0 message can enter; a later message
cannot backfill an earlier missing side. One-sided / crossed / suspended / in-play / empty
refuse. No book-quality arithmetic (that stays research-only). No outcome.
"""
from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from xmarket_contracts import synchronizer as SY


def _md(mid: str, pt: int, *, status: str = "OPEN", in_play: bool = False,
        mt: str = "COMBINED_TOTAL", ev: str = "E1", cross: bool = False,
        market_time: int = 2000) -> dict[str, Any]:
    return {"pt": pt, "mc": [{"id": mid, "marketDefinition": {
        "status": status, "inPlay": in_play, "marketType": mt, "eventId": ev,
        "crossMatching": cross, "marketTime": market_time}}]}


def _rc(mid: str, pt: int, sel: int, hc: float, *, bb: list[list[float]] | None = None,
        bl: list[list[float]] | None = None, tv: float = 0.0) -> dict[str, Any]:
    ch: dict[str, Any] = {"id": sel, "hc": hc, "tv": tv}
    if bb is not None:
        ch["batb"] = bb
    if bl is not None:
        ch["batl"] = bl
    return {"pt": pt, "mc": [{"id": mid, "rc": [ch]}]}


def _two_sided(mid: str = "1.1") -> list[dict[str, Any]]:
    return [
        _md(mid, 100),
        _rc(mid, 200, 111, 20.5, bb=[[0, 1.90, 50.0]], bl=[[0, 1.95, 40.0]], tv=500.0),
        _rc(mid, 300, 222, 20.5, bb=[[0, 2.05, 30.0]], bl=[[0, 2.10, 20.0]], tv=400.0),
    ]


def test_post_f0_message_is_inaccessible() -> None:
    stream = _two_sided() + [_rc("1.1", 5000, 111, 20.5, bb=[[0, 1.10, 999.0]], bl=[[0, 1.11, 999.0]])]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    q = {(s.selection_id, s.line): s for s in snap.quotes}[(111, 20.5)]
    assert q.best_back_price == 1.90
    assert snap.latest_message_pt == 300


def test_message_exactly_at_cutoff_is_included() -> None:
    stream = [_md("1.1", 100),
              _rc("1.1", 1000, 111, 20.5, bb=[[0, 1.90, 50.0]], bl=[[0, 1.95, 40.0]])]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert snap.latest_message_pt == 1000


def test_later_price_cannot_backfill_missing_side() -> None:
    stream = [_md("1.1", 100), _rc("1.1", 200, 111, 20.5, bb=[[0, 1.90, 50.0]]),
              _rc("1.1", 5000, 111, 20.5, bb=[[0, 1.90, 50.0]], bl=[[0, 1.95, 40.0]])]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    q = {(s.selection_id, s.line): s for s in snap.quotes}[(111, 20.5)]
    assert q.best_lay_price is None
    assert SY.book_exclusion_reason(snap) == SY.DERIVATIVE_ONE_SIDED_AT_F0


def test_no_state_before_cutoff_refuses() -> None:
    with pytest.raises(SY.ReconstructionRefusal) as ei:
        SY.reconstruct_as_of([_md("1.1", 5000)], "1.1", cutoff_ms=1000)
    assert ei.value.reason == SY.NO_STATE_AT_OR_BEFORE_F0_TIMESTAMP


def test_other_market_messages_ignored() -> None:
    stream = _two_sided() + [_rc("1.999", 400, 111, 20.5, bb=[[0, 1.01, 1.0]], bl=[[0, 1.02, 1.0]])]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert all(s.best_back_price != 1.01 for s in snap.quotes)


def test_in_play_refuses() -> None:
    snap = SY.reconstruct_as_of(_two_sided() + [_md("1.1", 900, in_play=True)], "1.1", cutoff_ms=1000)
    assert SY.book_exclusion_reason(snap) == SY.DERIVATIVE_IN_PLAY_AT_F0


def test_suspended_refuses() -> None:
    snap = SY.reconstruct_as_of(_two_sided() + [_md("1.1", 900, status="SUSPENDED")], "1.1", cutoff_ms=1000)
    assert SY.book_exclusion_reason(snap) == SY.DERIVATIVE_SUSPENDED_AT_F0


def test_crossed_refuses() -> None:
    stream = [_md("1.1", 100), _rc("1.1", 200, 111, 20.5, bb=[[0, 2.00, 5.0]], bl=[[0, 1.90, 5.0]])]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert SY.book_exclusion_reason(snap) == SY.DERIVATIVE_CROSSED_AT_F0


def test_one_sided_refuses() -> None:
    stream = [_md("1.1", 100), _rc("1.1", 200, 111, 20.5, bb=[[0, 1.90, 5.0]])]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert SY.book_exclusion_reason(snap) == SY.DERIVATIVE_ONE_SIDED_AT_F0


def test_empty_refuses() -> None:
    stream = [_md("1.1", 100), _rc("1.1", 200, 111, 20.5, tv=0.0)]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert SY.book_exclusion_reason(snap) == SY.DERIVATIVE_EMPTY_AT_F0


def test_clean_two_sided_passes_and_quote_age() -> None:
    snap = SY.reconstruct_as_of(_two_sided(), "1.1", cutoff_ms=1000)
    assert SY.book_exclusion_reason(snap) is None
    assert SY.quote_age_seconds(snap) == pytest.approx(0.7)


def test_snapshot_has_no_outcome_field() -> None:
    snap = SY.reconstruct_as_of(_two_sided(), "1.1", cutoff_ms=1000)
    banned = {"winner", "result", "settled", "pnl", "bsp", "outcome", "close", "won", "roi", "ev"}
    fields = {f.name.lower() for f in type(snap).__dataclass_fields__.values()}
    fields |= {f.name.lower() for f in type(snap.quotes[0]).__dataclass_fields__.values()}
    assert not (fields & banned)


def test_reconstruction_row_order_invariant() -> None:
    a = SY.reconstruct_as_of(_two_sided(), "1.1", cutoff_ms=1000)
    b = SY.reconstruct_as_of(list(reversed(_two_sided())), "1.1", cutoff_ms=1000)
    assert repr(a) == repr(b)


# ---------------------------------------------------------------------------
# STAGE3-0006 §8 mutation-kill tests (behavioural survivors, section C).
# ---------------------------------------------------------------------------

def _fresh_str(s: str) -> str:
    """A fresh, non-interned str object equal in value to ``s``."""
    return s.encode().decode()


def _one_quote(*, bb: Any = None, bl: Any = None) -> SY.SelectionQuote:
    """Reconstruct a one-selection book from a single rc message; return its quote.
    Accepts raw (possibly malformed) ladder values for the ``_best_level`` guards."""
    ch: dict[str, Any] = {"id": 111, "hc": 20.5, "tv": 0.0}
    if bb is not None:
        ch["batb"] = bb
    if bl is not None:
        ch["batl"] = bl
    snap = SY.reconstruct_as_of([{"pt": 200, "mc": [{"id": "1.1", "rc": [ch]}]}], "1.1", cutoff_ms=1000)
    return snap.quotes[0]


def test_selection_quote_frozen_and_hashable() -> None:
    """L42 SelectionQuote @dataclass(frozen=True) ReplaceTrueWithFalse::0."""
    q = SY.reconstruct_as_of(_two_sided(), "1.1", cutoff_ms=1000).quotes[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        q.selection_id = 0  # type: ignore[misc]
    assert isinstance(hash(q), int)


def test_asofbook_frozen_and_hashable() -> None:
    """L58 AsOfBook @dataclass(frozen=True) ReplaceTrueWithFalse::1."""
    snap = SY.reconstruct_as_of(_two_sided(), "1.1", cutoff_ms=1000)
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.market_id = "x"  # type: ignore[misc]
    assert isinstance(hash(snap), int)


def test_no_state_refusal_detail_included() -> None:
    """L26 `f"{reason}: {detail}" if detail else reason` AddNot::0 and L94
    `have_definition = False` FalseWithTrue::1 — an all-post-cutoff stream must refuse via
    the L136 path carrying "has no state at/before"."""
    with pytest.raises(SY.ReconstructionRefusal) as ei:
        SY.reconstruct_as_of([_md("1.1", 5000)], "1.1", cutoff_ms=1000)
    assert "has no state at/before" in str(ei.value)


def test_lay_only_selection_back_levels_zero() -> None:
    """L36 `back_levels: int = 0` NumberReplacer::0/::1 — a lay-only selection reads the
    default back_levels, which must be 0."""
    q = _one_quote(bl=[[0, 1.95, 5.0]])
    assert q.back_levels == 0


def test_back_only_selection_lay_levels_zero() -> None:
    """L37 `lay_levels: int = 0` NumberReplacer::2/::3 — a back-only selection reads the
    default lay_levels, which must be 0."""
    q = _one_quote(bb=[[0, 1.90, 5.0]])
    assert q.lay_levels == 0


def test_non_list_ladder_is_clean_none() -> None:
    """L75 `not isinstance(ladder, list) or not ladder` ReplaceOrWithAnd::0 — a truthy
    non-list ladder must yield None (mutant `and` iterates an int -> TypeError)."""
    assert _one_quote(bb=5).best_back_price is None


def test_empty_ladder_zero_levels() -> None:
    """L76 `return None, None, 0` NumberReplacer::8/::9 — an empty ladder yields level
    count 0, not 1/-1."""
    q = _one_quote(bb=[])
    assert q.best_back_price is None
    assert q.back_levels == 0


def test_ladder_entry_wrong_length_rejected() -> None:
    """L77 `len(e) == 3` Eq_LtE::0 / Eq_GtE::0 — entries of length 2 and 4 must be dropped
    (mutants `<=`/`>=` would admit them)."""
    assert _one_quote(bb=[[1, 2.0]]).best_back_price is None
    assert _one_quote(bb=[[0, 1.9, 5.0, 99]]).best_back_price is None


def test_non_numeric_and_bool_price_rejected() -> None:
    """L78 `isinstance(e[1], (int, float)) and not isinstance(e[1], bool)`
    NumberReplacer::12..15 — a non-numeric or bool price must be dropped (mutants validating
    e[0] would admit them)."""
    assert _one_quote(bb=[[0, "bad", 5.0]]).best_back_price is None
    assert _one_quote(bb=[[0, True, 5.0]]).best_back_price is None


def test_negative_size_rejected() -> None:
    """L79 `e[2] > 0` Gt_NotEq::0 — a negative-size level must be dropped (mutant `!= 0`
    would admit it)."""
    assert _one_quote(bb=[[0, 1.9, -5.0]]).best_back_price is None


def test_small_positive_size_kept() -> None:
    """L79 `e[2] > 0` NumberReplacer (`> 1`) — a size in (0, 1] must be kept."""
    assert _one_quote(bb=[[0, 1.9, 0.5]]).best_back_price == 1.9


def test_best_level_is_lowest_ladder_index() -> None:
    """L81 `min(priced, key=lambda e: e[0])` NumberReplacer::24/::25 — with distinct
    level/price/size the best is chosen by ladder index (level 0), not by price or size."""
    q = _one_quote(bb=[[0, 1.95, 10.0], [1, 1.90, 50.0], [2, 2.00, 5.0]])
    assert q.best_back_price == 1.95


def test_best_level_sizes_are_size_not_price() -> None:
    """L83 `float(best[1]), float(best[2]), len(priced)` NumberReplacer::31 — best_*_size
    must be the size (best[2]), not the price (best[1])."""
    snap = SY.reconstruct_as_of(_two_sided(), "1.1", cutoff_ms=1000)
    q = {(s.selection_id, s.line): s for s in snap.quotes}[(111, 20.5)]
    assert q.best_back_size == 50.0
    assert q.best_lay_size == 40.0


def test_rc_only_stream_not_in_play() -> None:
    """L89 `in_play = False` FalseWithTrue::0 — with no marketDefinition, in_play must
    stay False (mutant init True would refuse IN_PLAY)."""
    snap = SY.reconstruct_as_of([_rc("1.1", 200, 111, 20.5, bb=[[0, 1.9, 5.0]], bl=[[0, 1.95, 5.0]])],
                                "1.1", cutoff_ms=1000)
    assert snap.in_play is False


def test_applied_message_at_pt_zero_is_returned() -> None:
    """L138 `latest_pt < 0` Lt_Eq::0 / Lt_LtE::0 / NumberReplacer (`< 1`) — an applied
    message at pt=0 must reconstruct (mutants `==0`/`<=0`/`<1` would refuse)."""
    snap = SY.reconstruct_as_of([_rc("1.1", 0, 111, 20.5, bb=[[0, 1.9, 5.0]], bl=[[0, 1.95, 5.0]])],
                                "1.1", cutoff_ms=1000)
    assert snap.latest_message_pt == 0


def test_negative_pt_never_beats_sentinel() -> None:
    """L95 `latest_pt = -1` USub_UAdd::1 / USub_Not::1 / Delete_USub::1 — a single applied
    message at pt=-3 must still refuse NO_STATE; a >=0 sentinel would return spuriously."""
    with pytest.raises(SY.ReconstructionRefusal):
        SY.reconstruct_as_of([_rc("1.1", -3, 111, 20.5, bb=[[0, 1.9, 5.0]])], "1.1", cutoff_ms=1000)


def test_latest_pt_ignores_other_market_message() -> None:
    """L102 `applied = False` FalseWithTrue::2 — an in-scope other-market message (pt 400)
    must not advance latest_message_pt (mutant init True would set it to 400)."""
    stream = [_md("1.1", 100),
              _rc("1.1", 200, 111, 20.5, bb=[[0, 1.90, 50.0]], bl=[[0, 1.95, 40.0]]),
              _rc("1.1", 300, 222, 20.5, bb=[[0, 2.05, 30.0]], bl=[[0, 2.10, 20.0]]),
              _rc("1.999", 400, 111, 20.5, bb=[[0, 1.01, 1.0]], bl=[[0, 1.02, 1.0]])]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=5000)
    assert snap.latest_message_pt == 300


def test_other_market_id_below_ours_excluded() -> None:
    """L104 `mc.get("id") != market_id` NotEq_Gt::0 — a stray mc id ("1.0") sorting below
    ours ("1.1") must be excluded (mutant `>` would process it)."""
    stream = [_md("1.1", 100), _rc("1.1", 200, 111, 20.5, bb=[[0, 1.9, 5.0]], bl=[[0, 1.95, 5.0]]),
              {"pt": 250, "mc": [{"id": "1.0", "rc": [{"id": 999, "hc": 20.5, "batb": [[0, 7.77, 5.0]]}]}]}]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert all(q.best_back_price != 7.77 for q in snap.quotes)


def test_own_market_equal_nonidentical_id_matched() -> None:
    """L104 `mc.get("id") != market_id` NotEq_IsNot::0 — market_id passed as an equal-but-
    non-identical string must still match own messages; `is not` would skip them all."""
    snap = SY.reconstruct_as_of(
        [_md("1.1", 100), _rc("1.1", 200, 111, 20.5, bb=[[0, 1.9, 5.0]], bl=[[0, 1.95, 5.0]])],
        _fresh_str("1.1"), cutoff_ms=1000)
    assert len(snap.quotes) == 1


def test_mc_loop_continues_past_other_market_entry() -> None:
    """L105 `continue` ContinueWithBreak::1 — a leading other-market mc entry must not stop
    processing our mc entry in the same message."""
    stream = [{"pt": 200, "mc": [
        {"id": "other"},
        {"id": "1.1", "rc": [{"id": 111, "hc": 20.5, "batb": [[0, 1.9, 5.0]], "batl": [[0, 1.95, 5.0]]}]},
    ]}]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert len(snap.quotes) == 1


def test_rc_loop_continues_past_non_int_selection() -> None:
    """L119 `continue` ContinueWithBreak::2 — a leading non-int selection must not stop
    processing a valid selection in the same rc list."""
    stream = [{"pt": 200, "mc": [{"id": "1.1", "rc": [
        {"id": "notint", "hc": 1.0},
        {"id": 111, "hc": 20.5, "batb": [[0, 1.9, 5.0]], "batl": [[0, 1.95, 5.0]]},
    ]}]}]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert any(q.selection_id == 111 for q in snap.quotes)


def test_definition_only_market_reconstructs() -> None:
    """L135 `not have_definition and not book` Delete_Not::9 — a definition-only market
    (no rc) must reconstruct (empty book), not refuse."""
    snap = SY.reconstruct_as_of([_md("1.1", 100)], "1.1", cutoff_ms=1000)
    assert SY.book_exclusion_reason(snap) == SY.DERIVATIVE_EMPTY_AT_F0


def test_rc_only_market_reconstructs() -> None:
    """L135 `not have_definition and not book` Delete_Not::9 — an rc-only market (no
    definition) must reconstruct, not refuse."""
    snap = SY.reconstruct_as_of([_rc("1.1", 200, 111, 20.5, bb=[[0, 1.9, 5.0]], bl=[[0, 1.95, 5.0]])],
                                "1.1", cutoff_ms=1000)
    assert snap.latest_message_pt == 200


def test_none_line_and_line_ordering() -> None:
    """L149 sort key `... if kv[0][1] is not None else -1.0` IsNot_Is::1 / AddNot::14 /
    USub_UAdd::2 / USub_Invert::2 / USub_Not::2 / Delete_USub::2 / NumberReplacer::43..49 —
    a None-line selection plus lines spanning the (-1, +1) range must sort with the None
    sentinel (-1.0) first; every mutant that moves the sentinel or mishandles None reorders
    or raises."""
    stream = [
        _rc("1.1", 100, 111, 20.5, bb=[[0, 1.9, 5.0]]),
        _rc("1.1", 110, 111, 10.5, bb=[[0, 1.9, 5.0]]),
        _rc("1.1", 120, 111, 0.5, bb=[[0, 1.9, 5.0]]),
        _rc("1.1", 130, 111, -0.5, bb=[[0, 1.9, 5.0]]),
        {"pt": 140, "mc": [{"id": "1.1", "rc": [{"id": 111, "tv": 0.0}]}]},  # None line (no hc)
    ]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert [q.line for q in snap.quotes] == [None, -0.5, 0.5, 10.5, 20.5]


def test_locked_book_is_crossed() -> None:
    """L164 `q.best_back_price >= q.best_lay_price` GtE_Gt::0 — a locked book (back == lay)
    must be DERIVATIVE_CROSSED_AT_F0 (mutant `>` treats equal as usable)."""
    stream = [_md("1.1", 100), _rc("1.1", 200, 111, 20.5, bb=[[0, 1.95, 5.0]], bl=[[0, 1.95, 5.0]])]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert SY.book_exclusion_reason(snap) == SY.DERIVATIVE_CROSSED_AT_F0


def test_status_below_open_is_suspended() -> None:
    """L172 `snap.status != "OPEN"` NotEq_Gt::1 — a status sorting below "OPEN" ("CLOSED")
    must be DERIVATIVE_SUSPENDED_AT_F0 (mutant `>` treats it as OPEN)."""
    stream = [_md("1.1", 100, status="CLOSED"),
              _rc("1.1", 200, 111, 20.5, bb=[[0, 1.9, 5.0]], bl=[[0, 1.95, 5.0]])]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert SY.book_exclusion_reason(snap) == SY.DERIVATIVE_SUSPENDED_AT_F0


def test_status_equal_nonidentical_open_not_suspended() -> None:
    """L172 `snap.status != "OPEN"` NotEq_IsNot::1 — an equal-but-non-identical "OPEN"
    status must be usable; `is not` would force SUSPENDED."""
    stream = [_md("1.1", 100, status=_fresh_str("OPEN")),
              _rc("1.1", 200, 111, 20.5, bb=[[0, 1.9, 5.0]], bl=[[0, 1.95, 5.0]])]
    snap = SY.reconstruct_as_of(stream, "1.1", cutoff_ms=1000)
    assert SY.book_exclusion_reason(snap) is None
