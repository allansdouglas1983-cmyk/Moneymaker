"""Exchange prices joined to corpus matches, with fill evidence attached, kept as a file.

Producing this table costs eighty seconds and a four-gigabyte archive. Every experiment that
wants exchange prices should not pay that again, and — more to the point — should not be
free to pay it *differently*. A price table rebuilt with a different horizon or a different
join on each run is a table across which no two results can be compared. So it is built
once, the horizon and corpus vintage are recorded in the file, and everything downstream
reads it.

**Every price carries its own fill evidence.** Betfair Historical BASIC is a last-trade
trace: the price at a horizon is what somebody else was matched at, not an offer that was
waiting for us. So each side's price arrives with the :mod:`~tennis_edge.fill_evidence`
verdict for that side, and a settlement that wants to credit a bet has to look at it. The
evidence travels with the price or the row does not exist — the one arrangement under which
a later loop cannot quietly assume every fill happened.

**Orientation is resolved here, once.** The corpus is name-ordered ``(player_a, player_b)``
with the outcome isolated in ``winner_is_a``; Betfair's runner order is its own business.
This module writes the price that belongs to the *corpus* player A, and carries the outcome
on the same row. Re-joining the result later is another opportunity to transpose it, and a
transposition scores every bet against the wrong match with nothing downstream able to tell.
"""
from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from tennis_edge.betfair import MarketHistory
from tennis_edge.corpus import Match
from tennis_edge.exchange import PriceSource
from tennis_edge.exchange_link import (
    DEFAULT_HORIZON_SECONDS,
    LINK_BRIDGE_VERSION,
    link_markets,
)
from tennis_edge.fill_evidence import FillSupport, traded_through

__all__ = [
    "PRICES_KIND",
    "ExchangePrice",
    "build_prices",
    "write_prices",
    "read_prices",
]

PRICES_KIND = "tennis-edge-exchange-prices-v1"


@dataclass(frozen=True)
class ExchangePrice:
    """One corpus match, its exchange prices, and whether the record supports taking them."""

    date: dt.date
    tour: str
    #: The corpus's name-ordered players. Prices and outcome follow THESE, never Betfair's
    #: runner order.
    player_a: str
    player_b: str
    odds_a: Decimal
    odds_b: Decimal
    won_a: bool
    support_a: FillSupport
    support_b: FillSupport
    #: Pre-off prints after the horizon on each side. A verdict from one print and a verdict
    #: from forty are different verdicts; the count travels so a report can stratify.
    prints_a: int
    prints_b: int
    market_id: str

    def __post_init__(self) -> None:
        for name in ("odds_a", "odds_b"):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(
                    f"{name} must be Decimal, not {type(value).__name__}; a float price "
                    "would round its way into every return computed from this table"
                )


def build_prices(
    markets: Sequence[MarketHistory],
    matches: Sequence[Match],
    *,
    horizon_seconds: int = DEFAULT_HORIZON_SECONDS,
) -> tuple[ExchangePrice, ...]:
    """Link, price at the horizon, and attach the traded-through verdict for each side.

    A market with no price at the horizon produces no row. Not a zero and not a carried
    guess: the absence is real, and the exclusion is already counted by the linker.
    """
    result = link_markets(markets, matches, horizon_seconds=horizon_seconds,
                          use_ladder=False, source=PriceSource.LAST_TRADED)
    prices: list[ExchangePrice] = []
    for link in result.linked:
        market, match = link.market, link.match
        selection_a = link.selection_for_player_a
        others = [r.selection_id for r in market.runners
                  if r.selection_id != selection_a]
        if len(others) != 1:
            continue
        selection_b = others[0]

        odds_a = market.ltp_at(selection_a, seconds_before_off=horizon_seconds)
        odds_b = market.ltp_at(selection_b, seconds_before_off=horizon_seconds)
        if odds_a is None or odds_b is None:
            continue

        evidence_a = traded_through(market, selection_a, odds_a,
                                    seconds_before_off=horizon_seconds)
        evidence_b = traded_through(market, selection_b, odds_b,
                                    seconds_before_off=horizon_seconds)
        prices.append(ExchangePrice(
            date=match.match_date, tour=match.tour,
            player_a=match.player_a, player_b=match.player_b,
            odds_a=odds_a, odds_b=odds_b, won_a=match.winner_is_a,
            support_a=evidence_a.support, support_b=evidence_b.support,
            prints_a=evidence_a.subsequent_prints,
            prints_b=evidence_b.subsequent_prints,
            market_id=market.market_id,
        ))
    return tuple(prices)


def write_prices(
    path: Path | str,
    prices: Iterable[ExchangePrice],
    *,
    horizon_seconds: int,
    corpus_vintage: str,
    source_digest: str,
    # Any table written by this build was joined by the current linker, so the current
    # version is the truthful default; a caller replaying an older join must say so.
    link_bridge_version: str = LINK_BRIDGE_VERSION,
) -> int:
    """Write the table with a header naming what produced it. Returns rows written."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "kind": PRICES_KIND,
            "horizon_seconds": horizon_seconds,
            "corpus_vintage": corpus_vintage,
            "source_digest": source_digest,
            "link_bridge_version": link_bridge_version,
        }) + "\n")
        for price in prices:
            handle.write(json.dumps({
                "date": price.date.isoformat(),
                "tour": price.tour,
                "player_a": price.player_a,
                "player_b": price.player_b,
                "odds_a": str(price.odds_a),
                "odds_b": str(price.odds_b),
                "won_a": price.won_a,
                "support_a": price.support_a.value,
                "support_b": price.support_b.value,
                "prints_a": price.prints_a,
                "prints_b": price.prints_b,
                "market_id": price.market_id,
            }) + "\n")
            written += 1
    return written


def read_prices(path: Path | str) -> Iterator[ExchangePrice]:
    """Read the table back. Refuses a file that does not declare what it is.

    Two tables built at different horizons are different experiments. A file that does not
    say which one it is can be read as the other, and the mistake is invisible. Tables
    written before ``link_bridge_version`` existed carry no such key and still load.
    """
    target = Path(path)
    with target.open(encoding="utf-8") as handle:
        first = handle.readline()
        try:
            header = json.loads(first)
        except ValueError as error:
            raise ValueError(f"{target} has no exchange-price header") from error
        if not isinstance(header, dict) or header.get("kind") != PRICES_KIND:
            raise ValueError(
                f"{target} is not a {PRICES_KIND} table; refusing to guess at its shape"
            )
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            yield ExchangePrice(
                date=dt.date.fromisoformat(row["date"]),
                tour=row["tour"],
                player_a=row["player_a"],
                player_b=row["player_b"],
                odds_a=Decimal(row["odds_a"]),
                odds_b=Decimal(row["odds_b"]),
                won_a=bool(row["won_a"]),
                support_a=FillSupport(row["support_a"]),
                support_b=FillSupport(row["support_b"]),
                prints_a=int(row["prints_a"]),
                prints_b=int(row["prints_b"]),
                market_id=row["market_id"],
            )
