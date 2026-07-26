"""Corpus tests. The provider stores rows winner-first, so the loader's neutral
re-orientation is the single guard standing between us and a model that has been handed the
answer. These tests exist to make that guard impossible to break silently."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import openpyxl
import pytest

from tennis_edge.corpus import Completion, is_odds_column, load_corpus

_HEADER = [
    "ATP", "Location", "Tournament", "Date", "Series", "Court", "Surface", "Round", "Best of",
    "Winner", "Loser", "WRank", "LRank", "WPts", "LPts",
    "W1", "L1", "W2", "L2", "W3", "L3", "W4", "L4", "W5", "L5", "Wsets", "Lsets", "Comment",
    "B365W", "B365L", "PSW", "PSL", "MaxW", "MaxL", "AvgW", "AvgL", "BFEW", "BFEL",
]


def _row(*, date: dt.date, winner: str, loser: str, comment: str = "Completed",
         psw: float | None = 1.5, psl: float | None = 2.6) -> list[object]:
    return [
        1, "Testville", "Test Open", dt.datetime(date.year, date.month, date.day),
        "ATP250", "Outdoor", "Hard", "1st Round", 3,
        winner, loser, 10, 40, 2000, 800,
        6, 3, 6, 4, None, None, None, None, None, None, 2, 0, comment,
        1.5, 2.5, psw, psl, 1.6, 2.7, 1.45, 2.4, 1.55, 2.65,
    ]


def _write(tmp_path: Path, rows: list[list[object]], name: str = "atp-2024.xlsx") -> Path:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(_HEADER)
    for row in rows:
        sheet.append(row)
    path = tmp_path / name
    workbook.save(path)
    return tmp_path


def test_neutral_orientation_does_not_encode_the_winner(tmp_path: Path) -> None:
    """Alice beating Bob and Bob beating Alice must produce the SAME player ordering and
    differ only in winner_is_a. If ordering tracked the result, every feature built from
    player_a would silently know who won."""
    root = _write(tmp_path, [
        _row(date=dt.date(2024, 1, 1), winner="Alice", loser="Bob"),
        _row(date=dt.date(2024, 1, 2), winner="Bob", loser="Alice"),
    ])
    matches, _ = load_corpus(root)
    assert [m.player_a for m in matches] == ["Alice", "Alice"]
    assert [m.player_b for m in matches] == ["Bob", "Bob"]
    assert [m.winner_is_a for m in matches] == [True, False]


def test_ranks_points_and_odds_follow_the_player_not_the_result(tmp_path: Path) -> None:
    """When the loser sorts first, every per-player column must be swapped with them."""
    root = _write(tmp_path, [_row(date=dt.date(2024, 1, 1), winner="Zoe", loser="Adam")])
    (match,), _ = load_corpus(root)
    assert match.player_a == "Adam" and match.winner_is_a is False
    # The row's "loser" columns belong to Adam, who is player_a here.
    assert match.rank_a == 40 and match.rank_b == 10
    assert match.points_a == 800 and match.points_b == 2000
    assert match.odds.pair("pinnacle") == (2.6, 1.5)
    assert match.games_a == 7 and match.games_b == 12
    assert match.sets_a == 0 and match.sets_b == 2


def test_winner_and_loser_properties_agree_with_the_flag(tmp_path: Path) -> None:
    root = _write(tmp_path, [_row(date=dt.date(2024, 1, 1), winner="Zoe", loser="Adam")])
    (match,), _ = load_corpus(root)
    assert match.winner == "Zoe" and match.loser == "Adam"


def test_retirements_are_excluded_by_default_and_counted(tmp_path: Path) -> None:
    root = _write(tmp_path, [
        _row(date=dt.date(2024, 1, 1), winner="Alice", loser="Bob"),
        _row(date=dt.date(2024, 1, 2), winner="Cara", loser="Dan", comment="Retired"),
    ])
    matches, stats = load_corpus(root)
    assert len(matches) == 1
    assert stats.exclusions.get("not_completed_retired") == 1


def test_retirements_are_available_when_asked_for(tmp_path: Path) -> None:
    root = _write(tmp_path, [
        _row(date=dt.date(2024, 1, 2), winner="Cara", loser="Dan", comment="Retired"),
    ])
    matches, _ = load_corpus(root, completed_only=False)
    assert matches[0].completion is Completion.RETIRED
    assert matches[0].completed is False


def test_a_pair_day_with_contradictory_winners_is_dropped_entirely(tmp_path: Path) -> None:
    """A source contradiction is not resolved by preference — both rows go."""
    root = _write(tmp_path, [
        _row(date=dt.date(2024, 1, 1), winner="Alice", loser="Bob"),
        _row(date=dt.date(2024, 1, 1), winner="Bob", loser="Alice"),
    ])
    matches, stats = load_corpus(root)
    assert matches == ()
    assert len(stats.winner_conflicts) == 1


def test_an_exact_duplicate_collapses_to_one_row(tmp_path: Path) -> None:
    root = _write(tmp_path, [
        _row(date=dt.date(2024, 1, 1), winner="Alice", loser="Bob"),
        _row(date=dt.date(2024, 1, 1), winner="Alice", loser="Bob"),
    ])
    matches, stats = load_corpus(root)
    assert len(matches) == 1 and stats.duplicates_dropped == 1


def test_missing_prices_are_left_missing_never_imputed(tmp_path: Path) -> None:
    root = _write(tmp_path, [
        _row(date=dt.date(2024, 1, 1), winner="Alice", loser="Bob", psw=None, psl=None),
    ])
    (match,), _ = load_corpus(root)
    assert match.odds.pair("pinnacle") is None
    assert match.odds.pinnacle_a is None


def test_a_one_sided_price_is_treated_as_no_price(tmp_path: Path) -> None:
    root = _write(tmp_path, [
        _row(date=dt.date(2024, 1, 1), winner="Alice", loser="Bob", psw=1.5, psl=None),
    ])
    (match,), _ = load_corpus(root)
    assert match.odds.pair("pinnacle") is None


def test_matches_come_back_in_chronological_order(tmp_path: Path) -> None:
    root = _write(tmp_path, [
        _row(date=dt.date(2024, 3, 1), winner="Alice", loser="Bob"),
        _row(date=dt.date(2024, 1, 1), winner="Cara", loser="Dan"),
        _row(date=dt.date(2024, 2, 1), winner="Eve", loser="Finn"),
    ])
    matches, _ = load_corpus(root)
    assert [m.match_date for m in matches] == sorted(m.match_date for m in matches)


def test_odds_columns_are_identified_for_the_feature_ban_list() -> None:
    for name in ("B365W", "PSL", "MaxW", "AvgL", "BFEW", "EXW"):
        assert is_odds_column(name)
    for name in ("Winner", "WRank", "Surface", "Round", "W1", "Wsets"):
        assert not is_odds_column(name)


def test_an_empty_directory_is_an_error_not_an_empty_corpus(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_corpus(tmp_path)
