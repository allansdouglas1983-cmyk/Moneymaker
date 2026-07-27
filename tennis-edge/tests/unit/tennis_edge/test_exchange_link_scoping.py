"""The name bridge has to be asked about one day's players, not a decade of world tennis.

Betfair ran markets on every tennis event there is — ITF, juniors, exhibitions — while the
corpus carries main-tour ATP and WTA. Building one bridge over the whole archive puts 2,982
corpus names against 14,788 Betfair names, and surname-plus-initial collisions that do not
exist on the main tour appear in droves: "Cilic M." is unique among ATP players and ambiguous
once every ITF player on earth is in the pool. The bridge refuses ambiguity, correctly, and
the join collapsed to 200 links out of 405,487 markets with 3,131 homonym refusals.

Scoping the bridge to a single day fixes it without loosening a single rule: same module,
same normalisation, same refusals, asked over a population where the question has an answer.
Measured on the ten busiest days, resolution went from 12.3% to 93.0%.

These tests pin that the scoping is real — that a name resolvable on its own day is NOT
resolved by a same-named player from a different one, which is the whole danger of the
change. A wrong link scores one match's price against another match's outcome and nothing
downstream can detect it.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from tennis_edge.betfair import LtpObservation, MarketHistory, Runner
from tennis_edge.corpus import Completion, Match, OddsQuotes
from tennis_edge.exchange import PriceSource
from tennis_edge.exchange_link import LinkOutcome, link_markets


def _match(date: dt.date, a: str, b: str, *, tour: str = "ATP") -> Match:
    return Match(
        match_date=date, tour=tour, tournament="Test Open", location="Testville",
        tier="ATP250", court="Outdoor", surface="Hard", round_name="1st Round",
        best_of=3, player_a=a, player_b=b, winner_is_a=True,
        rank_a=10, rank_b=40, points_a=2000, points_b=800,
        games_a=12, games_b=7, sets_a=2, sets_b=0,
        completion=Completion.COMPLETED,
        odds=OddsQuotes(b365_a=1.5, b365_b=2.5), source_file="test",
    )


def _market(date: dt.date, a: str, b: str, *, market_id: str = "1.1") -> MarketHistory:
    off = int(dt.datetime.combine(date, dt.time(12, 0),
                                  tzinfo=dt.timezone.utc).timestamp() * 1000)
    return MarketHistory(
        market_id=market_id, event_id="9", event_name=f"{a} v {b}",
        market_type="MATCH_ODDS", country_code="GB", market_time_ms=off,
        runners=(Runner(selection_id=1, name=a, status="ACTIVE", sort_priority=1),
                 Runner(selection_id=2, name=b, status="ACTIVE", sort_priority=2)),
        observations=(
            LtpObservation(publish_time_ms=off - 900_000, selection_id=1,
                           price=Decimal("2.0")),
            LtpObservation(publish_time_ms=off - 900_000, selection_id=2,
                           price=Decimal("2.0")),
        ),
        went_in_play=False,
    )


def _link(markets: list[MarketHistory], matches: list[Match]) -> object:
    return link_markets(markets, matches, use_ladder=False,
                        source=PriceSource.LAST_TRADED)


DAY = dt.date(2019, 6, 3)
OTHER_DAY = dt.date(2019, 9, 9)


class TestPerDayScoping:
    def test_a_name_unique_on_its_own_day_resolves(self) -> None:
        """The base case the global bridge was failing."""
        result = _link([_market(DAY, "Marin Cilic", "Ricardas Berankis")],
                       [_match(DAY, "Berankis R.", "Cilic M.")])
        assert len(result.linked) == 1  # type: ignore[attr-defined]

    def test_two_betfair_players_on_different_days_do_not_poison_each_other(self) -> None:
        """This is the failure that cost 3,131 names and it is cross-DAY, not same-day.

        Tennis-Data abbreviates to surname plus initial, so "Marin Cilic" and "Mate Cilic"
        are both "Cilic M.". Over a decade of archive both appear, one corpus identity maps
        to two Betfair names, and the bridge refuses HOMONYM_MULTIPLE_BETFAIR — killing
        both. They never play on the same day: scoped per day each is unambiguous, and both
        markets link.
        """
        matches = [
            _match(DAY, "Berankis R.", "Cilic M."),
            _match(OTHER_DAY, "Cilic M.", "Zverev A."),
        ]
        markets = [
            _market(DAY, "Marin Cilic", "Ricardas Berankis", market_id="1.1"),
            _market(OTHER_DAY, "Mate Cilic", "Alexander Zverev", market_id="1.2"),
        ]
        result = _link(markets, matches)
        assert len(result.linked) == 2  # type: ignore[attr-defined]

    def test_a_genuine_same_day_ambiguity_still_refuses(self) -> None:
        """Scoping must not become guessing. Two DIFFERENT Betfair players normalising to
        one corpus identity on the SAME day is real ambiguity and must still refuse — a
        wrong link scores one match's price against another's outcome, undetectably."""
        matches = [_match(DAY, "Berankis R.", "Cilic M.")]
        markets = [
            _market(DAY, "Marin Cilic", "Ricardas Berankis", market_id="1.1"),
            _market(DAY, "Mate Cilic", "Ricardas Berankis", market_id="1.2"),
        ]
        result = _link(markets, matches)
        outcomes = {e.outcome for e in result.excluded}  # type: ignore[attr-defined]
        assert LinkOutcome.UNRESOLVED_NAME in outcomes
        assert len(result.linked) == 0  # type: ignore[attr-defined]

    def test_a_market_whose_players_are_not_in_the_corpus_is_excluded_not_guessed(
            self) -> None:
        """Most of the archive is ITF and junior tennis the corpus never carried. Those
        must land in the exclusion ledger, not be forced onto whoever is nearest."""
        result = _link([_market(DAY, "Some Junior", "Another Junior")],
                       [_match(DAY, "Berankis R.", "Cilic M.")])
        assert len(result.linked) == 0  # type: ignore[attr-defined]
        assert all(e.outcome is LinkOutcome.UNRESOLVED_NAME
                   for e in result.excluded)  # type: ignore[attr-defined]

    def test_the_date_tolerance_still_applies_across_midnight(self) -> None:
        """A late match in one time zone lands on the next UTC date. Scoping per day must
        not undo the one-day tolerance that exists for exactly that reason."""
        result = _link([_market(DAY, "Marin Cilic", "Ricardas Berankis")],
                       [_match(DAY + dt.timedelta(days=1), "Berankis R.", "Cilic M.")])
        assert len(result.linked) == 1  # type: ignore[attr-defined]

    def test_every_market_is_linked_or_excluded_exactly_once(self) -> None:
        """The denominator discipline. Universe in equals linked plus excluded, always."""
        markets = [
            _market(DAY, "Marin Cilic", "Ricardas Berankis", market_id="1.1"),
            _market(DAY, "Some Junior", "Another Junior", market_id="1.2"),
            _market(OTHER_DAY, "Marin Cilic", "Alexander Zverev", market_id="1.3"),
        ]
        matches = [_match(DAY, "Berankis R.", "Cilic M.")]
        result = _link(markets, matches)
        assert result.universe == len(markets)  # type: ignore[attr-defined]
        assert (len(result.linked) + len(result.excluded)  # type: ignore[attr-defined]
                == len(markets))
