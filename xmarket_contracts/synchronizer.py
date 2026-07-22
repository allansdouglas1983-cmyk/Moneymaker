"""PROMOTED as-of-F0 synchronizer + two-sided validator + quote-age (STAGE3-0004 §10).

Hardened production re-home of the leakage-critical audit core, independent of
``research.xmarket``. A derivative's book is rebuilt ONLY from stream messages whose
publish_time (``pt``) is <= the frozen F0 decision timestamp; no post-F0 message enters and a
later message cannot backfill an earlier missing side. This module captures the RAW book
(best back/lay price+size, priced-level counts, matched volume, last update) and validates
usability. It computes NO book-quality arithmetic (spread/interval stay research-only /
future coherence) and reads NO outcome. Import-quarantined from execution and research.xmarket.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

NO_STATE_AT_OR_BEFORE_F0_TIMESTAMP = "NO_STATE_AT_OR_BEFORE_F0_TIMESTAMP"
DERIVATIVE_IN_PLAY_AT_F0 = "DERIVATIVE_IN_PLAY_AT_F0"
DERIVATIVE_SUSPENDED_AT_F0 = "DERIVATIVE_SUSPENDED_AT_F0"
DERIVATIVE_ONE_SIDED_AT_F0 = "DERIVATIVE_ONE_SIDED_AT_F0"
DERIVATIVE_CROSSED_AT_F0 = "DERIVATIVE_CROSSED_AT_F0"
DERIVATIVE_EMPTY_AT_F0 = "DERIVATIVE_EMPTY_AT_F0"


class ReconstructionRefusal(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


@dataclass
class _Slot:
    bb_price: float | None = None
    bb_size: float | None = None
    bl_price: float | None = None
    bl_size: float | None = None
    back_levels: int = 0
    lay_levels: int = 0
    matched_volume: float = 0.0
    last_pt: int = -1


@dataclass(frozen=True)
class SelectionQuote:
    """Raw best-of-book for one (selection_id, line) at F0. Outcome-free; no arithmetic."""

    selection_id: int
    line: float | None
    best_back_price: float | None
    best_back_size: float | None
    best_lay_price: float | None
    best_lay_size: float | None
    back_levels: int
    lay_levels: int
    matched_volume: float
    last_update_pt: int


@dataclass(frozen=True)
class AsOfBook:
    """A derivative's reconstructed raw book as-of the F0 decision timestamp. No outcome."""

    market_id: str
    event_id: str | None
    market_type: str | None
    status: str
    in_play: bool
    cross_matching: bool | None
    market_time_ms: int | None
    cutoff_ms: int
    latest_message_pt: int
    quotes: tuple[SelectionQuote, ...]


def _best_level(ladder: object) -> tuple[float | None, float | None, int]:
    if not isinstance(ladder, list) or not ladder:
        return None, None, 0
    priced = [e for e in ladder if isinstance(e, list) and len(e) == 3
              and isinstance(e[1], (int, float)) and not isinstance(e[1], bool)
              and isinstance(e[2], (int, float)) and not isinstance(e[2], bool) and e[2] > 0]
    if not priced:
        return None, None, 0
    best = min(priced, key=lambda e: e[0])
    return float(best[1]), float(best[2]), len(priced)


def reconstruct_as_of(messages: Iterable[Mapping[str, Any]], market_id: str,
                      cutoff_ms: int) -> AsOfBook:
    status = "OPEN"
    in_play = False
    cross_matching: bool | None = None
    market_time_ms: int | None = None
    event_id: str | None = None
    market_type: str | None = None
    have_definition = False
    latest_pt = -1
    book: dict[tuple[int, float | None], _Slot] = {}

    for msg in messages:
        pt = msg.get("pt")
        if not isinstance(pt, int) or pt > cutoff_ms:
            continue
        applied = False
        for mc in msg.get("mc") or []:
            if mc.get("id") != market_id:
                continue
            md = mc.get("marketDefinition")
            if md is not None:
                have_definition = True
                status = md.get("status", status)
                in_play = bool(md.get("inPlay", in_play))
                cross_matching = md.get("crossMatching", cross_matching)
                market_time_ms = md.get("marketTime", market_time_ms)
                event_id = md.get("eventId", event_id)
                market_type = md.get("marketType", market_type)
                applied = True
            for rc in mc.get("rc") or []:
                sel = rc.get("id")
                if not isinstance(sel, int):
                    continue
                hc = rc.get("hc")
                line = float(hc) if isinstance(hc, (int, float)) else None
                slot = book.setdefault((sel, line), _Slot())
                if "batb" in rc:
                    slot.bb_price, slot.bb_size, slot.back_levels = _best_level(rc.get("batb"))
                if "batl" in rc:
                    slot.bl_price, slot.bl_size, slot.lay_levels = _best_level(rc.get("batl"))
                tv = rc.get("tv")
                if isinstance(tv, (int, float)) and not isinstance(tv, bool):
                    slot.matched_volume = float(tv)
                slot.last_pt = pt
                applied = True
        if applied and pt > latest_pt:
            latest_pt = pt

    if not have_definition and not book:
        raise ReconstructionRefusal(NO_STATE_AT_OR_BEFORE_F0_TIMESTAMP,
                                    f"market {market_id} has no state at/before {cutoff_ms}")
    if latest_pt < 0:
        raise ReconstructionRefusal(NO_STATE_AT_OR_BEFORE_F0_TIMESTAMP,
                                    f"market {market_id} produced no in-scope update")

    quotes = tuple(
        SelectionQuote(
            selection_id=sel, line=line, best_back_price=v.bb_price, best_back_size=v.bb_size,
            best_lay_price=v.bl_price, best_lay_size=v.bl_size, back_levels=v.back_levels,
            lay_levels=v.lay_levels, matched_volume=v.matched_volume, last_update_pt=v.last_pt,
        )
        for (sel, line), v in sorted(book.items(),
                                     key=lambda kv: (kv[0][0], kv[0][1] if kv[0][1] is not None else -1.0))
    )
    return AsOfBook(
        market_id=market_id, event_id=event_id, market_type=market_type, status=status,
        in_play=in_play, cross_matching=cross_matching, market_time_ms=market_time_ms,
        cutoff_ms=cutoff_ms, latest_message_pt=latest_pt, quotes=quotes,
    )


def _two_sided(q: SelectionQuote) -> bool:
    return q.best_back_price is not None and q.best_lay_price is not None


def _crossed(q: SelectionQuote) -> bool:
    return (q.best_back_price is not None and q.best_lay_price is not None
            and q.best_back_price >= q.best_lay_price)


def book_exclusion_reason(snap: AsOfBook) -> str | None:
    """Usability of the derivative's F0 book, or None if usable. Precedence: in-play ->
    non-OPEN -> empty -> one-sided -> all-crossed."""
    if snap.in_play:
        return DERIVATIVE_IN_PLAY_AT_F0
    if snap.status != "OPEN":
        return DERIVATIVE_SUSPENDED_AT_F0
    priced = [q for q in snap.quotes if q.best_back_price is not None or q.best_lay_price is not None]
    if not priced:
        return DERIVATIVE_EMPTY_AT_F0
    two_sided = [q for q in snap.quotes if _two_sided(q)]
    if not two_sided:
        return DERIVATIVE_ONE_SIDED_AT_F0
    if all(_crossed(q) for q in two_sided):
        return DERIVATIVE_CROSSED_AT_F0
    return None


def quote_age_seconds(snap: AsOfBook) -> float:
    return (snap.cutoff_ms - snap.latest_message_pt) / 1000.0
