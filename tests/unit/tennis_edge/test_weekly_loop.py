"""Weekly-loop tests: the append-only ledger, the frozen policy, and the two properties
that make an unattended job trustworthy — it cannot see the future, and running it twice
changes nothing.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from tennis_edge import weekly
from tennis_edge.corpus import Completion, CorpusStats, Match, OddsQuotes
from tennis_edge.ledger import Ledger, LedgerRow, match_key, summarise
from tennis_edge.policy import (
    MODEL_SHRINKAGE,
    TIP_MARGIN,
    Status,
    decide,
    policy_digest,
)
from tennis_edge.ratings import RatingEngine
from tennis_edge.refresh import Vintage
from tennis_edge.serve_stats import ServeEstimator


def _match(day: int, *, winner_is_a: bool = True,
           pinnacle: tuple[float, float] | None = (2.0, 2.0),
           player_a: str = "Alice", player_b: str = "Bob",
           month: int = 6) -> Match:
    return Match(
        match_date=dt.date(2025, month, day), tour="ATP", tournament="T", location="L",
        tier="ATP250", court="Outdoor", surface="Hard", round_name="R1", best_of=3,
        player_a=player_a, player_b=player_b, winner_is_a=winner_is_a,
        rank_a=10, rank_b=20, points_a=1000, points_b=500,
        games_a=12, games_b=7, sets_a=2, sets_b=0, completion=Completion.COMPLETED,
        odds=OddsQuotes(pinnacle_a=None if pinnacle is None else pinnacle[0],
                        pinnacle_b=None if pinnacle is None else pinnacle[1]),
        source_file="test",
    )


def _row(key: str, *, status: str = "NO_BET", odds: float | None = None,
         side: str | None = None, winner_is_a: bool = True,
         market: float | None = 0.5) -> LedgerRow:
    return LedgerRow(
        match_key=key, match_date="2025-06-01", tour="ATP", player_a="Alice",
        player_b="Bob", tier="ATP250", surface="Hard", status=status, book="pinnacle",
        market_probability_a=market, model_probability_a=market,
        blended_probability_a=market, quoted_odds=odds, side=side,
        expected_value=None, reason="test", winner_is_a=winner_is_a,
        policy_version="v", policy_digest="d", code_commit="c", data_vintage="v1",
        recorded_utc="2025-06-02T00:00:00Z",
    )


# ------------------------------------------------------------------------ ledger


def test_a_row_survives_a_round_trip(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append([_row("k1")])
    (back,) = list(ledger.rows())
    assert back == _row("k1")


def test_appending_the_same_match_twice_is_a_no_op(tmp_path: Path) -> None:
    """The property that makes the job safe to re-run, and safe for a Routine to double-fire."""
    ledger = Ledger(tmp_path / "l.jsonl")
    assert ledger.append([_row("k1"), _row("k2")]) == 2
    assert ledger.append([_row("k1"), _row("k2")]) == 0
    assert len(list(ledger.rows())) == 2


def test_a_partial_rerun_appends_only_what_is_new(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append([_row("k1")])
    assert ledger.append([_row("k1"), _row("k2")]) == 1
    assert {r.match_key for r in ledger.rows()} == {"k1", "k2"}


def test_earlier_lines_are_never_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    ledger = Ledger(path)
    ledger.append([_row("k1")])
    before = path.read_text()
    ledger.append([_row("k2")])
    assert path.read_text().startswith(before), "append-only means the prefix is preserved"


def test_a_reader_sees_rows_written_by_a_different_instance(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    Ledger(path).append([_row("k1")])
    assert Ledger(path).contains("k1")


def test_match_keys_separate_tours_and_dates() -> None:
    base = match_key(dt.date(2025, 6, 1), "ATP", "Alice", "Bob")
    assert base != match_key(dt.date(2025, 6, 2), "ATP", "Alice", "Bob")
    assert base != match_key(dt.date(2025, 6, 1), "WTA", "Alice", "Bob")


def test_realised_return_charges_commission_only_on_a_win() -> None:
    winner = _row("k", odds=3.0, side="A", winner_is_a=True)
    loser = _row("k", odds=3.0, side="A", winner_is_a=False)
    assert winner.realised_return == pytest.approx(2.0 * 0.98)
    assert loser.realised_return == pytest.approx(-1.0)


def test_a_row_with_no_recommendation_has_no_return() -> None:
    assert _row("k").realised_return is None


def test_summary_scores_market_and_model_on_the_same_matches() -> None:
    rows = [_row(f"k{i}", market=0.6, winner_is_a=i % 2 == 0) for i in range(10)]
    rows.append(_row("kx", market=None))          # unpriced: excluded from both
    summary = summarise(rows)
    assert summary.rows == 11 and summary.scored == 10
    assert summary.market_log_loss is not None and summary.model_log_loss is not None


# ------------------------------------------------------------------------ policy


def test_the_digest_changes_when_a_constant_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ledger row must be traceable to the exact rule that produced it, so a silently
    edited threshold has to produce a different digest."""
    before = policy_digest()
    monkeypatch.setattr("tennis_edge.policy.TIP_MARGIN", TIP_MARGIN + 0.01)
    assert policy_digest() != before


