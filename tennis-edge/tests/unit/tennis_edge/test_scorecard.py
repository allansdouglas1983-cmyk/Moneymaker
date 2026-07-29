"""The site grades its own served predictions (TE-0017 S6, scorecard half).

The predictions table is write-only today, so the full serving path has never been scored
end to end. These tests pin the reference grading logic the deployment mirrors: the
deterministic vintage policy (last pre-match row, declared before any outcome was seen),
the name reduction that lets a user-typed "Carlos Alcaraz" meet the corpus's
"Alcaraz C.", append-only settling, and typed exclusions for everything that cannot be
graded — visible, never silently dropped.
"""
from __future__ import annotations

import datetime as dt

from tennis_edge.scorecard import (
    GradeOutcome,
    grade,
    grade_key,
    last_pre_match,
)


class TestGradeKey:
    def test_the_two_name_forms_converge(self) -> None:
        """The whole point: what the user types and what the corpus stores must reduce
        to the same key, or nothing ever grades."""
        assert grade_key("Carlos Alcaraz") == grade_key("Alcaraz C.")
        assert grade_key("Jannik Sinner") == grade_key("Sinner J.")

    def test_diacritics_and_case_do_not_split_a_player(self) -> None:
        assert grade_key("Novak DJOKOVIC") == grade_key("Djokovic N.")

    def test_an_unreducible_name_is_none_never_a_guess(self) -> None:
        assert grade_key("") is None


class TestLastPreMatch:
    def test_the_latest_pre_match_prediction_is_the_graded_one(self) -> None:
        """Declared vintage policy: the LAST row created on or before the match date.
        Never select-the-best-vintage — the choice is made by the clock, not the result."""
        rows = [
            {"match_key": "k", "match_date": "2026-07-30",
             "created_at": "2026-07-28T10:00:00Z", "probability_a": 0.60},
            {"match_key": "k", "match_date": "2026-07-30",
             "created_at": "2026-07-29T09:00:00Z", "probability_a": 0.55},
        ]
        assert last_pre_match(rows)["k"]["probability_a"] == 0.55

    def test_a_post_match_prediction_never_grades(self) -> None:
        """A row minted after the match date knows too much; it is excluded from grading
        entirely rather than quietly out-competing the honest one."""
        rows = [
            {"match_key": "k", "match_date": "2026-07-30",
             "created_at": "2026-07-31T08:00:00Z", "probability_a": 0.99},
        ]
        assert last_pre_match(rows) == {}


def _prediction(**overrides: object) -> dict:
    row = {
        "match_key": "2026-07-30|ATP|Alcaraz C.|Sinner J.",
        "match_date": "2026-07-30", "tour": "ATP",
        "player_a": "Carlos Alcaraz", "player_b": "Jannik Sinner",
        "created_at": "2026-07-29T09:00:00Z",
        "probability_a": 0.55, "market_probability_a": 0.50,
    }
    row.update(overrides)
    return row


def _result(**overrides: object) -> dict:
    row = {
        "match_date": "2026-07-30", "tour": "ATP",
        "key_a": grade_key("Alcaraz C."), "key_b": grade_key("Sinner J."),
        "winner_key": grade_key("Alcaraz C."), "completion": "COMPLETED",
    }
    row.update(overrides)
    return row


class TestGrade:
    def test_a_completed_match_settles_the_last_pre_match_prediction(self) -> None:
        settled, exclusions = grade([_prediction()], [_result()])
        assert len(settled) == 1 and not exclusions
        row = settled[0]
        assert row["outcome"] is GradeOutcome.GRADED
        assert row["winner_side"] == "A"
        # -log(0.55) < -log(0.50): the model beat the market on this one.
        assert row["model_log_loss"] < row["market_log_loss"]

    def test_settling_never_mutates_the_prediction(self) -> None:
        prediction = _prediction()
        before = dict(prediction)
        grade([prediction], [_result()])
        assert prediction == before

    def test_a_future_match_is_pending_not_missing(self) -> None:
        settled, exclusions = grade([_prediction()], [])
        assert not settled
        assert exclusions == {GradeOutcome.PENDING_RESULT: 1}

    def test_an_unmatchable_name_is_a_typed_exclusion(self) -> None:
        settled, exclusions = grade(
            [_prediction(player_a="Zzz Qqq Xx-Yy XYZ.")],
            [_result()])
        assert not settled
        assert exclusions == {GradeOutcome.UNMATCHED_NAME: 1}

    def test_a_walkover_is_not_gradeable_and_says_so(self) -> None:
        settled, exclusions = grade([_prediction()],
                                    [_result(completion="WALKOVER",
                                             winner_key=None)])
        assert not settled
        assert exclusions == {GradeOutcome.NOT_GRADEABLE: 1}

    def test_a_retirement_with_a_winner_grades(self) -> None:
        """Tennis-Data records the winner of a retirement; forecast quality is about the
        outcome, not Betfair's void rules — this is the scorecard, not settlement."""
        settled, _exclusions = grade([_prediction()],
                                     [_result(completion="RETIRED")])
        assert len(settled) == 1

    def test_the_reversed_orientation_still_grades_correctly(self) -> None:
        """The user may type the players the other way round from the corpus row."""
        settled, _ = grade(
            [_prediction(player_a="Jannik Sinner", player_b="Carlos Alcaraz",
                         probability_a=0.45, market_probability_a=0.50)],
            [_result()])
        assert settled[0]["winner_side"] == "B"

    def test_grading_twice_produces_the_same_rows_not_more(self) -> None:
        """Append-only means idempotent: the caller dedups by match_key, and grade()
        must be deterministic so replaying the backfill proves nothing changed."""
        first = grade([_prediction()], [_result()])
        second = grade([_prediction()], [_result()])
        assert first == second


def test_grade_key_vectors_for_the_typescript_port() -> None:
    """The exact pairs the Deno test replays; a port divergence splits players silently."""
    for typed, corpus in [("Carlos Alcaraz", "Alcaraz C."),
                          ("Iga Swiatek", "Swiatek I."),
                          ("Frances Tiafoe", "Tiafoe F.")]:
        assert grade_key(typed) is not None
        assert grade_key(typed) == grade_key(corpus)
