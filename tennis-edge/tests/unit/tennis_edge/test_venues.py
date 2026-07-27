"""The registry's job is to stop an unreachable column being reported as money.

Every one of these tests exists because the failure it guards against already happened: a
results table was published led by Pinnacle, which has not accepted a UK customer since
2016, and by the panel maximum, which is arithmetic rather than a counterparty. Nothing in
the data says so, so it has to be said here and checked.
"""
from __future__ import annotations

import pytest

from tennis_edge.corpus import OddsQuotes
from tennis_edge.venues import (VENUES, Access, Kind, benchmark_keys, by_key, parsed_keys,
                                uk_settlement_keys)


def test_every_key_and_column_is_unique() -> None:
    """Two venues sharing a key would silently overwrite each other's prices."""
    keys = [v.key for v in VENUES]
    columns = [v.column for v in VENUES]
    assert len(set(keys)) == len(keys)
    assert len(set(columns)) == len(columns)


def test_uk_settlement_and_benchmarks_partition_the_parsed_columns() -> None:
    """A parsed column is either bettable from here or a labelled diagnostic. No third
    category, and nothing may fall through the gap into being quoted without a label."""
    uk, bench = set(uk_settlement_keys()), set(benchmark_keys())
    assert uk.isdisjoint(bench)
    assert uk | bench == set(parsed_keys())


def test_nothing_in_the_benchmark_list_is_reachable_from_the_uk() -> None:
    for key in benchmark_keys():
        assert by_key(key).access is not Access.UK_OPEN


def test_every_settlement_venue_is_a_real_place_a_uk_resident_can_reach() -> None:
    """The whole point. A synthetic column is not somewhere anyone can place a bet, and a
    venue closed to the UK is not somewhere *this* account can."""
    for key in uk_settlement_keys():
        venue = by_key(key)
        assert venue.access is Access.UK_OPEN
        assert venue.kind is not Kind.SYNTHETIC
        assert venue.restricts_winners is not None


def test_pinnacle_and_the_panel_maximum_are_never_settlement_venues() -> None:
    """Named explicitly because these two are the ones that were wrongly headlined."""
    assert "pinnacle" not in uk_settlement_keys()
    assert "max" not in uk_settlement_keys()
    assert by_key("pinnacle").access is Access.CLOSED_TO_UK
    assert by_key("max").access is Access.NOT_A_VENUE


def test_the_exchange_is_the_only_venue_that_cannot_limit_a_winner() -> None:
    """The reason Betfair decides the project and a Bet365 return has an expiry date."""
    unlimited = [v.key for v in VENUES
                 if v.access is Access.UK_OPEN and v.restricts_winners is False]
    assert unlimited == ["betfair"]
    assert by_key("betfair").kind is Kind.EXCHANGE


def test_a_synthetic_column_has_no_opinion_on_restricting_winners() -> None:
    """There is no account, so the question is not merely False — it does not apply."""
    for venue in VENUES:
        if venue.kind is Kind.SYNTHETIC:
            assert venue.restricts_winners is None


def test_every_parsed_venue_has_somewhere_to_put_its_prices() -> None:
    """A registry entry marked parsed with no OddsQuotes field would raise deep inside the
    loader on the first workbook, having already read half the corpus."""
    quotes = OddsQuotes()
    for key in parsed_keys():
        assert hasattr(quotes, f"{key}_a") and hasattr(quotes, f"{key}_b")


def test_every_venue_explains_itself() -> None:
    """A reachability verdict with no stated reason is a verdict nobody can check."""
    for venue in VENUES:
        assert venue.note.strip() and venue.note.strip().endswith(".")
        assert venue.name.strip()


def test_an_unknown_key_raises_rather_than_returning_a_default() -> None:
    with pytest.raises(KeyError):
        by_key("definitely-not-a-bookmaker")
