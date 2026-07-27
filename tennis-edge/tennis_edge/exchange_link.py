"""Link Betfair markets to corpus matches, and benchmark the exchange price.

Betfair names players in full ("Carlos Alcaraz"); Tennis-Data abbreviates ("Alcaraz C.").
Every exchange measurement rests on that join, and **a join that guesses is worse than one
that refuses** — a wrong link scores one match's price against another match's outcome and
nothing downstream can detect it.

So every failure is a *typed exclusion* rather than a dropped row. Universe in equals linked
plus exclusions, always; the denominator is what makes a benchmark honest, and a row that
quietly disappears inflates whatever survives.

Orientation is the other silent killer. The corpus is name-ordered `(player_a, player_b)`
with the outcome isolated in `winner_is_a`; Betfair's runner order is its own business. The
link therefore records *which selection is the corpus's player A*, so probabilities can
never be transposed.

Run with ``python -m tennis_edge.exchange_link --betfair <path>``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path
from typing import Sequence

from sport_tennis.identity_bridge import build_bridge
from tennis_edge.betfair import MarketHistory, read_markets
from tennis_edge.corpus import Match, default_vintage_root, load_corpus
from tennis_edge.exchange import ExchangeQuote, PriceSource, exchange_probability
from tennis_edge.metrics import log_loss

__all__ = [
    "LinkOutcome",
    "LinkedMarket",
    "ExcludedMarket",
    "LinkResult",
    "BenchmarkReport",
    "link_markets",
    "exchange_benchmark",
    "main",
]

#: A match late in one time zone lands on the next UTC date. One day either side is the
#: smallest window that covers that without inviting ambiguity.
DATE_TOLERANCE_DAYS = 1

#: The horizon the exchange price is read at. Ten minutes before the scheduled off is far
#: enough out to be actionable and close enough to be informative.
DEFAULT_HORIZON_SECONDS = 600

#: Comparison books in preference order, sharpest first. NOT a single hardcoded book:
#: Tennis-Data carries no Pinnacle quotes at all for June 2026 (0 of 761 matches), so
#: naming one book silently drops every row of a recent period. Whichever book is used is
#: reported, because the benchmark means something different depending on which it was.
COMPARISON_BOOKS: tuple[str, ...] = ("pinnacle", "b365", "avg")


@unique
class LinkOutcome(Enum):
    """Why a market did not become a scored row. Every one is counted, never dropped."""

    UNRESOLVED_NAME = "UNRESOLVED_NAME"
    NO_MATCH_ON_DATE = "NO_MATCH_ON_DATE"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    NO_PRICE_AT_HORIZON = "NO_PRICE_AT_HORIZON"
    ALREADY_CLAIMED = "ALREADY_CLAIMED"
    NO_BOOKMAKER_PRICE = "NO_BOOKMAKER_PRICE"


@dataclass(frozen=True)
class LinkedMarket:
    """A market joined to its match, with orientation resolved onto the corpus."""

    market: MarketHistory
    match: Match
    quote: ExchangeQuote
    #: Which Betfair selection is the corpus's ``player_a``. Without this every probability
    #: is a coin-flip away from being transposed.
    selection_for_player_a: int

    @property
    def exchange_probability_a(self) -> float:
        if self.selection_for_player_a == self.quote.selection_a:
            return self.quote.probability_a
        return self.quote.probability_b


@dataclass(frozen=True)
class ExcludedMarket:
    """A market that could not be scored, and exactly why."""

    market_id: str
    event_name: str
    outcome: LinkOutcome
    detail: str


@dataclass(frozen=True)
class LinkResult:
    linked: tuple[LinkedMarket, ...]
    excluded: tuple[ExcludedMarket, ...]

    @property
    def universe(self) -> int:
        return len(self.linked) + len(self.excluded)


def _off_date(market: MarketHistory) -> dt.date:
    return dt.datetime.fromtimestamp(
        market.market_time_ms / 1000, tz=dt.timezone.utc
    ).date()


def _resolve_names(
    markets: Sequence[MarketHistory], matches: Sequence[Match]
) -> dict[tuple[dt.date, str], str]:
    """``(off date, Betfair full name)`` -> Tennis-Data name, via the governed bridge.

    **Scoped per day, and that is the whole point.** One bridge over the whole archive puts
    2,982 corpus names against 14,788 Betfair names and manufactures homonyms that do not
    exist among the players who actually met: Tennis-Data abbreviates to surname plus
    initial, so "Marin Cilic" and "Mate Cilic" are both "Cilic M.", one corpus identity maps
    to two Betfair names, and the bridge refuses HOMONYM_MULTIPLE_BETFAIR — killing both.
    They never play on the same day. Measured on the archive, that single effect took
    resolution from 93% to 12% and the join from usable to 200 links out of 405,487.

    Nothing is loosened to fix it. Same module, same normalisation, same refusals; the
    bridge is simply asked about one day's card, where the question has an answer. A
    genuine same-day ambiguity still refuses, because it is still ambiguous.

    Corpus names are drawn from a window of ±:data:`DATE_TOLERANCE_DAYS` around the market's
    date, matching the window the link itself allows — a match that crossed midnight UTC
    must be resolvable, or the tolerance downstream is decoration.
    """
    matches_by_date: dict[dt.date, list[Match]] = defaultdict(list)
    for match in matches:
        matches_by_date[match.match_date].append(match)

    names_by_date: dict[dt.date, set[str]] = defaultdict(set)
    for market in markets:
        for runner in market.runners:
            if runner.name:
                names_by_date[_off_date(market)].add(runner.name)

    resolved: dict[tuple[dt.date, str], str] = {}
    window = range(-DATE_TOLERANCE_DAYS, DATE_TOLERANCE_DAYS + 1)
    for day, betfair_names in names_by_date.items():
        by_tour: dict[str, set[str]] = defaultdict(set)
        for offset in window:
            for match in matches_by_date.get(day + dt.timedelta(days=offset), ()):
                by_tour[match.tour].add(match.player_a)
                by_tour[match.tour].add(match.player_b)
        if not by_tour:
            continue
        bridge = build_bridge(
            td_names_by_tour={t: sorted(n) for t, n in by_tour.items()},
            betfair_full_names=sorted(betfair_names),
            source_vintage="tennis-edge-exchange-link",
        )
        for mapping in bridge.mappings:
            resolved[(day, mapping.betfair_alias.display_name)] = mapping.source.raw_name
    return resolved


def link_markets(
    markets: Sequence[MarketHistory],
    matches: Sequence[Match],
    *,
    horizon_seconds: int = DEFAULT_HORIZON_SECONDS,
    use_ladder: bool = True,
    source: PriceSource = PriceSource.MIDPOINT,
) -> LinkResult:
    """Join markets to matches. Every market ends up linked or explicitly excluded."""
    resolved = _resolve_names(markets, matches)
    by_pair: dict[frozenset[str], list[Match]] = defaultdict(list)
    by_date: dict[dt.date, list[Match]] = defaultdict(list)
    for match in matches:
        by_pair[frozenset((match.player_a, match.player_b))].append(match)
        by_date[match.match_date].append(match)

    def matches_on(day: dt.date) -> list[Match]:
        return by_date.get(day, [])

    linked: list[LinkedMarket] = []
    excluded: list[ExcludedMarket] = []
    claimed: set[int] = set()

    for market in markets:
        active = [r for r in market.runners if r.status.upper() == "ACTIVE"]
        market_day = _off_date(market)

        # Asked BEFORE the names, because per-day scoping otherwise collapses two different
        # facts into one. A market on a date the corpus does not cover has no resolvable
        # names by construction, and reporting that as UNRESOLVED_NAME would say "we do not
        # know these players" when the truth is "there is no play in the corpus that day" —
        # the difference between a name problem and a coverage problem, and only one of them
        # is worth chasing.
        if not any(matches_on(market_day + dt.timedelta(days=offset))
                   for offset in range(-DATE_TOLERANCE_DAYS, DATE_TOLERANCE_DAYS + 1)):
            excluded.append(ExcludedMarket(
                market.market_id, market.event_name, LinkOutcome.NO_MATCH_ON_DATE,
                f"no corpus match within {DATE_TOLERANCE_DAYS}d of "
                f"{market_day.isoformat()}",
            ))
            continue

        names = [resolved.get((market_day, r.name)) for r in active]
        if len(names) != 2 or any(n is None for n in names):
            excluded.append(ExcludedMarket(
                market.market_id, market.event_name, LinkOutcome.UNRESOLVED_NAME,
                f"could not resolve {[r.name for r in active]} to corpus names",
            ))
            continue

        off_date = market_day
        candidates = [
            m for m in by_pair.get(frozenset(n for n in names if n), ())
            if abs((m.match_date - off_date).days) <= DATE_TOLERANCE_DAYS
        ]
        if not candidates:
            excluded.append(ExcludedMarket(
                market.market_id, market.event_name, LinkOutcome.NO_MATCH_ON_DATE,
                f"no corpus match for {names} within "
                f"{DATE_TOLERANCE_DAYS}d of {off_date.isoformat()}",
            ))
            continue
        if len(candidates) > 1:
            excluded.append(ExcludedMarket(
                market.market_id, market.event_name, LinkOutcome.AMBIGUOUS_MATCH,
                f"{len(candidates)} corpus matches for {names} near "
                f"{off_date.isoformat()}; refusing rather than choosing",
            ))
            continue

        match = candidates[0]
        if id(match) in claimed:
            excluded.append(ExcludedMarket(
                market.market_id, market.event_name, LinkOutcome.ALREADY_CLAIMED,
                "another market already linked to this match",
            ))
            continue

        quote = exchange_probability(
            market, seconds_before_off=horizon_seconds, use_ladder=use_ladder,
            source=source if use_ladder else PriceSource.LAST_TRADED,
        )
        if quote is None:
            excluded.append(ExcludedMarket(
                market.market_id, market.event_name, LinkOutcome.NO_PRICE_AT_HORIZON,
                f"no two-sided price at T-{horizon_seconds}s",
            ))
            continue

        selection_a = active[0].selection_id if names[0] == match.player_a \
            else active[1].selection_id
        claimed.add(id(match))
        linked.append(LinkedMarket(market, match, quote, selection_a))

    return LinkResult(tuple(linked), tuple(excluded))


@dataclass(frozen=True)
class BenchmarkReport:
    """Exchange against bookmaker, scored on exactly the same matches."""

    universe: int
    linked: int
    scored: int
    #: Which comparison book the bookmaker figure came from, or None if nothing scored.
    bookmaker_book: str | None
    exchange_log_loss: float | None
    bookmaker_log_loss: float | None
    mean_exchange_overround: float | None
    #: True when prices came from the ladder. A last-traded overround is an artefact and
    #: must not be read as a cost of trading.
    crossable: bool
    price_source: str | None
    median_exchange_overround: float | None
    median_size: float | None
    exclusions: dict[str, int]

    def report(self) -> str:
        lines = [
            f"markets: {self.universe:,}  linked: {self.linked:,}  "
            f"scored: {self.scored:,}",
        ]
        if self.exchange_log_loss is not None:
            lines.append(f"  exchange   log loss {self.exchange_log_loss:.5f}")
        if self.bookmaker_log_loss is not None:
            lines.append(f"  bookmaker  log loss {self.bookmaker_log_loss:.5f} "
                         f"({self.bookmaker_book})")
        if self.mean_exchange_overround is not None:
            label = self.price_source or "?"
            if not self.crossable:
                label += " — ARTEFACT, not a cost of trading"
            lines.append(f"  exchange overround  mean {self.mean_exchange_overround:.4f}"
                         + (f"  median {self.median_exchange_overround:.4f}"
                            if self.median_exchange_overround is not None else "")
                         + f"  ({label})")
        if self.median_size is not None:
            lines.append(f"  median size at best back GBP {self.median_size:,.2f}")
        if self.exclusions:
            lines.append("  exclusions: " + ", ".join(
                f"{k}={v}" for k, v in sorted(self.exclusions.items())))
        return "\n".join(lines)


def exchange_benchmark(result: LinkResult) -> BenchmarkReport:
    """Score the exchange price and the bookmaker price on the identical linked set."""
    from tennis_edge.backtest import market_probability
    from tennis_edge.devig import DevigMethod

    exclusions: dict[str, int] = {}
    for excluded in result.excluded:
        exclusions[excluded.outcome.value] = exclusions.get(excluded.outcome.value, 0) + 1

    # Choose the comparison book ONCE, across the whole linked set, so every scored row is
    # measured against the same book. Picking per row would silently mix benchmarks.
    chosen: str | None = None
    for candidate in COMPARISON_BOOKS:
        if any(market_probability(r.match, book=candidate, method=DevigMethod.POWER)
               is not None for r in result.linked):
            chosen = candidate
            break

    exchange: list[float] = []
    bookmaker: list[float] = []
    outcomes: list[int] = []
    overrounds: list[float] = []
    sizes: list[float] = []

    for row in result.linked:
        book = (None if chosen is None else
                market_probability(row.match, book=chosen, method=DevigMethod.POWER))
        if book is None:
            # A row dropped inside the benchmark is invisible; a row excluded by name is
            # not. This is the failure that reported "scored: 0" from 416 linked markets.
            key = LinkOutcome.NO_BOOKMAKER_PRICE.value
            exclusions[key] = exclusions.get(key, 0) + 1
            continue
        exchange.append(row.exchange_probability_a)
        bookmaker.append(book)
        outcomes.append(1 if row.match.winner_is_a else 0)
        overrounds.append(row.quote.raw_overround)
        for side in (row.quote.size_a, row.quote.size_b):
            if side is not None:
                sizes.append(float(side))

    return BenchmarkReport(
        universe=result.universe,
        linked=len(result.linked),
        scored=len(outcomes),
        bookmaker_book=chosen if outcomes else None,
        exchange_log_loss=log_loss(exchange, outcomes) if outcomes else None,
        bookmaker_log_loss=log_loss(bookmaker, outcomes) if outcomes else None,
        mean_exchange_overround=(math.fsum(overrounds) / len(overrounds)
                                 if overrounds else None),
        crossable=all(r.quote.crossable for r in result.linked) if result.linked else False,
        price_source=(result.linked[0].quote.source.value if result.linked else None),
        median_exchange_overround=(sorted(overrounds)[len(overrounds) // 2]
                                   if overrounds else None),
        median_size=(sorted(sizes)[len(sizes) // 2] if sizes else None),
        exclusions=exclusions,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark Betfair exchange prices against bookmaker closing prices "
                    "on exactly the same matches."
    )
    parser.add_argument("--betfair", required=True,
                        help="file, archive or directory of Betfair Historical data")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON_SECONDS,
                        help="seconds before the scheduled off (default 600)")
    parser.add_argument("--price", choices=[s.value for s in PriceSource],
                        default=PriceSource.MIDPOINT.value,
                        help="MIDPOINT estimates the probability (default); BEST_BACK is "
                             "the transactable price and distorts a probability estimate")
    parser.add_argument("--last-traded", action="store_true",
                        help="price from last trades instead of the ladder. Only for feeds "
                             "with no ladder (BASIC); the resulting overround is an "
                             "artefact, not a cost of trading")
    args = parser.parse_args(argv)

    markets = read_markets(args.betfair)
    print(f"read {len(markets):,} Match Odds markets", file=sys.stderr)

    root = Path(args.data_root) if args.data_root else default_vintage_root()
    from tennis_edge.refresh import latest_vintage

    vintage = latest_vintage(root)
    if vintage is None:
        raise RuntimeError(f"no Tennis-Data vintage under {root}")
    matches, _stats = load_corpus(vintage.root)

    result = link_markets(markets, matches, horizon_seconds=args.horizon,
                          use_ladder=not args.last_traded,
                          source=PriceSource(args.price))
    print(exchange_benchmark(result).report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
