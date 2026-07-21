"""Cross-market feasibility audit — as-of-F0 derivative reconstruction (STAGE3-0002
§6/§7/§8; audit code version xmarket-audit-v1).

The leakage-critical core. A derivative sibling's book state is rebuilt ONLY from stream
messages whose publish_time (``pt``) is <= the frozen F0 decision timestamp
(``commit_pt_ms``). No later, substitute, closing, or in-play state may enter; a later
message can never fill an earlier missing state. Betfair commits F0 pre-off, so the
reconstructed state is pre-settlement: no winner/result exists yet to read, and the
snapshot type below carries NO outcome / settlement / P&L field by construction (§16).

Audit-only: this reads market prices/book (permitted — fields_permitted_to_read.market_stream)
but NEVER outcomes, settlement, BSP, or any result-derived field. Import-quarantined from
l5_decision / l5b_risk / l6_broker. No latent-model equation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

AUDIT_CODE_VERSION = "xmarket-audit-v1"

# Exclusion reasons (subset consumed here) — must match specs/programme/cross-market-audit-v1.yaml
NO_STATE_AT_OR_BEFORE_F0_TIMESTAMP = "NO_STATE_AT_OR_BEFORE_F0_TIMESTAMP"
DERIVATIVE_IN_PLAY_AT_F0 = "DERIVATIVE_IN_PLAY_AT_F0"
DERIVATIVE_SUSPENDED_AT_F0 = "DERIVATIVE_SUSPENDED_AT_F0"
DERIVATIVE_ONE_SIDED_AT_F0 = "DERIVATIVE_ONE_SIDED_AT_F0"
DERIVATIVE_CROSSED_AT_F0 = "DERIVATIVE_CROSSED_AT_F0"
DERIVATIVE_EMPTY_AT_F0 = "DERIVATIVE_EMPTY_AT_F0"


@dataclass
class _Slot:
    """Mutable per-(id,hc) best-of-book accumulator during replay."""

    bb_price: float | None = None
    bb_size: float | None = None
    bl_price: float | None = None
    bl_size: float | None = None
    back_levels: int = 0
    lay_levels: int = 0
    tv: float = 0.0
    last_pt: int = -1


class ReconstructionRefusal(Exception):
    """Reconstruction cannot proceed — carries a reason from the exclusion vocabulary."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


@dataclass(frozen=True)
class SelectionQuote:
    """Best-of-book for one (selection_id, line) at the F0 timestamp. Outcome-free."""

    selection_id: int
    line: float | None
    best_back_price: float | None
    best_back_size: float | None
    best_lay_price: float | None
    best_lay_size: float | None
    back_levels: int
    lay_levels: int
    traded_volume: float
    last_update_pt: int


@dataclass(frozen=True)
class AsOfSnapshot:
    """The derivative's reconstructed book as-of the F0 decision timestamp. NO outcome,
    winner, settlement, BSP, or P&L field is representable here (§16)."""

    market_id: str
    event_id: str | None
    market_type: str | None
    status: str
    in_play: bool
    cross_matching: bool | None
    number_of_active_runners: int | None
    market_time_ms: int | None
    cutoff_ms: int
    latest_message_pt: int
    quotes: tuple[SelectionQuote, ...]


@dataclass(frozen=True)
class BookQuality:
    """Outcome-blind book-quality summary (§8)."""

    two_sided_line_count: int
    priced_selection_count: int
    min_spread_ticks: int | None
    min_spread_bps: float | None
    best_back_size_max: float | None
    best_lay_size_max: float | None
    back_depth_max: int
    lay_depth_max: int
    traded_volume_total: float


def _best_level(ladder: object) -> tuple[float | None, float | None, int]:
    """Return (best_price, best_size, level_count) from a Betfair batb/batl ladder
    ([[level, price, size], ...]); level 0 is best. A zero/absent size is not a price."""
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
                      cutoff_ms: int) -> AsOfSnapshot:
    """Replay ``messages`` for ``market_id``, applying ONLY those with pt <= cutoff_ms, and
    return the as-of-F0 snapshot. Raises ReconstructionRefusal(NO_STATE_...) if no in-scope
    message for this market exists at/before the cutoff."""
    status = "OPEN"
    in_play = False
    cross_matching: bool | None = None
    num_active: int | None = None
    market_time_ms: int | None = None
    event_id: str | None = None
    market_type: str | None = None
    have_definition = False
    latest_pt = -1
    # per (id, hc): mutable best-of-book accumulators
    book: dict[tuple[int, float | None], _Slot] = {}

    for msg in messages:
        pt = msg.get("pt")
        if not isinstance(pt, int):
            continue
        if pt > cutoff_ms:
            continue  # strictly no state after the F0 timestamp
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
                num_active = md.get("numberOfActiveRunners", num_active)
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
                    slot.tv = float(tv)
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
            selection_id=sel, line=line,
            best_back_price=v.bb_price, best_back_size=v.bb_size,
            best_lay_price=v.bl_price, best_lay_size=v.bl_size,
            back_levels=v.back_levels, lay_levels=v.lay_levels,
            traded_volume=v.tv, last_update_pt=v.last_pt,
        )
        for (sel, line), v in sorted(book.items(), key=lambda kv: (kv[0][0], kv[0][1] if kv[0][1] is not None else -1.0))
    )
    return AsOfSnapshot(
        market_id=market_id, event_id=event_id, market_type=market_type,
        status=status, in_play=in_play, cross_matching=cross_matching,
        number_of_active_runners=num_active, market_time_ms=market_time_ms,
        cutoff_ms=cutoff_ms, latest_message_pt=latest_pt, quotes=quotes,
    )


