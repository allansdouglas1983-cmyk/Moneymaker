"""STAGE3-0004 §10/§14 — PROMOTED as-of-F0 synchronizer (red tests first).

Hardened production re-home. A derivative's book is rebuilt ONLY from messages with
publish_time <= the F0 decision timestamp; no post-F0 message can enter; a later message
cannot backfill an earlier missing side. One-sided / crossed / suspended / in-play / empty
refuse. No book-quality arithmetic (that stays research-only). No outcome.
"""
from __future__ import annotations

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
