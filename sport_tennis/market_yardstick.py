"""F0 market yardstick — COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE decision policy + the
governed market probability (Stage 2B §2; specs/programme/reschedule-policy-v1.yaml).

Pure policy over a market's pre-off timeline. Constants are the FROZEN founder
declarations (W = 60 s dwell, L = 300 s maximum nominal lead). The input type carries
prices/schedule/status ONLY — winners, settlement, P&L, CLV and model returns are
structurally absent, so F0 cannot read them.

Decision semantics (frozen rules 1–6; F-13 execution retries are out of scope here):
at any time t the market may commit its ONE decision iff status is OPEN, pre-in-play,
remaining = marketTime_as_known_at_t − t ∈ [0, L], and no marketTime revision occurred
in the trailing W seconds (a revision during the dwell resets the dwell). The first
such t commits; later revisions never re-decide. If no such t exists before the off,
the market records an explicit refusal reason. Both outcomes are decisions downstream
(BET/ABSTAIN is the decision layer's business, never F0's).

Market probability: the frozen info-price definition (specs/prices/info-price-v2.yaml,
scope betfair MATCH_ODDS): per selection raw_p = (1/best_back + 1/best_lay)/2 on the
canonical ladder, normalised to unit sum over the two active selections.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
from typing import Mapping, Sequence

from price_contracts.ladder import price_of

__all__ = [
    "DWELL_SECONDS",
    "MAX_NOMINAL_LEAD_SECONDS",
    "MarketTimelineEvent",
    "BookLevel",
    "CommitRefusalReason",
    "CommittedDecision",
    "commit_once_decision",
    "market_probabilities_from_book",
]

DWELL_SECONDS = 60
MAX_NOMINAL_LEAD_SECONDS = 300
_W_MS = DWELL_SECONDS * 1000
_L_MS = MAX_NOMINAL_LEAD_SECONDS * 1000


@dataclass(frozen=True)
class MarketTimelineEvent:
    """One pre-off observation: publish time, schedule as known then, status, and the
    best displayed book per selection ((tick, size_minor) pairs). No outcome field is
    representable here."""

    pt_ms: int
    market_time_ms: int
    status: str
    inplay: bool
    best_back_by_selection: Mapping[int, tuple[int, int]]
    best_lay_by_selection: Mapping[int, tuple[int, int]]


@dataclass(frozen=True)
class BookLevel:
    back_tick: int
    lay_tick: int


@unique
class CommitRefusalReason(Enum):
    NO_VALID_COMMIT_WINDOW = "NO_VALID_COMMIT_WINDOW"
    NO_TWO_SIDED_BOOK_AT_COMMIT = "NO_TWO_SIDED_BOOK_AT_COMMIT"
    EMPTY_TIMELINE = "EMPTY_TIMELINE"


@dataclass(frozen=True)
class CommittedDecision:
    committed: bool
    commit_pt_ms: int | None
    market_time_ms_at_commit: int | None
    book_at_commit: Mapping[int, BookLevel] | None
    decision_digest: str | None
    book_state_digest: str | None
    post_commit_revision_count: int
    refusal_reason: CommitRefusalReason | None


def _digest(payload: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def commit_once_decision(
    timeline: Sequence[MarketTimelineEvent], *, first_inplay_pt_ms: int | None
) -> CommittedDecision:
    """Deterministic pure function of the timeline (events in publish order) and the
    off boundary. Exactly one commit, or one typed refusal."""
    if not timeline:
        return CommittedDecision(False, None, None, None, None, None, 0, CommitRefusalReason.EMPTY_TIMELINE)

    # revision epochs: (revision_pt, market_time) whenever marketTime changes
    revisions: list[tuple[int, int]] = []
    for e in timeline:
        if not revisions or revisions[-1][1] != e.market_time_ms:
            revisions.append((e.pt_ms, e.market_time_ms))

    end_cap = first_inplay_pt_ms  # decisions are pre-off only

    for k, e in enumerate(timeline):
        t_start = e.pt_ms
        t_end = timeline[k + 1].pt_ms if k + 1 < len(timeline) else (end_cap if end_cap is not None else e.pt_ms + 1)
        if end_cap is not None:
            t_end = min(t_end, end_cap)
        if t_end <= t_start:
            continue
        if e.status != "OPEN" or e.inplay:
            continue
        m = e.market_time_ms
        last_rev_pt = max(pt for pt, _mt in revisions if pt <= t_start)
        # earliest admissible t in [t_start, t_end): dwell elapsed, inside lead, pre-nominal
        t = max(t_start, last_rev_pt + _W_MS, m - _L_MS)
        if t >= t_end:
            continue
        if m - t < 0 or m - t > _L_MS:
            continue
        # commit at t with the book of event e (the state in force at t)
        book: dict[int, BookLevel] = {}
        two_sided = set(e.best_back_by_selection) & set(e.best_lay_by_selection)
        if len(two_sided) != 2 or set(e.best_back_by_selection) != set(e.best_lay_by_selection):
            return CommittedDecision(
                False, None, None, None, None, None, 0, CommitRefusalReason.NO_TWO_SIDED_BOOK_AT_COMMIT
            )
        for sid in sorted(two_sided):
            book[sid] = BookLevel(
                back_tick=e.best_back_by_selection[sid][0], lay_tick=e.best_lay_by_selection[sid][0]
            )
        book_payload = {
            str(sid): {
                "back": list(e.best_back_by_selection[sid]),
                "lay": list(e.best_lay_by_selection[sid]),
            }
            for sid in sorted(two_sided)
        }
        book_digest = _digest(book_payload)
        decision_digest = _digest(
            {"commit_pt_ms": t, "market_time_ms": m, "policy": "COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE",
             "W_s": DWELL_SECONDS, "L_s": MAX_NOMINAL_LEAD_SECONDS, "book": book_payload}
        )
        post_revs = sum(1 for pt, _mt in revisions if pt > t)
        return CommittedDecision(True, t, m, book, decision_digest, book_digest, post_revs, None)

    return CommittedDecision(False, None, None, None, None, None, 0, CommitRefusalReason.NO_VALID_COMMIT_WINDOW)


def market_probabilities_from_book(book: Mapping[int, BookLevel]) -> Mapping[int, float]:
    """Normalized two-player implied-midpoint probabilities (info-price-v2 formula)."""
    if len(book) != 2:
        raise ValueError(f"tennis MATCH_ODDS market probability needs exactly 2 selections, got {len(book)}")
    mids: dict[int, Decimal] = {}
    for sid, lvl in book.items():
        back = price_of(lvl.back_tick)
        lay = price_of(lvl.lay_tick)
        mids[sid] = (Decimal(1) / back + Decimal(1) / lay) / 2
    total = sum(mids.values())
    return {sid: float(m / total) for sid, m in mids.items()}