def _two_sided(q: SelectionQuote) -> bool:
    return q.best_back_price is not None and q.best_lay_price is not None


def _crossed(q: SelectionQuote) -> bool:
    # best back price >= best lay price is a crossed/locked book (normally back < lay)
    return (q.best_back_price is not None and q.best_lay_price is not None
            and q.best_back_price >= q.best_lay_price)


def book_exclusion_reason(snap: AsOfSnapshot) -> str | None:
    """Return the exclusion reason for the derivative's F0 book, or None if usable.

    Precedence: in-play, then non-OPEN, then empty, then one-sided, then all-crossed. A
    market is usable if at least one selection is two-sided and not crossed."""
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


def quote_age_seconds(snap: AsOfSnapshot) -> float:
    """Seconds between the latest pre-cutoff book update and the F0 decision timestamp."""
    return (snap.cutoff_ms - snap.latest_message_pt) / 1000.0


# ------------------------------------------------------------------- canonical ladder
# Betfair price ladder (SPEC-053). Used ONLY to express a book spread in integer ticks for
# a diagnostic book-quality metric; no price is ever represented as a float index here.
def _ladder_prices() -> list[float]:
    out: list[float] = []
    for lo, hi, step in [(1.01, 2.0, 0.01), (2.0, 3.0, 0.02), (3.0, 4.0, 0.05),
                         (4.0, 6.0, 0.1), (6.0, 10.0, 0.2), (10.0, 20.0, 0.5),
                         (20.0, 30.0, 1.0), (30.0, 50.0, 2.0), (50.0, 100.0, 5.0),
                         (100.0, 1000.0, 10.0)]:
        # integer stepping to avoid float drift
        n = round((hi - lo) / step)
        for i in range(n):
            out.append(round(lo + i * step, 2))
    out.append(1000.0)
    return out


_LADDER = _ladder_prices()
_LADDER_INDEX = {round(p, 2): i for i, p in enumerate(_LADDER)}


def _tick_index(price: float) -> int | None:
    return _LADDER_INDEX.get(round(price, 2))


def book_quality(snap: AsOfSnapshot) -> BookQuality:
    """Outcome-blind book-quality summary over the two-sided, non-crossed selections."""
    two_sided = [q for q in snap.quotes if _two_sided(q) and not _crossed(q)]
    priced = [q for q in snap.quotes if q.best_back_price is not None or q.best_lay_price is not None]
    min_ticks: int | None = None
    min_bps: float | None = None
    for q in two_sided:
        assert q.best_back_price is not None and q.best_lay_price is not None
        bi, li = _tick_index(q.best_back_price), _tick_index(q.best_lay_price)
        if bi is not None and li is not None:
            ticks = li - bi
            if min_ticks is None or ticks < min_ticks:
                min_ticks = ticks
        mid = (q.best_back_price + q.best_lay_price) / 2.0
        if mid > 0:
            bps = (q.best_lay_price - q.best_back_price) / mid * 10000.0
            if min_bps is None or bps < min_bps:
                min_bps = bps
    bb_sizes = [q.best_back_size for q in two_sided if q.best_back_size is not None]
    bl_sizes = [q.best_lay_size for q in two_sided if q.best_lay_size is not None]
    return BookQuality(
        two_sided_line_count=len(two_sided),
        priced_selection_count=len(priced),
        min_spread_ticks=min_ticks,
        min_spread_bps=min_bps,
        best_back_size_max=max(bb_sizes) if bb_sizes else None,
        best_lay_size_max=max(bl_sizes) if bl_sizes else None,
        back_depth_max=max((q.back_levels for q in snap.quotes), default=0),
        lay_depth_max=max((q.lay_levels for q in snap.quotes), default=0),
        traded_volume_total=sum(q.traded_volume for q in snap.quotes),
    )
