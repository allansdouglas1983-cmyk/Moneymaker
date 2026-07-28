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
import json
from decimal import Decimal
from pathlib import Path

import pytest

from price_contracts.ladder import index_of, price_of
from tennis_edge.betfair import (
    LadderLevel,
    LadderObservation,
    LtpObservation,
    MarketHistory,
    Runner,
)
from tennis_edge.corpus import Completion, Match, OddsQuotes
from tennis_edge.exchange_link import (
    LINK_BRIDGE_VERSION,
    LinkOutcome,
    exchange_benchmark,
    link_markets,
)
from tennis_edge.exchange_prices import (
    PRICES_KIND,
    ExchangePrice,
    read_prices,
    write_prices,
)
from tennis_edge.fill_evidence import FillSupport

A, B = 111, 222


def _off(day: int = 15, hour: int = 14, year: int = 2025) -> int:
    return int(dt.datetime(year, 6, day, hour, tzinfo=dt.UTC).timestamp() * 1000)


def _history(
    *, names: tuple[str, str] = ("Carlos Alcaraz", "Jannik Sinner"),
    prices: tuple[str, str] | None = ("2.0", "2.0"), day: int = 15,
    market_id: str = "1.1", year: int = 2025,
    runners: tuple[Runner, ...] | None = None,
) -> MarketHistory:
    off = _off(day, year=year)
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
        # A real book is two-sided: lay sits one tick above back on the canonical ladder.
        # The midpoint estimator needs both sides and refuses without them.
        ladders = tuple(
            LadderObservation(
                publish_time_ms=off - 1_800_000, selection_id=sid,
                best_back=LadderLevel(Decimal(p), Decimal("120")),
                best_lay=LadderLevel(price_of(index_of(Decimal(p)) + 1), Decimal("120")),
            )
            for sid, p in ((A, prices[0]), (B, prices[1]))
        )
    return MarketHistory(
        market_id=market_id, event_id="9", event_name=" v ".join(names),
        market_type="MATCH_ODDS", country_code="GB", market_time_ms=off,
        runners=runners if runners is not None
        else (Runner(A, names[0], "ACTIVE", 1), Runner(B, names[1], "ACTIVE", 2)),
        observations=observations, ladders=ladders, went_in_play=False,
    )


