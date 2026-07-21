"""STAGE3-0002 §6/§7/§8/§16/§17 — as-of-F0 derivative reconstruction (red tests first).

The leakage-critical core of the audit: a derivative sibling's book state is rebuilt ONLY
from stream messages whose publish_time (``pt``) is <= the frozen F0 decision timestamp
(``commit_pt_ms``). No later, substitute, closing, or in-play state may enter; a later
message can never fill an earlier missing state. The reconstructed snapshot carries NO
outcome / winner / settlement / P&L field (structurally impossible — §16).

Tests are hermetic (synthetic messages) — no corpus dependency.
"""
from __future__ import annotations

from typing import Any

import pytest

from research.xmarket import reconstruct as R


# --------------------------------------------------------------------------- helpers
def _md(mid: str, pt: int, *, status: str = "OPEN", in_play: bool = False,
        market_type: str = "COMBINED_TOTAL", event_id: str = "35670766", cross: bool = False,
        market_time: int = 2000, num_active: int = 110) -> dict[str, Any]:
    return {"pt": pt, "mc": [{"id": mid, "marketDefinition": {
        "status": status, "inPlay": in_play, "marketType": market_type,
        "eventId": event_id, "crossMatching": cross, "marketTime": market_time,
        "numberOfActiveRunners": num_active}}]}


def _rc(mid: str, pt: int, sel: int, hc: float, *, batb: list[list[float]] | None = None,
        batl: list[list[float]] | None = None, ltp: float = 0.0,
        tv: float = 0.0) -> dict[str, Any]:
    change: dict[str, Any] = {"id": sel, "hc": hc, "ltp": ltp, "tv": tv}
    if batb is not None:
        change["batb"] = batb
    if batl is not None:
        change["batl"] = batl
    return {"pt": pt, "mc": [{"id": mid, "rc": [change]}]}


def _two_sided_stream(mid: str = "1.1") -> list[dict[str, Any]]:
    return [
        _md(mid, 100),
        _rc(mid, 200, 7698572, 20.5, batb=[[0, 1.90, 50.0]], batl=[[0, 1.95, 40.0]], tv=500.0),
        _rc(mid, 300, 7698577, 20.5, batb=[[0, 2.05, 30.0]], batl=[[0, 2.10, 20.0]], tv=450.0),
    ]


# --------------------------------------------------------------- as-of timestamp core
def test_state_after_f0_timestamp_is_structurally_inaccessible() -> None:
    mid = "1.1"
    stream = _two_sided_stream(mid) + [
        _rc(mid, 5000, 7698572, 20.5, batb=[[0, 1.10, 999.0]], batl=[[0, 1.11, 999.0]]),
    ]
    snap = R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    q = {(s.selection_id, s.line): s for s in snap.quotes}[(7698572, 20.5)]
    assert q.best_back_price == 1.90
    assert q.best_back_size == 50.0
    assert snap.latest_message_pt == 300


def test_later_price_cannot_fill_an_earlier_missing_state() -> None:
    mid = "1.1"
    stream = [
        _md(mid, 100),
        # pre-cutoff the Over is BACK-ONLY (a genuinely one-sided book at F0)
        _rc(mid, 200, 7698572, 20.5, batb=[[0, 1.90, 50.0]]),
        # the lay side (which would make it two-sided) only arrives AFTER the cutoff
        _rc(mid, 5000, 7698572, 20.5, batb=[[0, 1.90, 50.0]], batl=[[0, 1.95, 40.0]]),
    ]
    snap = R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    q = {(s.selection_id, s.line): s for s in snap.quotes}[(7698572, 20.5)]
    assert q.best_back_price == 1.90
    assert q.best_lay_price is None  # the later lay did NOT backfill the earlier missing side
    assert R.book_exclusion_reason(snap) == R.DERIVATIVE_ONE_SIDED_AT_F0


def test_message_exactly_at_cutoff_is_included() -> None:
    # the rule is publish_time <= commit_pt_ms: a message at pt EXACTLY == cutoff is IN.
    # Kills the leakage-boundary mutant `pt > cutoff` -> `pt >= cutoff` (which would drop it).
    mid = "1.1"
    stream = [
        _md(mid, 100),
        _rc(mid, 1000, 7698572, 20.5, batb=[[0, 1.90, 50.0]], batl=[[0, 1.95, 40.0]]),
    ]
    snap = R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    assert snap.latest_message_pt == 1000
    q = {(s.selection_id, s.line): s for s in snap.quotes}[(7698572, 20.5)]
    assert q.best_back_price == 1.90 and q.best_lay_price == 1.95


