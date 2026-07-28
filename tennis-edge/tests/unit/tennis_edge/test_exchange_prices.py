"""Exchange prices joined to corpus matches, kept as a file the rest of the work can use.

The link costs eighty seconds and a four-gigabyte archive. Every experiment that wants
exchange prices should not pay that again, and — more importantly — should not be free to
pay it *differently*. A price table rebuilt with a different horizon or a different join
each time is a table nobody can compare two results across.

So the join is persisted once, with the horizon and the corpus vintage recorded in the file,
and the settlement side reads it. Two things these tests exist to prevent:

**A price with no fill evidence.** BASIC is a last-trade trace. Every price written here
carries the traded-through verdict for the side it belongs to, so a downstream settlement
cannot silently credit a fill nobody witnessed. The evidence travels with the price or the
row does not exist.

**A table that forgets what made it.** Horizon, corpus vintage and source digest are in the
header, and reading a file without them is refused. Two tables built at different horizons
are different experiments, and finding that out afterwards is finding it out too late.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

import pytest

from tennis_edge.betfair import LtpObservation, MarketHistory, Runner
from tennis_edge.corpus import Completion, Match, OddsQuotes
from tennis_edge.exchange_prices import (
    PRICES_KIND,
    ExchangePrice,
    build_prices,
    read_prices,
    write_prices,
)
from tennis_edge.fill_evidence import FillSupport

DAY = dt.date(2019, 6, 3)
OFF = int(dt.datetime.combine(DAY, dt.time(12, 0),
                              tzinfo=dt.timezone.utc).timestamp() * 1000)


def _match(a: str = "Berankis R.", b: str = "Cilic M.", *, winner_is_a: bool = True) -> Match:
    return Match(
        match_date=DAY, tour="ATP", tournament="Test Open", location="Testville",
        tier="ATP250", court="Outdoor", surface="Hard", round_name="1st Round",
        best_of=3, player_a=a, player_b=b, winner_is_a=winner_is_a,
        rank_a=10, rank_b=40, points_a=2000, points_b=800,
        games_a=12, games_b=7, sets_a=2, sets_b=0,
        completion=Completion.COMPLETED,
        odds=OddsQuotes(b365_a=1.5, b365_b=2.5), source_file="test",
    )


def _market(prints: list[tuple[int, int, str]]) -> MarketHistory:
    """``prints`` is (seconds before off, selection_id, price)."""
    return MarketHistory(
        market_id="1.1", event_id="9", event_name="Cilic v Berankis",
        market_type="MATCH_ODDS", country_code="GB", market_time_ms=OFF,
        runners=(Runner(selection_id=1, name="Ricardas Berankis", status="ACTIVE",
                        sort_priority=1),
                 Runner(selection_id=2, name="Marin Cilic", status="ACTIVE",
                        sort_priority=2)),
        observations=tuple(
            LtpObservation(publish_time_ms=OFF - s * 1000, selection_id=sid,
                           price=Decimal(p))
            for s, sid, p in prints
        ),
        went_in_play=False,
    )


def _standard() -> tuple[list[MarketHistory], list[Match]]:
    market = _market([
        (900, 1, "2.5"), (900, 2, "1.6"),
        (600, 1, "2.6"), (600, 2, "1.55"),
        (120, 1, "2.8"), (120, 2, "1.5"),
    ])
    return [market], [_match()]


class TestBuildPrices:
    def test_a_linked_market_yields_a_price_for_both_sides(self) -> None:
        markets, matches = _standard()
        prices = build_prices(markets, matches, horizon_seconds=600)
        assert len(prices) == 1
        price = prices[0]
        assert price.odds_a == Decimal("2.6")
        assert price.odds_b == Decimal("1.55")

    def test_the_price_belongs_to_the_corpus_player_not_the_betfair_runner(self) -> None:
        """Orientation is the silent killer. player_a is the name-ordered corpus player,
        and its price must follow that player through the join, not Betfair's runner order.
        Transposing them scores every bet against the wrong outcome."""
        markets, matches = _standard()
        price = build_prices(markets, matches, horizon_seconds=600)[0]
        assert price.player_a == "Berankis R."
        # Berankis is Betfair selection 1, priced 2.6 at the horizon.
        assert price.odds_a == Decimal("2.6")

    def test_every_price_carries_its_own_fill_evidence(self) -> None:
        """A price without a verdict lets a settlement credit a fill nobody witnessed."""
        markets, matches = _standard()
        price = build_prices(markets, matches, horizon_seconds=600)[0]
        assert price.support_a in set(FillSupport)
        assert price.support_b in set(FillSupport)

    def test_a_side_that_later_trades_better_is_supported(self) -> None:
        """Berankis goes 2.6 -> 2.8 after the horizon: somebody backed at 2.6 or better."""
        markets, matches = _standard()
        price = build_prices(markets, matches, horizon_seconds=600)[0]
        assert price.support_a is FillSupport.SUPPORTED

    def test_a_side_that_only_shortens_is_unsupported(self) -> None:
        """Cilic goes 1.55 -> 1.5: nothing puts anyone at 1.55 after the horizon."""
        markets, matches = _standard()
        price = build_prices(markets, matches, horizon_seconds=600)[0]
        assert price.support_b is FillSupport.UNSUPPORTED

    def test_the_outcome_travels_with_the_row(self) -> None:
        """Settlement needs the result, and re-joining it later is another chance to
        transpose it."""
        markets, matches = _standard()
        price = build_prices(markets, matches, horizon_seconds=600)[0]
        assert price.won_a is True

    def test_a_market_with_no_price_at_the_horizon_yields_nothing(self) -> None:
        """Not a zero, not a guess. The row does not exist."""
        markets = [_market([(120, 1, "2.8"), (120, 2, "1.5")])]
        assert build_prices(markets, [_match()], horizon_seconds=600) == ()

    def test_an_unlinked_market_yields_nothing(self) -> None:
        markets, _ = _standard()
        assert build_prices(markets, [_match(a="Nobody X.", b="Nemo Y.")],
                            horizon_seconds=600) == ()


class TestRoundTrip:
    def test_prices_survive_the_file_exactly(self, tmp_path: Path) -> None:
        """A price that changes crossing the file makes every number after it fiction."""
        markets, matches = _standard()
        prices = build_prices(markets, matches, horizon_seconds=600)
        out = tmp_path / "prices.jsonl"
        write_prices(out, prices, horizon_seconds=600, corpus_vintage="v1",
                     source_digest="sha256:abc")
        back = list(read_prices(out))
        assert back == list(prices)
        assert isinstance(back[0].odds_a, Decimal)

    def test_the_header_records_the_horizon_and_the_corpus(self, tmp_path: Path) -> None:
        markets, matches = _standard()
        out = tmp_path / "prices.jsonl"
        write_prices(out, build_prices(markets, matches, horizon_seconds=600),
                     horizon_seconds=600, corpus_vintage="vintage-2026-07-26",
                     source_digest="sha256:abc")
        header = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
        assert header["kind"] == PRICES_KIND
        assert header["horizon_seconds"] == 600
        assert header["corpus_vintage"] == "vintage-2026-07-26"
        assert header["source_digest"] == "sha256:abc"

    def test_reading_a_file_without_the_header_is_refused(self, tmp_path: Path) -> None:
        stray = tmp_path / "stray.jsonl"
        stray.write_text('{"player_a": "x"}\n', encoding="utf-8")
        with pytest.raises(ValueError):
            list(read_prices(stray))


class TestExchangePriceType:
    def test_a_price_is_immutable(self) -> None:
        markets, matches = _standard()
        price = build_prices(markets, matches, horizon_seconds=600)[0]
        with pytest.raises(Exception):
            price.odds_a = Decimal("9.9")  # type: ignore[misc]

    def test_prices_are_decimal_never_float(self) -> None:
        """Money is exact. A float price here would round its way into every return."""
        markets, matches = _standard()
        price = build_prices(markets, matches, horizon_seconds=600)[0]
        assert isinstance(price.odds_a, Decimal)
        assert isinstance(price.odds_b, Decimal)

    def test_a_float_price_is_refused_by_the_constructor(self) -> None:
        with pytest.raises(TypeError):
            ExchangePrice(date=DAY, tour="ATP", player_a="A", player_b="B",
                          odds_a=2.5, odds_b=1.6,  # type: ignore[arg-type]
                          won_a=True, support_a=FillSupport.SUPPORTED,
                          support_b=FillSupport.SUPPORTED,
                          prints_a=1, prints_b=1, market_id="1.1")
