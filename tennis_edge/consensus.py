"""Cross-book consensus deviation — betting where one book is out of line with the rest.

This is the only architecture in the sports-betting literature with **real-money**
verification rather than a backtest: Kaunitz, Zhong & Kreiner staked actual cash for five
months and returned ~10%, and their accounts were subsequently limited, which is itself
confirmation the edge was real. It also does not require out-predicting anyone. Our own
rating layer and point model both measured zero incremental value over the closing line;
this approach never tries to.

The mechanic: build a fair probability from a consensus of books, then look for a *different*
book quoting a price long enough that the consensus implies positive expectation. You are not
claiming to know better than the market — only that one participant in it is stale.

Three things this module is careful about, because each can manufacture a fake edge:

**Circularity.** The consensus must not contain the book being bet. Tennis-Data's ``Avg`` and
``Max`` are panel aggregates that already include Bet365 and Pinnacle, so using ``Avg`` as the
fair estimate for a Bet365 bet is partly comparing a number to itself.
:data:`INDEPENDENT_PAIRINGS` records which combinations are clean and
:func:`ConsensusConfig.circularity_warning` reports the rest rather than hiding them.

**Attainability.** ``Max`` is the best price anywhere on a scraped panel at an unstated
moment. It is an upper bound, not a price you could have taken, and results computed on it
should never be quoted as achievable.

**De-vig.** Margin sits disproportionately on longshots, so proportional removal overstates
their probability and invents underdog value. Power removal is the default here for the same
reason it is elsewhere in this package.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from tennis_edge.backtest import DEFAULT_COMMISSION, worsen_one_tick
from tennis_edge.corpus import Match
from tennis_edge.devig import DevigMethod, devig
from tennis_edge.metrics import BetResult, BettingSummary, clv_beat, summarise_bets

__all__ = [
    "INDEPENDENT_PAIRINGS",
    "EXCHANGE_BOOKS",
    "ATTAINABLE_BOOKS",
    "ConsensusConfig",
    "ValueBet",
    "consensus_probabilities",
    "find_value_bets",
    "evaluate",
]

#: (consensus books, target book) combinations where the consensus genuinely excludes the
#: target. Anything outside this set is reported with a circularity warning attached.
INDEPENDENT_PAIRINGS: frozenset[tuple[tuple[str, ...], str]] = frozenset(
    {
        (("pinnacle",), "b365"),
        (("pinnacle",), "betfair"),
        (("b365",), "betfair"),
        (("pinnacle", "b365"), "betfair"),
    }
)

#: Books where commission is charged on winnings rather than built into the price.
EXCHANGE_BOOKS = frozenset({"betfair"})

#: Books representing a price a single account could actually have taken. ``max`` and ``avg``
#: are panel statistics, not counters you can walk up to.
ATTAINABLE_BOOKS = frozenset({"b365", "pinnacle", "betfair"})


@dataclass(frozen=True)
class ConsensusConfig:
    """One fully specified strategy variant. Every field is part of the trial count."""

    consensus_books: tuple[str, ...] = ("pinnacle",)
    target_book: str = "b365"
    method: DevigMethod = DevigMethod.POWER
    min_edge: float = 0.0
    commission: float | None = None
    apply_slippage: bool = True
    min_price: float = 1.0
    max_price: float = 1000.0
    tours: frozenset[str] | None = None
    tiers: frozenset[str] | None = None
    #: Book used to measure closing-line value. It MUST NOT be one of the consensus books:
    #: measuring CLV against the very probability that selected the bet is circular and
    #: comes out positive by construction, whether or not the strategy makes money. Leave
    #: None and no CLV is reported, which is more honest than reporting a tautology.
    clv_reference: str | None = None

    @property
    def effective_commission(self) -> float:
        """Exchange commission where it applies; bookmakers price their margin in instead."""
        if self.commission is not None:
            return self.commission
        return DEFAULT_COMMISSION if self.target_book in EXCHANGE_BOOKS else 0.0

    @property
    def independent(self) -> bool:
        return (self.consensus_books, self.target_book) in INDEPENDENT_PAIRINGS

    @property
    def attainable(self) -> bool:
        return self.target_book in ATTAINABLE_BOOKS

    def circularity_warning(self) -> str | None:
        """Why this variant's number should be discounted, if it should."""
        problems: list[str] = []
        if self.target_book in self.consensus_books:
            problems.append("the target book is inside its own consensus")
        elif not self.independent:
            problems.append(
                f"consensus {self.consensus_books} is a panel aggregate that likely "
                f"contains {self.target_book}"
            )
        if not self.attainable:
            problems.append(f"{self.target_book} is a panel statistic, not a takeable price")
        return "; ".join(problems) if problems else None

    def label(self) -> str:
        books = "+".join(self.consensus_books)
        return (
            f"{books}->{self.target_book} {self.method.value.lower()} "
            f"edge>{self.min_edge:.1%}"
            + (f" price[{self.min_price:g},{self.max_price:g}]"
               if (self.min_price > 1.0 or self.max_price < 1000.0) else "")
            + (f" {'/'.join(sorted(self.tours))}" if self.tours else "")
        )


@dataclass(frozen=True)
class ValueBet:
    """One qualifying deviation, with the price actually assumed struck."""

    match: Match
    side: str
    consensus_probability: float
    quoted_price: float
    struck_price: float
    edge: float
    won: bool

    @property
    def day(self) -> dt.date:
        return self.match.match_date


