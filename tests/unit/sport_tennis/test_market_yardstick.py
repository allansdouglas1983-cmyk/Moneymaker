"""F0 market yardstick (Stage 2B §2): COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE decision
policy (W=60s, L=300s) + normalized two-player market probability from the committed
book. Synthetic timelines only. F0 reads prices/market state; winners, settlement,
P&L, CLV and model returns are structurally absent from its input type."""
from __future__ import annotations

import pytest

from sport_tennis.market_yardstick import (
    DWELL_SECONDS,
    MAX_NOMINAL_LEAD_SECONDS,
    BookLevel,
    CommitRefusalReason,
    MarketTimelineEvent,
    commit_once_decision,
    market_probabilities_from_book,
)

pytestmark = [pytest.mark.spec("SPEC-036")]

_M = 60_000  # ms per minute


def ev(pt_s: int, mt_s: int, status: str = "OPEN", inplay: bool = False,
       backs: dict[int, tuple[int, int]] | None = None,
       lays: dict[int, tuple[int, int]] | None = None) -> MarketTimelineEvent:
    return MarketTimelineEvent(
        pt_ms=pt_s * 1000,
        market_time_ms=mt_s * 1000,
        status=status,
        inplay=inplay,
        best_back_by_selection=backs or {1: (55, 1000), 2: (137, 1000)},  # ticks 1.56 / 5.4-ish
        best_lay_by_selection=lays or {1: (56, 1000), 2: (145, 1000)},
    )


class TestCommitOnce:
    def test_commits_at_first_stable_crossing_inside_lead(self) -> None:
        # marketTime 1000s; events publish a stable schedule from t=0.
        tl = [ev(0, 1000), ev(500, 1000), ev(800, 1000), ev(900, 1000)]
        d = commit_once_decision(tl, first_inplay_pt_ms=1_000_000)
        assert d.committed
        # inside-lead from t=700 (remaining 300s); dwell 60s already satisfied
        # (quiet since t=0) -> commit at the first event state covering t>=700.
        assert d.commit_pt_ms == 700_000
        assert d.market_time_ms_at_commit == 1_000_000
        assert d.decision_digest is not None and d.book_state_digest is not None
        assert d.decision_digest.startswith("sha256:") and d.book_state_digest.startswith("sha256:")

    def test_revision_during_dwell_resets_dwell(self) -> None:
        # schedule revised at t=680 (inside what would be the dwell run-up):
        # quiet-clock restarts; commit no earlier than 680+60=740.
        tl = [ev(0, 1000), ev(680, 1050), ev(750, 1050), ev(900, 1050)]
        d = commit_once_decision(tl, first_inplay_pt_ms=1_100_000)
        assert d.committed
        assert d.commit_pt_ms is not None and d.commit_pt_ms >= 740_000
        assert d.market_time_ms_at_commit == 1_050_000

    def test_commit_once_holds_through_later_revisions(self) -> None:
        tl = [ev(0, 1000), ev(800, 1000), ev(850, 2000), ev(900, 2000)]  # revision AFTER commit t=700
        d = commit_once_decision(tl, first_inplay_pt_ms=2_000_000)
        assert d.committed and d.commit_pt_ms == 700_000
        assert d.post_commit_revision_count == 1  # recorded, never re-decided

    def test_suspended_at_candidate_defers_to_reopen(self) -> None:
        tl = [ev(0, 1000), ev(600, 1000, status="SUSPENDED"), ev(760, 1000, status="OPEN"), ev(900, 1000)]
        d = commit_once_decision(tl, first_inplay_pt_ms=1_000_000)
        assert d.committed and d.commit_pt_ms == 760_000

    def test_never_inside_lead_refuses(self) -> None:
        # goes in-play before remaining <= 300s is ever quiet+open
        tl = [ev(0, 1000)]
        d = commit_once_decision(tl, first_inplay_pt_ms=600_000)
        assert not d.committed
        assert d.refusal_reason is CommitRefusalReason.NO_VALID_COMMIT_WINDOW

    def test_no_two_sided_book_at_commit_refuses(self) -> None:
        tl = [ev(0, 1000, lays={1: (56, 1000)})]  # selection 2 has no lay
        d = commit_once_decision(tl, first_inplay_pt_ms=1_000_000)
        assert not d.committed
        assert d.refusal_reason is CommitRefusalReason.NO_TWO_SIDED_BOOK_AT_COMMIT

    def test_deterministic_and_input_order_independent_of_trailing_events(self) -> None:
        tl = [ev(0, 1000), ev(500, 1000), ev(900, 1000)]
        a = commit_once_decision(tl, first_inplay_pt_ms=1_000_000)
        b = commit_once_decision(list(tl), first_inplay_pt_ms=1_000_000)
        assert a == b


class TestMarketProbabilities:
    def test_normalized_two_player_probabilities(self) -> None:
        p = market_probabilities_from_book(
            {1: BookLevel(back_tick=55, lay_tick=56), 2: BookLevel(back_tick=137, lay_tick=145)}
        )
        assert set(p) == {1, 2}
        assert abs(sum(p.values()) - 1.0) < 1e-12
        assert p[1] > p[2]  # shorter odds => higher probability

    def test_two_selections_required(self) -> None:
        with pytest.raises(ValueError):
            market_probabilities_from_book({1: BookLevel(back_tick=55, lay_tick=56)})


def test_frozen_constants() -> None:
    assert DWELL_SECONDS == 60
    assert MAX_NOMINAL_LEAD_SECONDS == 300