def test_no_price_is_blocked_not_guessed() -> None:
    decision = decide(_match(1, pinnacle=None), 0.9)
    assert decision.status is Status.BLOCKED
    assert decision.market_probability_a is None


def test_no_model_view_leaves_the_market_standing_alone() -> None:
    decision = decide(_match(1), None)
    assert decision.status is Status.NO_BET
    assert decision.blended_probability_a == decision.market_probability_a


def test_agreement_with_the_market_produces_no_bet() -> None:
    decision = decide(_match(1), 0.5)
    assert decision.status is Status.NO_BET


def test_the_model_is_shrunk_hard_toward_the_market() -> None:
    """b1 measured at -0.027 and +0.056 across the model layers, so the blend must stay far
    closer to the price than to the model however confident the model is."""
    decision = decide(_match(1), 0.99)
    assert decision.market_probability_a is not None
    assert decision.blended_probability_a is not None
    assert decision.blended_probability_a < 0.65, "a 0.99 model view must not dominate"
    assert decision.blended_probability_a > decision.market_probability_a
    assert MODEL_SHRINKAGE <= 0.2, "the shrinkage constant must stay conservative"


def test_a_large_disagreement_at_a_positive_price_recommends() -> None:
    decision = decide(_match(1, pinnacle=(3.0, 1.4)), 0.99)
    assert decision.status in (Status.RECOMMEND_A, Status.RECOMMEND_B)
    assert decision.quoted_odds is not None and decision.side is not None
    assert decision.expected_value is not None and decision.expected_value > 0.0


def test_a_recommendation_requires_positive_expectation_after_commission() -> None:
    """A disagreement alone is not enough — it has to survive the cost of placing the bet."""
    decision = decide(_match(1, pinnacle=(1.01, 40.0)), 0.99)
    assert decision.status is not Status.RECOMMEND_A


def test_only_recommendations_carry_a_price_and_a_side() -> None:
    quiet = decide(_match(1), 0.5)
    assert quiet.quoted_odds is None and quiet.side is None


def test_no_status_authorises_real_money() -> None:
    """The vocabulary is deliberately closed: nothing in it means 'place this bet'."""
    assert {s.value for s in Status} == {
        "RECOMMEND_A", "RECOMMEND_B", "WATCH", "NO_BET", "BLOCKED",
    }


# -------------------------------------------------------------------- the weekly run


def _synthetic_corpus() -> tuple[Match, ...]:
    """Ten days of play in which P1 appears twice on every single day.

    The repeated same-day appearance is the point: if the job ever updated ratings
    match-by-match instead of day-by-day, P1's second match of the day would be priced from
    state that had already seen P1's first, and the counting test below would catch it.
    """
    matches: list[Match] = []
    for day in range(1, 11):
        for a, b in (("P1", "P2"), ("P3", "P4"), ("P5", "P6"), ("P1", "P3")):
            matches.append(_match(day, player_a=a, player_b=b, winner_is_a=day % 2 == 0))
    return tuple(matches)