def test_no_state_at_or_before_cutoff_refuses() -> None:
    mid = "1.1"
    stream = [_md(mid, 5000), _rc(mid, 6000, 7698572, 20.5, batb=[[0, 1.9, 5.0]])]
    with pytest.raises(R.ReconstructionRefusal) as ei:
        R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    assert ei.value.reason == R.NO_STATE_AT_OR_BEFORE_F0_TIMESTAMP


def test_messages_for_other_markets_are_ignored() -> None:
    mid = "1.1"
    stream = _two_sided_stream(mid) + [
        _rc("1.999", 400, 7698572, 20.5, batb=[[0, 1.01, 1.0]], batl=[[0, 1.02, 1.0]]),
    ]
    snap = R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    assert snap.market_id == mid
    assert all(s.best_back_price != 1.01 for s in snap.quotes)


# ------------------------------------------------------------------- book exclusions
def test_in_play_at_f0_refuses() -> None:
    mid = "1.1"
    stream = _two_sided_stream(mid) + [_md(mid, 900, in_play=True)]
    snap = R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    assert R.book_exclusion_reason(snap) == R.DERIVATIVE_IN_PLAY_AT_F0


def test_suspended_at_f0_refuses() -> None:
    mid = "1.1"
    stream = _two_sided_stream(mid) + [_md(mid, 900, status="SUSPENDED")]
    snap = R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    assert R.book_exclusion_reason(snap) == R.DERIVATIVE_SUSPENDED_AT_F0


def test_one_sided_at_f0_refuses() -> None:
    mid = "1.1"
    stream = [
        _md(mid, 100),
        _rc(mid, 200, 7698572, 20.5, batb=[[0, 1.90, 50.0]]),  # back only
    ]
    snap = R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    assert R.book_exclusion_reason(snap) == R.DERIVATIVE_ONE_SIDED_AT_F0


def test_crossed_at_f0_refuses() -> None:
    mid = "1.1"
    stream = [
        _md(mid, 100),
        _rc(mid, 200, 7698572, 20.5, batb=[[0, 2.00, 50.0]], batl=[[0, 1.90, 40.0]]),
    ]
    snap = R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    assert R.book_exclusion_reason(snap) == R.DERIVATIVE_CROSSED_AT_F0


def test_empty_book_at_f0_refuses() -> None:
    mid = "1.1"
    stream = [_md(mid, 100), _rc(mid, 200, 7698572, 20.5, ltp=0.0, tv=0.0)]  # no batb/batl
    snap = R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    assert R.book_exclusion_reason(snap) == R.DERIVATIVE_EMPTY_AT_F0


def test_clean_two_sided_book_passes() -> None:
    snap = R.reconstruct_as_of(_two_sided_stream(), "1.1", cutoff_ms=1000)
    assert R.book_exclusion_reason(snap) is None


# ------------------------------------------------------------------------ sync / age
def test_quote_age_seconds_uses_latest_pre_cutoff_update() -> None:
    mid = "1.1"
    stream = _two_sided_stream(mid)  # latest pre-cutoff pt = 300
    snap = R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    assert R.quote_age_seconds(snap) == pytest.approx(0.7)


# ---------------------------------------------------------------------- book quality
def test_book_quality_reports_spread_sizes_and_depth() -> None:
    snap = R.reconstruct_as_of(_two_sided_stream(), "1.1", cutoff_ms=1000)
    bq = R.book_quality(snap)
    assert bq.two_sided_line_count >= 1
    assert bq.best_back_size_max == 50.0
    assert bq.traded_volume_total == pytest.approx(950.0)
    assert bq.min_spread_ticks is not None


# --------------------------------------------------------------- no-outcome contract
def test_snapshot_has_no_outcome_field() -> None:
    snap = R.reconstruct_as_of(_two_sided_stream(), "1.1", cutoff_ms=1000)
    banned = {"winner", "result", "settled", "settled_time", "pnl", "profit", "loss",
              "outcome", "won", "runner_result", "bsp", "close", "closing"}
    fields = set()
    for obj in (snap, snap.quotes[0]):
        fields |= {f.lower() for f in vars(obj)} if hasattr(obj, "__dict__") else set()
        fields |= {f.name.lower() for f in getattr(type(obj), "__dataclass_fields__", {}).values()}
    assert not (fields & banned), f"outcome-shaped field present: {fields & banned}"


# ------------------------------------------------------------------------ determinism
def test_reconstruction_is_deterministic_and_row_order_invariant() -> None:
    mid = "1.1"
    stream = _two_sided_stream(mid)
    a = R.reconstruct_as_of(stream, mid, cutoff_ms=1000)
    b = R.reconstruct_as_of(list(reversed(stream)), mid, cutoff_ms=1000)
    assert repr(a) == repr(b)
