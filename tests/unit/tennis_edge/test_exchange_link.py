"""Linking Betfair markets to corpus matches, and the exchange benchmark.

Betfair names players in full ("Carlos Alcaraz"); Tennis-Data abbreviates
("Alcaraz C."). Every exchange measurement depends on that join being right, and a join
that guesses is worse than one that refuses — a wrong link silently scores one match's
price against another match's outcome.

So every failure mode here is a **typed exclusion**, never a dropped row: the denominator
is the thing that makes a benchmark honest.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from tennis_edge.betfair import (
    LadderLevel,
    LadderObservation,
    LtpObservation,
    MarketHistory,
    Runner,
)
from tennis_edge.corpus import Completion, Match, OddsQuotes
from tennis_edge.exchange_link import (
    LinkOutcome,
    exchange_benchmark,
    link_markets,
)

A, B = 111, 222


def _off(day: int = 15, hour: int = 14) -> int:
    return int(dt.datetime(2025, 6, day, hour, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _history(
    *, names: tuple[str, str] = ("Carlos Alcaraz", "Jannik Sinner"),
    prices: tuple[str, str] | None = ("2.0", "2.0"), day: int = 15,
    market_id: str = "1.1",
) -> MarketHistory:
    off = _off(day)
    observations: tuple[LtpObservation, ...] = ()
    ladders: tuple[LadderObservation, ...] = ()
    if prices is not None:
        # A realistic market carries BOTH: last trades and a two-sided ladder. The linker
        # prices from the ladder by default, because that is the crossable price.
        observations = tuple(
            LtpObservation(publish_time_ms=off - 1_800_000, selection_id=sid,
                           price=Decimal(p))
            for sid, p in ((A, prices[0]), (B, prices[1]))
        )
        ladders = tuple(
            LadderObservation(publish_time_ms=off - 1_800_000, selection_id=sid,
                              best_back=LadderLevel(Decimal(p), Decimal("120")),
                              best_lay=None)
            for sid, p in ((A, prices[0]), (B, prices[1]))
        )
    return MarketHistory(
        market_id=market_id, event_id="9", event_name=" v ".join(names),
        market_type="MATCH_ODDS", country_code="GB", market_time_ms=off,
        runners=(Runner(A, names[0], "ACTIVE", 1), Runner(B, names[1], "ACTIVE", 2)),
        observations=observations, ladders=ladders, went_in_play=False,
    )


def _match(*, a: str = "Alcaraz C.", b: str = "Sinner J.", day: int = 15,
           winner_is_a: bool = True) -> Match:
    return Match(
        match_date=dt.date(2025, 6, day), tour="ATP", tournament="T", location="L",
        tier="Grand Slam", court="Outdoor", surface="Grass", round_name="F", best_of=5,
        player_a=a, player_b=b, winner_is_a=winner_is_a,
        rank_a=1, rank_b=2, points_a=9000, points_b=8000,
        games_a=18, games_b=12, sets_a=3, sets_b=1, completion=Completion.COMPLETED,
        odds=OddsQuotes(pinnacle_a=1.9, pinnacle_b=2.0), source_file="test",
    )


# ------------------------------------------------------------------ linking


def test_a_full_name_links_to_an_abbreviated_one() -> None:
    result = link_markets((_history(),), (_match(),))
    assert len(result.linked) == 1
    linked = result.linked[0]
    assert linked.match.player_a == "Alcaraz C."
    assert linked.selection_for_player_a == A


def test_orientation_follows_the_corpus_not_the_market() -> None:
    """The corpus is name-ordered; Betfair's runner order is its own. The link must map
    selections onto the corpus's A/B, or every probability is silently transposed."""
    swapped = _history(names=("Jannik Sinner", "Carlos Alcaraz"))
    result = link_markets((swapped,), (_match(),))
    assert result.linked[0].selection_for_player_a == B


def test_an_unknown_player_is_an_explicit_exclusion() -> None:
    result = link_markets((_history(names=("Nobody Here", "Jannik Sinner")),), (_match(),))
    assert result.linked == ()
    assert result.excluded[0].outcome is LinkOutcome.UNRESOLVED_NAME


def test_a_market_with_no_matching_date_is_an_explicit_exclusion() -> None:
    result = link_markets((_history(day=20),), (_match(day=15),))
    assert result.linked == ()
    assert result.excluded[0].outcome is LinkOutcome.NO_MATCH_ON_DATE


def test_a_match_a_day_either_side_still_links() -> None:
    """A late match in one time zone lands on the next UTC date. One day of tolerance is
    the smallest window that covers it."""
    assert len(link_markets((_history(day=16),), (_match(day=15),)).linked) == 1


def test_two_candidate_matches_refuse_rather_than_pick() -> None:
    """The same pair on adjacent days is ambiguous. Guessing here would score a price
    against the wrong outcome, which is worse than losing the row."""
    result = link_markets((_history(day=15),), (_match(day=15), _match(day=16)))
    assert result.linked == ()
    assert result.excluded[0].outcome is LinkOutcome.AMBIGUOUS_MATCH


