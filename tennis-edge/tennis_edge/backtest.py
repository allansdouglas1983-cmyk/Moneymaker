"""Walk-forward backtesting: the harness every model must survive before it is believed.

Three rules are enforced structurally rather than by care:

**Predict before update.** Models see a whole day's matches as a prediction batch, and only
then observe that day's results. A match played earlier the same day can never inform a
prediction made later the same day, because the live system could not have known it either.

**The closing price is a benchmark, not a fill.** Tennis-Data odds are "the most recent
before play starts" — the closing line. Betting *at* the close in a backtest tests a bet
nobody could place, since the close already contains the information that arrived after you
would have acted. So :func:`simulate_bets` charges an explicit slippage haircut, and the
untouched closing price is used only to measure CLV.

**Commission is charged per market on net winnings.** Betfair does not charge per bet. On a
market where you hold offsetting positions, per-bet commission overstates the cost.

The harness also records how many distinct strategies have been evaluated. That count is the
``N`` in a deflated-Sharpe correction: with 100 trials and no real edge, the best backtest
shows a Sharpe about 2.5 standard deviations above zero purely by construction.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Iterable, Protocol, Sequence

from price_contracts.ladder import index_of, is_on_ladder, price_of

from tennis_edge.corpus import Match, group_by_day
from tennis_edge.devig import DevigMethod, devig
from tennis_edge.metrics import BetResult, BettingSummary, ScoreCard, clv_beat, score, summarise_bets

__all__ = [
    "BOOKS",
    "DEFAULT_COMMISSION",
    "MIN_STAKE",
    "Model",
    "Prediction",
    "market_probability",
    "run_walk_forward",
    "evaluate_market",
    "evaluate_predictions",
    "simulate_bets",
    "worsen_one_tick",
    "TrialLog",
]

#: Books available in the corpus. ``betfair`` is the exchange price and is the correct
#: benchmark for a system that bets on the exchange — but it exists only from 2025.
#: ``pinnacle`` is the sharpest book with long history and is the default benchmark.
BOOKS = ("pinnacle", "betfair", "max", "avg", "b365")

#: Betfair "My Betfair Rewards" flat rate on net market winnings. The 5% base rate is the
#: stress case; a personal account with no points history should model 2%.
DEFAULT_COMMISSION = 0.05  # TE-0042: Betfair tennis market base rate, was a wrong 0.02

#: Betfair UK minimum back stake. A Kelly fraction below this is not a small bet, it is no
#: bet — rounding it up would breach the risk limit it came from.
MIN_STAKE = 2.0


class Model(Protocol):
    """A walk-forward model. Predict for the day, then observe the day."""

    @property
    def name(self) -> str: ...

    def predict(self, match: Match) -> float | None:
        """P(player_a wins), or None to abstain on this match."""

    def observe(self, matches: Sequence[Match]) -> None:
        """Absorb one completed day. Called only after every prediction for that day."""


@dataclass(frozen=True)
class Prediction:
    """One model forecast, paired with the market view and the realised outcome."""

    match: Match
    model_probability: float | None
    market_probability: float | None
    outcome: int

    @property
    def day(self) -> dt.date:
        return self.match.match_date


def market_probability(
    match: Match, *, book: str = "pinnacle", method: DevigMethod = DevigMethod.POWER
) -> float | None:
    """De-vigged P(player_a wins) implied by ``book``, or None if it had no price."""
    pair = match.odds.pair(book)
    if pair is None:
        return None
    return devig(pair, method).probabilities[0]


def run_walk_forward(
    matches: Sequence[Match],
    model: Model,
    *,
    start: dt.date | None = None,
    end: dt.date | None = None,
    book: str = "pinnacle",
    method: DevigMethod = DevigMethod.POWER,
    warmup_from: dt.date | None = None,
) -> list[Prediction]:
    """Run ``model`` over the corpus in strict chronological day batches.

    Matches before ``start`` still update the model (that is the warm-up), but are not
    scored. ``warmup_from`` optionally skips even the update for very early history.
    """
    predictions: list[Prediction] = []
    for day, batch in group_by_day(matches):
        if warmup_from is not None and day < warmup_from:
            continue
        scoring_day = (start is None or day >= start) and (end is None or day <= end)
        if scoring_day:
            ordered = sorted(batch, key=lambda m: (m.tour, m.player_a, m.player_b))
            for match in ordered:
                predictions.append(
                    Prediction(
                        match=match,
                        model_probability=model.predict(match),
                        market_probability=market_probability(match, book=book, method=method),
                        outcome=1 if match.winner_is_a else 0,
                    )
                )
        model.observe(batch)
    return predictions


def evaluate_market(
    matches: Sequence[Match],
    *,
    book: str = "pinnacle",
    method: DevigMethod = DevigMethod.POWER,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> ScoreCard:
    """Score the market itself — the benchmark every model is measured against."""
    probabilities: list[float] = []
    outcomes: list[int] = []
    for match in matches:
        if start is not None and match.match_date < start:
            continue
        if end is not None and match.match_date > end:
            continue
        p = market_probability(match, book=book, method=method)
        if p is None:
            continue
        probabilities.append(p)
        outcomes.append(1 if match.winner_is_a else 0)
    if not probabilities:
        raise ValueError(f"no {book} prices in the requested window")
    return score(probabilities, outcomes)


def evaluate_predictions(
    predictions: Sequence[Prediction], *, require_market: bool = True
) -> tuple[ScoreCard, ScoreCard]:
    """Score model and market on exactly the same matches, so the comparison is fair.

    Scoring a model on matches the market did not price (or vice versa) compares two
    different samples and is the commonest way a model is made to look better than it is.
    """
    model_p: list[float] = []
    market_p: list[float] = []
    outcomes: list[int] = []
    for pred in predictions:
        if pred.model_probability is None:
            continue
        if require_market and pred.market_probability is None:
            continue
        model_p.append(pred.model_probability)
        market_p.append(pred.market_probability if pred.market_probability is not None else 0.5)
        outcomes.append(pred.outcome)
    if not model_p:
        raise ValueError("no comparable predictions")
    return score(model_p, outcomes), score(market_p, outcomes)


def worsen_one_tick(price: float) -> float:
    """The next worse price on the Betfair ladder — a minimum realistic slippage charge.

    A one-tick haircut costs about 0.5% at odds 2.0 and about 2% at odds 5.0, which is the
    same order as any edge we could plausibly have. Charging zero slippage is the fastest
    way to turn a losing system into a winning backtest.
    """
    value = Decimal(str(round(price, 2)))
    if not is_on_ladder(value):
        # Snap down to the nearest ladder price first; an off-ladder quote is not tradable.
        index = 0
        for candidate in range(0, 350):
            if price_of(candidate) <= value:
                index = candidate
            else:
                break
    else:
        index = index_of(value)
    return float(price_of(max(index - 1, 0)))


@dataclass
class TrialLog:
    """Every strategy variant evaluated, so the multiple-comparisons cost stays visible.

    With 100 trials and zero true edge, the best backtest shows a Sharpe roughly 2.5 SDs
    above zero by construction. A deflated Sharpe ratio needs an honest count of trials —
    including the ones that were quietly abandoned.
    """

    entries: list[tuple[str, str]] = field(default_factory=list)

    def record(self, name: str, detail: str = "") -> None:
        self.entries.append((name, detail))

    @property
    def trials(self) -> int:
        return len(self.entries)

    def report(self) -> str:
        lines = [f"{i + 1:>3}. {name}  {detail}" for i, (name, detail) in enumerate(self.entries)]
        return f"{self.trials} strategy variants evaluated:\n" + "\n".join(lines)


def simulate_bets(
    predictions: Sequence[Prediction],
    *,
    edge_threshold: float = 0.0,
    book: str = "pinnacle",
    commission: float = DEFAULT_COMMISSION,
    apply_slippage: bool = True,
    stake: float = 1.0,
    closing_method: DevigMethod = DevigMethod.POWER,
    price_filter: Callable[[float], bool] | None = None,
) -> BettingSummary:
    """Settle notional bets wherever the model's edge over the quoted price clears a threshold.

    The price actually struck is the quoted price worsened by one tick (unless slippage is
    disabled for a pure like-for-like comparison). CLV is measured against the untouched
    closing price, which is the whole point of keeping the two separate.

    Clusters are match dates, so the bootstrap in :func:`summarise_bets` resamples days
    rather than individual bets and does not treat one afternoon's results as independent
    evidence.
    """
    results: list[BetResult] = []
    for pred in predictions:
        if pred.model_probability is None:
            continue
        quotes = pred.match.odds.pair(book)
        if quotes is None:
            continue
        closing = market_probability(pred.match, book=book, method=closing_method)
        for side, (probability, quoted) in enumerate(
            ((pred.model_probability, quotes[0]), (1.0 - pred.model_probability, quotes[1]))
        ):
            if price_filter is not None and not price_filter(quoted):
                continue
            struck = worsen_one_tick(quoted) if apply_slippage else quoted
            if struck <= 1.0:
                continue
            if probability * struck - 1.0 <= edge_threshold:
                continue
            won = (pred.outcome == 1) if side == 0 else (pred.outcome == 0)
            fair_close = None
            if closing is not None:
                fair_close = closing if side == 0 else 1.0 - closing
            results.append(
                BetResult(
                    cluster=pred.day,
                    odds=struck,
                    stake=stake,
                    won=won,
                    commission=commission,
                    clv=None if fair_close is None else clv_beat(struck, fair_close),
                )
            )
    if not results:
        raise ValueError("the strategy placed no bets in this window")
    return summarise_bets(results)


def date_span(matches: Iterable[Match]) -> tuple[dt.date, dt.date]:
    """First and last match date in a corpus slice."""
    dates = [m.match_date for m in matches]
    if not dates:
        raise ValueError("empty corpus slice")
    return min(dates), max(dates)
