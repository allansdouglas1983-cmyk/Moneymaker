"""Tests for the fixture list — the front of the chain that did not exist.

Everything downstream of this worked and none of it was reachable without a human writing a
JSON file by hand. A tool you have to hand-feed the day's matches to is a demonstration.

Two sources, one shape. Manual entry stays first-class because it always works and needs no
account, no key and no network. The delayed-key adapter is the automated path and is built
so it can be authenticated later without any downstream change — it produces the same
``Fixture`` objects from the same validation.

The tests are about refusing bad input rather than parsing good input: a fixture with a
missing price, a past date, or a player the state has never seen is a fixture that must not
silently become a prediction.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from tennis_edge.fixtures import (
    FixtureSource,
    load_fixture_file,
    parse_fixture,
)


def payload(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "date": "2026-07-28", "tour": "ATP",
        "player_a": "Sinner J.", "player_b": "Alcaraz C.",
        "surface": "Hard", "best_of": 3, "odds_a": "2.10", "odds_b": "1.85",
    }
    entry.update(overrides)
    return entry


class TestParsing:
    def test_a_complete_entry_parses(self) -> None:
        fixture, source = parse_fixture(payload())
        assert fixture.player_a == "Sinner J."
        assert source is FixtureSource.MANUAL_BETFAIR_UI

    def test_prices_survive_as_exact_decimals(self) -> None:
        """A float literal damages a price before it is ever used."""
        fixture, _source = parse_fixture(payload(odds_a="2.10"))
        assert str(fixture.odds_a) == "2.10"

    def test_the_source_is_recorded_when_given(self) -> None:
        _fixture, source = parse_fixture(payload(source="DELAYED_KEY"))
        assert source is FixtureSource.DELAYED_KEY

    def test_an_unknown_source_is_refused(self) -> None:
        """A source nobody declared cannot be audited later."""
        with pytest.raises(ValueError, match="unknown source"):
            parse_fixture(payload(source="A_MATE_TOLD_ME"))

    def test_a_missing_price_is_refused(self) -> None:
        entry = payload()
        del entry["odds_a"]
        with pytest.raises(ValueError, match="odds_a"):
            parse_fixture(entry)

    def test_a_price_at_or_below_evens_is_refused(self) -> None:
        with pytest.raises(ValueError, match="above 1"):
            parse_fixture(payload(odds_a="1.0"))

    def test_a_non_numeric_price_is_refused(self) -> None:
        with pytest.raises(ValueError, match="not a decimal price"):
            parse_fixture(payload(odds_a="evens"))

    def test_the_same_player_twice_is_refused(self) -> None:
        with pytest.raises(ValueError, match="same player"):
            parse_fixture(payload(player_b="Sinner J."))

    def test_an_unsupported_format_is_refused(self) -> None:
        with pytest.raises(ValueError, match="best_of"):
            parse_fixture(payload(best_of=4))


class TestFile:
    def test_a_file_of_fixtures_loads(self, tmp_path: Path) -> None:
        path = tmp_path / "fixtures.json"
        path.write_text(json.dumps([payload(), payload(player_a="Draper J.")]),
                        encoding="utf-8")
        assert len(load_fixture_file(path)) == 2

    def test_an_empty_file_loads_to_nothing_rather_than_raising(self, tmp_path: Path) -> None:
        """No matches today is an ordinary Tuesday, not an error."""
        path = tmp_path / "fixtures.json"
        path.write_text("[]", encoding="utf-8")
        assert load_fixture_file(path) == []

    def test_one_bad_entry_fails_the_whole_file(self, tmp_path: Path) -> None:
        """Partial acceptance would silently drop a match nobody notices is missing."""
        path = tmp_path / "fixtures.json"
        path.write_text(json.dumps([payload(), payload(odds_b="0")]), encoding="utf-8")
        with pytest.raises(ValueError, match="fixture 2"):
            load_fixture_file(path)

    def test_a_non_list_file_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "fixtures.json"
        path.write_text(json.dumps(payload()), encoding="utf-8")
        with pytest.raises(ValueError, match="list of fixtures"):
            load_fixture_file(path)


class TestDates:
    def test_a_past_fixture_is_refused(self, tmp_path: Path) -> None:
        """A match already played is not a prediction, whatever the model says about it."""
        path = tmp_path / "fixtures.json"
        path.write_text(json.dumps([payload(date="2020-01-01")]), encoding="utf-8")
        with pytest.raises(ValueError, match="already been played"):
            load_fixture_file(path, today=dt.date(2026, 7, 28))

    def test_todays_fixture_is_allowed(self, tmp_path: Path) -> None:
        path = tmp_path / "fixtures.json"
        path.write_text(json.dumps([payload(date="2026-07-28")]), encoding="utf-8")
        assert load_fixture_file(path, today=dt.date(2026, 7, 28))

    def test_the_date_check_is_skipped_when_no_today_is_supplied(self,
                                                                tmp_path: Path) -> None:
        """Reproducing an old prediction is legitimate; doing it by accident is not."""
        path = tmp_path / "fixtures.json"
        path.write_text(json.dumps([payload(date="2020-01-01")]), encoding="utf-8")
        assert load_fixture_file(path)