def test_one_market_never_claims_two_matches() -> None:
    result = link_markets((_history(),), (_match(), _match(a="Sinner J.", b="Zverev A.")))
    assert len(result.linked) == 1


def test_every_market_is_accounted_for() -> None:
    """Universe in = linked + typed exclusions. A row never simply disappears."""
    markets = (_history(), _history(day=20, market_id="1.2"),
               _history(names=("Nobody Here", "X Y"), market_id="1.3"))
    result = link_markets(markets, (_match(),))
    assert len(result.linked) + len(result.excluded) == len(markets)


def test_a_market_with_no_price_is_excluded_with_a_reason() -> None:
    result = link_markets((_history(prices=None),), (_match(),))
    assert result.excluded[0].outcome is LinkOutcome.NO_PRICE_AT_HORIZON


# ------------------------------------------------------------------ benchmark


def test_the_benchmark_scores_exchange_and_bookmaker_on_the_same_matches() -> None:
    """Comparing the exchange on one set of matches and the bookmaker on another is not a
    comparison. Both must be scored on exactly the linked set."""
    result = link_markets((_history(prices=("1.5", "3.0")),), (_match(),))
    report = exchange_benchmark(result)
    assert report.scored == 1
    assert report.exchange_log_loss is not None
    assert report.bookmaker_log_loss is not None


def test_a_confident_correct_exchange_price_scores_better() -> None:
    right = exchange_benchmark(
        link_markets((_history(prices=("1.2", "6.0")),), (_match(winner_is_a=True),))
    )
    wrong = exchange_benchmark(
        link_markets((_history(prices=("1.2", "6.0")),), (_match(winner_is_a=False),))
    )
    assert right.exchange_log_loss is not None and wrong.exchange_log_loss is not None
    assert right.exchange_log_loss < wrong.exchange_log_loss


def test_the_exchange_overround_is_reported() -> None:
    report = exchange_benchmark(link_markets((_history(),), (_match(),)))
    assert report.mean_exchange_overround == pytest.approx(1.0)
    assert report.crossable is True, "the default price is the one you could have taken"
    assert report.median_size == pytest.approx(120.0)


def test_last_traded_mode_is_marked_as_an_artefact() -> None:
    """A last-traded overround must never be presented as a cost of trading."""
    report = exchange_benchmark(
        link_markets((_history(),), (_match(),), use_ladder=False)
    )
    assert report.crossable is False and report.median_size is None


def test_an_empty_link_scores_nothing_rather_than_zero() -> None:
    report = exchange_benchmark(link_markets((), (_match(),)))
    assert report.scored == 0
    assert report.exchange_log_loss is None


def test_the_report_counts_exclusions_by_reason() -> None:
    markets = (_history(day=20), _history(names=("Nobody Here", "X Y"), market_id="1.3"))
    report = exchange_benchmark(link_markets(markets, (_match(),)))
    assert report.exclusions[LinkOutcome.NO_MATCH_ON_DATE.value] == 1
    assert report.exclusions[LinkOutcome.UNRESOLVED_NAME.value] == 1


# ------------------------------------------------------------------ bookmaker fallback


def _match_priced(book: str | None) -> Match:
    quotes = {"pinnacle": OddsQuotes(pinnacle_a=1.9, pinnacle_b=2.0),
              "b365": OddsQuotes(b365_a=1.9, b365_b=2.0),
              None: OddsQuotes()}[book]
    base = _match()
    return Match(**{**base.__dict__, "odds": quotes})


def test_the_benchmark_falls_back_when_the_sharpest_book_is_absent() -> None:
    """Tennis-Data carries no Pinnacle quotes for June 2026 (0 of 761). Hardcoding one book
    silently drops every row; the comparison book is chosen by preference order instead."""
    report = exchange_benchmark(link_markets((_history(),), (_match_priced("b365"),)))
    assert report.scored == 1
    assert report.bookmaker_book == "b365"


def test_the_sharpest_available_book_is_preferred() -> None:
    report = exchange_benchmark(link_markets((_history(),), (_match_priced("pinnacle"),)))
    assert report.bookmaker_book == "pinnacle"


def test_a_linked_row_with_no_bookmaker_price_is_an_explicit_exclusion() -> None:
    """The failure that produced 'scored: 0' from 416 linked markets. A row dropped inside
    the benchmark is invisible; a row excluded by name is not."""
    report = exchange_benchmark(link_markets((_history(),), (_match_priced(None),)))
    assert report.scored == 0
    assert report.exclusions[LinkOutcome.NO_BOOKMAKER_PRICE.value] == 1


def test_linked_and_scored_are_reported_separately() -> None:
    result = link_markets((_history(),), (_match_priced(None),))
    report = exchange_benchmark(result)
    assert report.linked == 1 and report.scored == 0


def test_every_market_is_still_accounted_for_after_scoring() -> None:
    markets = (_history(), _history(day=20, market_id="1.2"))
    report = exchange_benchmark(link_markets(markets, (_match_priced(None),)))
    assert report.scored + sum(report.exclusions.values()) == report.universe
