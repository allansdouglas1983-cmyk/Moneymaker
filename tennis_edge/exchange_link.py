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
from tennis_edge.exchange import ExchangeQuote, exchange_probability
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


@unique
class LinkOutcome(Enum):
    """Why a market did not become a scored row. Every one is counted, never dropped."""

    UNRESOLVED_NAME = "UNRESOLVED_NAME"
    NO_MATCH_ON_DATE = "NO_MATCH_ON_DATE"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    NO_PRICE_AT_HORIZON = "NO_PRICE_AT_HORIZON"
    ALREADY_CLAIMED = "ALREADY_CLAIMED"


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


def _resolve_names(
    markets: Sequence[MarketHistory], matches: Sequence[Match]
) -> dict[str, str]:
    """Betfair full name -> Tennis-Data name, via the governed identity bridge."""
    by_tour: dict[str, set[str]] = defaultdict(set)
    for match in matches:
        by_tour[match.tour].add(match.player_a)
        by_tour[match.tour].add(match.player_b)
    betfair_names = {r.name for m in markets for r in m.runners if r.name}
    if not betfair_names or not by_tour:
        return {}
    bridge = build_bridge(
        td_names_by_tour={t: sorted(n) for t, n in by_tour.items()},
        betfair_full_names=sorted(betfair_names),
        source_vintage="tennis-edge-exchange-link",
    )
    return {m.betfair_alias.display_name: m.source.raw_name for m in bridge.mappings}


def link_markets(
    markets: Sequence[MarketHistory],
    matches: Sequence[Match],
    *,
    horizon_seconds: int = DEFAULT_HORIZON_SECONDS,
) -> LinkResult:
    """Join markets to matches. Every market ends up linked or explicitly excluded."""
    resolved = _resolve_names(markets, matches)
    by_pair: dict[frozenset[str], list[Match]] = defaultdict(list)
    for match in matches:
        by_pair[frozenset((match.player_a, match.player_b))].append(match)

    linked: list[LinkedMarket] = []
    excluded: list[ExcludedMarket] = []
    claimed: set[int] = set()

    for market in markets:
        active = [r for r in market.runners if r.status.upper() == "ACTIVE"]
        names = [resolved.get(r.name) for r in active]
        if len(names) != 2 or any(n is None for n in names):
            excluded.append(ExcludedMarket(
                market.market_id, market.event_name, LinkOutcome.UNRESOLVED_NAME,
                f"could not resolve {[r.name for r in active]} to corpus names",
            ))
            continue

        off_date = dt.datetime.fromtimestamp(
            market.market_time_ms / 1000, tz=dt.timezone.utc
        ).date()
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

        quote = exchange_probability(market, seconds_before_off=horizon_seconds)
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
    scored: int
    exchange_log_loss: float | None
    bookmaker_log_loss: float | None
    mean_exchange_overround: float | None
    exclusions: dict[str, int]

    def report(self) -> str:
        lines = [
            f"markets: {self.universe:,}  linked and scored: {self.scored:,}",
        ]
        if self.exchange_log_loss is not None:
            lines.append(f"  exchange   log loss {self.exchange_log_loss:.5f}")
        if self.bookmaker_log_loss is not None:
            lines.append(f"  bookmaker  log loss {self.bookmaker_log_loss:.5f}")
        if self.mean_exchange_overround is not None:
            lines.append(f"  mean exchange overround {self.mean_exchange_overround:.4f}")
        if self.exclusions:
            lines.append("  exclusions: " + ", ".join(
                f"{k}={v}" for k, v in sorted(self.exclusions.items())))
        return "\n".join(lines)


def exchange_benchmark(result: LinkResult) -> BenchmarkReport:
    """Score the exchange price and the bookmaker price on the identical linked set."""
    from tennis_edge.backtest import market_probability
    from tennis_edge.devig import DevigMethod

    exchange: list[float] = []
    bookmaker: list[float] = []
    outcomes: list[int] = []
    overrounds: list[float] = []

    for row in result.linked:
        book = market_probability(row.match, book="pinnacle", method=DevigMethod.POWER)
        if book is None:
            continue
        exchange.append(row.exchange_probability_a)
        bookmaker.append(book)
        outcomes.append(1 if row.match.winner_is_a else 0)
        overrounds.append(row.quote.raw_overround)

    exclusions: dict[str, int] = {}
    for excluded in result.excluded:
        exclusions[excluded.outcome.value] = exclusions.get(excluded.outcome.value, 0) + 1

    return BenchmarkReport(
        universe=result.universe,
        scored=len(outcomes),
        exchange_log_loss=log_loss(exchange, outcomes) if outcomes else None,
        bookmaker_log_loss=log_loss(bookmaker, outcomes) if outcomes else None,
        mean_exchange_overround=(math.fsum(overrounds) / len(overrounds)
                                 if overrounds else None),
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
    args = parser.parse_args(argv)

    markets = read_markets(args.betfair)
    print(f"read {len(markets):,} Match Odds markets", file=sys.stderr)

    root = Path(args.data_root) if args.data_root else default_vintage_root()
    from tennis_edge.refresh import latest_vintage

    vintage = latest_vintage(root)
    if vintage is None:
        raise RuntimeError(f"no Tennis-Data vintage under {root}")
    matches, _stats = load_corpus(vintage.root)

    result = link_markets(markets, matches, horizon_seconds=args.horizon)
    print(exchange_benchmark(result).report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