def _stub_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, matches: tuple[Match, ...]
) -> None:
    """Point the job at an in-memory corpus, with no network and no archive."""
    vintage = Vintage(vintage_id="vintage-test", root=tmp_path, provenance=())
    stats = CorpusStats(files_read=1, rows_seen=len(matches), rows_kept=len(matches),
                        exclusions={}, duplicates_dropped=0, winner_conflicts=())
    monkeypatch.setattr(weekly, "latest_vintage", lambda _root: vintage)
    monkeypatch.setattr(weekly, "load_corpus", lambda _root: (matches, stats))
    monkeypatch.setattr(weekly, "load_matches", lambda **_kwargs: ())


def test_a_decision_never_sees_a_result_from_its_own_day_or_later(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The no-lookahead property, asserted on the state that actually priced each match.

    At the moment a match is priced, each player's observed match count must equal exactly
    the number of matches they played on *strictly earlier* days. One extra means a result
    from the same day — or later — leaked into the decision that preceded it.
    """
    matches = _synthetic_corpus()
    _stub_environment(monkeypatch, tmp_path, matches)

    seen_at_decision: list[tuple[Match, int, int]] = []
    real_model_view = weekly._model_view

    def spy(engine: RatingEngine, estimator: ServeEstimator,
            match: Match, day: dt.date) -> float | None:
        seen_at_decision.append((
            match,
            engine.matches_played(match.tour, match.player_a),
            engine.matches_played(match.tour, match.player_b),
        ))
        return real_model_view(engine, estimator, match, day)

    monkeypatch.setattr(weekly, "_model_view", spy)
    weekly.run(ledger_path=tmp_path / "l.jsonl", data_root=tmp_path, do_refresh=False,
               dry_run=True, ledger_from=dt.date(2025, 1, 1))

    def played_strictly_before(player: str, when: dt.date) -> int:
        return sum(1 for m in matches
                   if m.match_date < when and player in (m.player_a, m.player_b))

    assert seen_at_decision, "the spy must actually have been exercised"
    for match, count_a, count_b in seen_at_decision:
        when = match.match_date
        assert count_a == played_strictly_before(match.player_a, when), match
        assert count_b == played_strictly_before(match.player_b, when), match


def test_a_second_run_over_the_same_vintage_appends_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """What makes the job safe to leave unattended on a schedule."""
    matches = _synthetic_corpus()
    _stub_environment(monkeypatch, tmp_path, matches)
    ledger_path = tmp_path / "l.jsonl"

    first = weekly.run(ledger_path=ledger_path, data_root=tmp_path, do_refresh=False,
                       ledger_from=dt.date(2025, 1, 1))
    assert first.appended == len(matches)

    second = weekly.run(ledger_path=ledger_path, data_root=tmp_path, do_refresh=False,
                        ledger_from=dt.date(2025, 1, 1))
    assert second.evaluated == 0 and second.appended == 0
    assert second.summary.rows == len(matches)


def test_a_dry_run_writes_nothing_but_still_reports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    matches = _synthetic_corpus()
    _stub_environment(monkeypatch, tmp_path, matches)
    ledger_path = tmp_path / "l.jsonl"

    result = weekly.run(ledger_path=ledger_path, data_root=tmp_path, do_refresh=False,
                        dry_run=True, ledger_from=dt.date(2025, 1, 1))
    assert not ledger_path.exists()
    assert result.evaluated == len(matches) and result.appended == 0
    assert result.summary.rows == len(matches), "a dry run reports what it would write"


def test_matches_before_the_ledger_start_build_state_without_being_recorded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """History earlier than the ledger window is corpus, not evidence — it trains the
    ratings but must not appear as a row."""
    matches = _synthetic_corpus()
    _stub_environment(monkeypatch, tmp_path, matches)

    result = weekly.run(ledger_path=tmp_path / "l.jsonl", data_root=tmp_path,
                        do_refresh=False, dry_run=True, ledger_from=dt.date(2025, 6, 6))
    recorded = {m for m in matches if m.match_date >= dt.date(2025, 6, 6)}
    assert result.evaluated == len(recorded)
