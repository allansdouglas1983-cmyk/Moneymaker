"""Backtest harness tests, centred on the one property that matters most: a model must
never see a result before it has predicted it. Everything else in a betting backtest can be
approximately right and still be useful; leak the outcome and the whole exercise is worthless.
"""
from __future__ import annotations

import datetime as dt
from typing import Sequence

import pytest

from tennis_edge.corpus import Completion, Match, OddsQuotes
from tennis_edge.devig import DevigMethod
from tennis_edge.backtest import (
    Prediction,
    TrialLog,
    evaluate_market,
    evaluate_predictions,
    market_probability,
    run_walk_forward,
    simulate_bets,
    worsen_one_tick,
)


def _match(day: int, a: str, b: str, *, winner_is_a: bool = True,
           pinnacle: tuple[float, float] | None = (1.5, 2.6)) -> Match:
    return Match(
        match_date=dt.date(2024, 1, day), tour="ATP", tournament="T", location="L",
        tier="ATP250", court="Outdoor", surface="Hard", round_name="R1", best_of=3,
        player_a=a, player_b=b, winner_is_a=winner_is_a,
        rank_a=1, rank_b=2, points_a=None, points_b=None,
        games_a=12, games_b=7, sets_a=2, sets_b=0, completion=Completion.COMPLETED,
        odds=OddsQuotes(pinnacle_a=None if pinnacle is None else pinnacle[0],
                        pinnacle_b=None if pinnacle is None else pinnacle[1]),
        source_file="test",
    )


class _Recorder:
    """A model that records the order of predict/observe calls and how much it has seen."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.seen: list[Match] = []

    @property
    def name(self) -> str:
        return "recorder"

    def predict(self, match: Match) -> float | None:
        self.calls.append(f"predict:{match.match_date.day}:{match.player_a}")
        return 0.5

    def observe(self, matches: Sequence[Match]) -> None:
        self.calls.append(f"observe:{matches[0].match_date.day}")
        self.seen.extend(matches)


class _Oracle:
    """A model that cheats if it can: it answers from whatever it has already observed.

    If the harness ever calls observe() before predict() for the same day, this model scores
    perfectly — which is precisely the failure the test is designed to catch.
    """

    def __init__(self) -> None:
        self._known: dict[tuple[dt.date, str], bool] = {}

    @property
    def name(self) -> str:
        return "oracle"

    def predict(self, match: Match) -> float | None:
        known = self._known.get((match.match_date, match.player_a))
        if known is None:
            return 0.5
        return 0.999 if known else 0.001

    def observe(self, matches: Sequence[Match]) -> None:
        for match in matches:
            self._known[(match.match_date, match.player_a)] = match.winner_is_a


def test_every_prediction_for_a_day_precedes_that_day_being_observed() -> None:
    matches = [_match(1, "A", "B"), _match(1, "C", "D"), _match(2, "E", "F")]
    model = _Recorder()
    run_walk_forward(matches, model)
    assert model.calls == [
        "predict:1:A", "predict:1:C", "observe:1", "predict:2:E", "observe:2",
    ]


def test_a_model_that_would_cheat_cannot_beat_a_coin_flip() -> None:
    """The decisive no-lookahead test. The oracle answers from observed results; under a
    correct harness it never has the current day, so it must stay at 0.5 throughout."""
    matches = [_match(day, "A", "B", winner_is_a=(day % 2 == 0)) for day in range(1, 20)]
    predictions = run_walk_forward(matches, _Oracle())
    assert all(p.model_probability == 0.5 for p in predictions), "outcome leaked into predict()"


def test_warmup_matches_update_the_model_but_are_not_scored() -> None:
    matches = [_match(day, "A", "B") for day in range(1, 11)]
    model = _Recorder()
    predictions = run_walk_forward(matches, model, start=dt.date(2024, 1, 6))
    assert len(predictions) == 5
    assert len(model.seen) == 10, "warm-up days must still train the model"


def test_predictions_are_ordered_deterministically_within_a_day() -> None:
    matches = [_match(1, "Z", "Y"), _match(1, "A", "B"), _match(1, "M", "N")]
    first = [p.match.player_a for p in run_walk_forward(matches, _Recorder())]
    second = [p.match.player_a for p in run_walk_forward(list(reversed(matches)), _Recorder())]
    assert first == second == ["A", "M", "Z"]


def test_market_probability_uses_the_requested_devig_method() -> None:
    match = _match(1, "A", "B", pinnacle=(1.25, 4.5))
    proportional = market_probability(match, method=DevigMethod.PROPORTIONAL)
    powered = market_probability(match, method=DevigMethod.POWER)
    assert proportional is not None and powered is not None
    assert powered > proportional, "power removal must favour the favourite"


def test_market_probability_is_none_without_a_price() -> None:
    assert market_probability(_match(1, "A", "B", pinnacle=None)) is None


def test_evaluate_market_refuses_a_window_with_no_prices() -> None:
    with pytest.raises(ValueError):
        evaluate_market([_match(1, "A", "B", pinnacle=None)])


def test_model_and_market_are_scored_on_exactly_the_same_matches() -> None:
    """Scoring a model on matches the market never priced compares two different samples,
    which is the commonest way a model is made to look better than it is."""
    predictions = [
        Prediction(_match(1, "A", "B"), 0.6, 0.55, 1),
        Prediction(_match(2, "C", "D"), 0.7, None, 1),      # market absent -> excluded
        Prediction(_match(3, "E", "F"), None, 0.55, 0),     # model abstained -> excluded
    ]
    model_card, market_card = evaluate_predictions(predictions)
    assert model_card.n == market_card.n == 1


def test_one_tick_slippage_always_worsens_the_price() -> None:
    for price in (1.5, 2.0, 2.02, 3.0, 6.0, 20.0):
        assert worsen_one_tick(price) < price


def test_slippage_lands_on_the_canonical_ladder() -> None:
    from price_contracts.ladder import is_on_ladder
    from decimal import Decimal

    for price in (1.5, 2.0, 3.0, 6.0, 20.0):
        assert is_on_ladder(Decimal(str(worsen_one_tick(price))))


def test_a_zero_edge_strategy_loses_roughly_the_costs() -> None:
    """The sanity check every betting backtest needs: bet with no edge at a fair price and
    the simulator must return the cost of trading, not a profit."""
    predictions = [
        Prediction(_match((i % 28) + 1, f"A{i}", f"B{i}", winner_is_a=(i % 2 == 0),
                          pinnacle=(2.0, 2.0)),
                   0.5, 0.5, 1 if i % 2 == 0 else 0)
        for i in range(400)
    ]
    summary = simulate_bets(predictions, edge_threshold=-1.0, commission=0.05)
    assert summary.roi < 0.0, "a zero-edge strategy must not show a profit"


def test_simulate_bets_refuses_when_nothing_qualifies() -> None:
    predictions = [Prediction(_match(1, "A", "B"), 0.01, 0.5, 1)]
    with pytest.raises(ValueError):
        simulate_bets(predictions, edge_threshold=10.0)


def test_trial_log_counts_every_variant_tried() -> None:
    log = TrialLog()
    log.record("elo", "k=32")
    log.record("elo", "k=24")
    assert log.trials == 2
    assert "2 strategy variants" in log.report()