def _logit(p: float) -> float:
    clipped = min(max(p, 1e-9), 1.0 - 1e-9)
    return math.log(clipped / (1.0 - clipped))


def consensus_probabilities(
    match: Match, books: Sequence[str], method: DevigMethod = DevigMethod.POWER
) -> tuple[float, float] | None:
    """Fair probabilities for (a, b) pooled across ``books``, or None if none priced it.

    Pooling is in logit space. Averaging probabilities directly drags a consensus toward
    0.5 and costs it resolution, which is precisely the quantity a sharp market has and a
    model does not — so the arithmetic mean would blunt the very thing being relied on.
    """
    logits: list[float] = []
    for book in books:
        pair = match.odds.pair(book)
        if pair is None:
            continue
        logits.append(_logit(devig(pair, method).probabilities[0]))
    if not logits:
        return None
    pooled = sum(logits) / len(logits)
    probability_a = 1.0 / (1.0 + math.exp(-pooled))
    return probability_a, 1.0 - probability_a


def find_value_bets(match: Match, config: ConsensusConfig) -> list[ValueBet]:
    """Qualifying deviations for one match under ``config``.

    Both sides are examined. Expectation is computed on the price after slippage and net of
    commission, so a bet only qualifies if it survives the costs of actually placing it.
    """
    if config.tours is not None and match.tour not in config.tours:
        return []
    if config.tiers is not None and match.tier not in config.tiers:
        return []
    consensus = consensus_probabilities(match, config.consensus_books, config.method)
    quotes = match.odds.pair(config.target_book)
    if consensus is None or quotes is None:
        return []

    commission = config.effective_commission
    found: list[ValueBet] = []
    for index, (probability, quoted) in enumerate(zip(consensus, quotes)):
        if not config.min_price <= quoted <= config.max_price:
            continue
        struck = worsen_one_tick(quoted) if config.apply_slippage else quoted
        if struck <= 1.0:
            continue
        net_odds = 1.0 + (struck - 1.0) * (1.0 - commission)
        edge = probability * net_odds - 1.0
        if edge <= config.min_edge:
            continue
        side = "A" if index == 0 else "B"
        won = match.winner_is_a if index == 0 else not match.winner_is_a
        found.append(
            ValueBet(
                match=match, side=side, consensus_probability=probability,
                quoted_price=quoted, struck_price=struck, edge=edge, won=won,
            )
        )
    return found


@dataclass(frozen=True)
class StrategyResult:
    """A variant's outcome, carrying the caveats that qualify it."""

    config: ConsensusConfig
    summary: BettingSummary
    warning: str | None = None
    trials_counted: int = 1

    def report(self) -> str:
        line = self.summary.report(self.config.label())
        return line if self.warning is None else f"{line}\n      caveat: {self.warning}"


def evaluate(
    matches: Iterable[Match],
    config: ConsensusConfig,
    *,
    start: dt.date | None = None,
    end: dt.date | None = None,
    bootstrap: int = 400,
) -> StrategyResult:
    """Run one variant over a date window and summarise it with clustered uncertainty.

    CLV is reported only against :attr:`ConsensusConfig.clv_reference`, a book outside the
    consensus. Scoring value against the same number that picked the bet would return a
    positive figure for every variant here, including the ones that lose money — the first
    sweep did exactly that, and every row came back with flattering CLV.
    """
    results: list[BetResult] = []
    reference = config.clv_reference
    if reference is not None and reference in config.consensus_books:
        raise ValueError(
            f"clv_reference {reference!r} is inside the consensus; CLV would be circular"
        )
    for match in matches:
        if start is not None and match.match_date < start:
            continue
        if end is not None and match.match_date > end:
            continue
        for bet in find_value_bets(match, config):
            clv: float | None = None
            if reference is not None:
                fair = consensus_probabilities(match, (reference,), config.method)
                if fair is not None:
                    clv = clv_beat(bet.struck_price, fair[0 if bet.side == "A" else 1])
            results.append(
                BetResult(
                    cluster=bet.day, odds=bet.struck_price, stake=1.0, won=bet.won,
                    commission=config.effective_commission, clv=clv,
                )
            )
    if not results:
        raise ValueError(f"no qualifying bets for {config.label()}")
    return StrategyResult(
        config=config,
        summary=summarise_bets(results, bootstrap=bootstrap),
        warning=config.circularity_warning(),
    )


@dataclass
class VariantSweep:
    """A recorded set of variants, so the multiple-comparisons cost cannot be forgotten.

    With a hundred variants and no real edge, the best backtest shows a Sharpe roughly 2.5
    standard deviations above zero purely by construction. The count kept here is what a
    deflated Sharpe ratio needs to undo that.
    """

    results: list[StrategyResult] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def add(self, result: StrategyResult) -> None:
        self.results.append(result)

    def skip(self, label: str, reason: str) -> None:
        """A variant that produced no bets still counts as a variant tried."""
        self.skipped.append((label, reason))

    @property
    def trials(self) -> int:
        return len(self.results) + len(self.skipped)

    def best(self, *, min_bets: int = 500, clean_only: bool = True) -> StrategyResult | None:
        """Best variant by ROI, among those worth taking seriously.

        Ranking on raw ROI alone is how a 54-bet strategy betting into a panel *average*
        wins a sweep — which is what happened the first time this ran. A variant must clear
        a minimum bet count, and by default must be free of circularity and attainability
        caveats, before it is eligible to be called best.
        """
        candidates = [
            r for r in self.results
            if r.summary.bets >= min_bets and (not clean_only or r.warning is None)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.summary.roi)