def _match(*, a: str = "Alcaraz C.", b: str = "Sinner J.", day: int = 15,
           winner_is_a: bool = True, tour: str = "ATP") -> Match:
    return Match(
        match_date=dt.date(2025, 6, day), tour=tour, tournament="T", location="L",
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


# ------------------------------------------- relaxed second pass (TE-0018, bridge v2)


def test_a_hyphenated_betfair_name_links_to_its_spaced_corpus_form() -> None:
    """TE-0018 rule class 1: Betfair "Pablo Carreno-Busta" is Tennis-Data "Carreno Busta
    P.". The strict bridge sees two different surnames; on hyphen-relaxed text its own
    split-point rule matches."""
    market = _history(names=("Pablo Carreno-Busta", "Jannik Sinner"))
    result = link_markets((market,), (_match(a="Carreno Busta P."),))
    assert len(result.linked) == 1
    assert result.linked[0].match.player_a == "Carreno Busta P."
    assert result.linked[0].selection_for_player_a == A


def test_a_hyphenated_corpus_name_links_to_its_spaced_betfair_form() -> None:
    """The relaxation applies to BOTH sides: the hyphen can just as well be Tennis-Data's
    ("Carreno-Busta P." against Betfair "Pablo Carreno Busta")."""
    market = _history(names=("Pablo Carreno Busta", "Jannik Sinner"))
    result = link_markets((market,), (_match(a="Carreno-Busta P."),))
    assert len(result.linked) == 1
    assert result.linked[0].match.player_a == "Carreno-Busta P."


def test_an_apostrophe_difference_still_links() -> None:
    """Tennis-Data "O'Connell C." against Betfair "Christopher OConnell": apostrophes are
    removed from both sides before the bridge's own rule is applied."""
    market = _history(names=("Christopher OConnell", "Jannik Sinner"))
    result = link_markets((market,), (_match(a="O'Connell C."),))
    assert len(result.linked) == 1
    assert result.linked[0].match.player_a == "O'Connell C."


def test_a_truncated_double_surname_links_by_token_subset() -> None:
    """TE-0018 rule class 2: Tennis-Data truncates double surnames ("Roberto Bautista
    Agut" is "Bautista R."). Surname tokens a subset of the Betfair tokens after the
    first, plus first-initial equality."""
    market = _history(names=("Roberto Bautista Agut", "Jannik Sinner"))
    result = link_markets((market,), (_match(a="Bautista R."),))
    assert len(result.linked) == 1
    assert result.linked[0].match.player_a == "Bautista R."


def test_twin_initials_resolve_via_the_longest_prefix_of_the_first_name() -> None:
    """The Pliskova twins share a surname and a first initial; Tennis-Data separates them
    only by two-letter initials "Ka."/"Kr.". Within one ±1-day window each Betfair first
    name matches exactly one candidate's initials as its longest prefix."""
    matches = (_match(a="Pliskova Ka.", b="Sabalenka A.", day=15, tour="WTA"),
               _match(a="Pliskova Kr.", b="Gauff C.", day=16, tour="WTA"))
    markets = (
        _history(names=("Karolina Pliskova", "Aryna Sabalenka"), day=15, market_id="1.1"),
        _history(names=("Kristyna Pliskova", "Coco Gauff"), day=16, market_id="1.2"),
    )
    result = link_markets(markets, matches)
    assert len(result.linked) == 2
    by_market = {link.market.market_id: link.match.player_a for link in result.linked}
    assert by_market["1.1"] == "Pliskova Ka."
    assert by_market["1.2"] == "Pliskova Kr."


def test_twins_the_prefix_rule_cannot_separate_are_refused() -> None:
    """Betfair "K. Pliskova" prefixes NEITHER "Ka." nor "Kr.": no unique longest prefix,
    so the pass resolves nothing — a guess here scores the wrong sister's match."""
    matches = (_match(a="Pliskova Ka.", b="Sabalenka A.", day=15, tour="WTA"),
               _match(a="Pliskova Kr.", b="Gauff C.", day=16, tour="WTA"))
    market = _history(names=("K. Pliskova", "Aryna Sabalenka"), day=15)
    result = link_markets((market,), matches)
    assert result.linked == ()
    assert result.excluded[0].outcome is LinkOutcome.UNRESOLVED_NAME


def test_a_strict_bridge_resolution_is_never_overridden_by_the_relaxed_pass() -> None:
    """"Roberto Bautista Agut" resolves strictly to "Bautista Agut R."; the relaxed
    subset rule would also reach "Bautista R." on the same card. The strict resolution
    stands and the relaxed pass never re-asks the question."""
    matches = (_match(a="Bautista Agut R.", b="Sinner J."),
               _match(a="Bautista R.", b="Zverev A."))
    market = _history(names=("Roberto Bautista Agut", "Jannik Sinner"))
    result = link_markets((market,), matches)
    assert len(result.linked) == 1
    assert result.linked[0].match.player_a == "Bautista Agut R."


def test_a_relaxed_candidate_matching_two_corpus_names_resolves_nothing() -> None:
    """"Mirjana Lucic-Baroni" reaches both "Lucic Baroni M." (rule 1) and "Lucic M."
    (rule 2) on the same day card, and identical initials give the twins rule no unique
    longest prefix. Exactly one corpus name or nothing — this is nothing."""
    matches = (_match(a="Lucic M.", b="Williams S.", tour="WTA"),
               _match(a="Lucic Baroni M.", b="Halep S.", tour="WTA"))
    market = _history(names=("Mirjana Lucic-Baroni", "Serena Williams"))
    result = link_markets((market,), matches)
    assert result.linked == ()
    assert result.excluded[0].outcome is LinkOutcome.UNRESOLVED_NAME


# ------------------------------------------------------- typed market-shape exclusions


def test_a_2099_off_date_is_provider_damage_not_a_coverage_gap() -> None:
    """TE-0018 §Junk-2099: test markets and double-listed junk carry 2099 off-times.
    Falling through as NO_MATCH_ON_DATE would conflate data damage with genuine corpus
    coverage gaps."""
    result = link_markets((_history(year=2099),), (_match(),))
    assert result.linked == ()
    assert result.excluded[0].outcome is LinkOutcome.IMPLAUSIBLE_OFF_DATE


def test_a_market_with_one_active_runner_is_typed_not_unresolved() -> None:
    """A walkover-shaped market is not a name failure. Saying UNRESOLVED_NAME would send
    someone chasing normalisation rules for a market that has no join to make."""
    runners = (Runner(A, "Carlos Alcaraz", "ACTIVE", 1),
               Runner(B, "Jannik Sinner", "REMOVED", 2))
    result = link_markets((_history(runners=runners),), (_match(),))
    assert result.linked == ()
    assert result.excluded[0].outcome is LinkOutcome.NOT_TWO_ACTIVE_RUNNERS


def test_a_market_with_three_active_runners_is_typed_not_unresolved() -> None:
    result = link_markets((_history(runners=(
        Runner(A, "Carlos Alcaraz", "ACTIVE", 1),
        Runner(B, "Jannik Sinner", "ACTIVE", 2),
        Runner(333, "Third Wheel", "ACTIVE", 3),
    )),), (_match(),))
    assert result.linked == ()
    assert result.excluded[0].outcome is LinkOutcome.NOT_TWO_ACTIVE_RUNNERS


# ------------------------------------------------- bridge version in the price table


def _price() -> ExchangePrice:
    return ExchangePrice(
        date=dt.date(2025, 6, 15), tour="ATP", player_a="Alcaraz C.",
        player_b="Sinner J.", odds_a=Decimal("2.0"), odds_b=Decimal("2.02"), won_a=True,
        support_a=FillSupport.SUPPORTED, support_b=FillSupport.UNSUPPORTED,
        prints_a=3, prints_b=0, market_id="1.1",
    )


def test_the_price_table_records_which_bridge_joined_it(tmp_path: Path) -> None:
    """Two tables joined by different bridge versions are different experiments; the
    header must say which one this is, and the rows must survive the file exactly."""
    out = tmp_path / "prices.jsonl"
    write_prices(out, [_price()], horizon_seconds=600, corpus_vintage="v1",
                 source_digest="sha256:abc", link_bridge_version=LINK_BRIDGE_VERSION)
    header = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert header["link_bridge_version"] == "exchange-link-bridge-v2"
    assert list(read_prices(out)) == [_price()]


def test_a_legacy_table_without_the_bridge_version_still_reads(tmp_path: Path) -> None:
    """Tables written before the version key existed remain readable; refusing them
    would orphan every measurement already built on one."""
    price = _price()
    legacy = tmp_path / "prices.jsonl"
    legacy.write_text(
        json.dumps({"kind": PRICES_KIND, "horizon_seconds": 600,
                    "corpus_vintage": "v0", "source_digest": "sha256:old"}) + "\n"
        + json.dumps({
            "date": price.date.isoformat(), "tour": price.tour,
            "player_a": price.player_a, "player_b": price.player_b,
            "odds_a": str(price.odds_a), "odds_b": str(price.odds_b),
            "won_a": price.won_a, "support_a": price.support_a.value,
            "support_b": price.support_b.value, "prints_a": price.prints_a,
            "prints_b": price.prints_b, "market_id": price.market_id,
        }) + "\n",
        encoding="utf-8",
    )
    assert list(read_prices(legacy)) == [price]


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
    assert report.mean_exchange_overround == pytest.approx(1.0, abs=0.02)
    assert report.crossable is True
    assert report.price_source == "MIDPOINT", "the probability comes from the midpoint"
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
