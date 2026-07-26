"""Price upcoming matches with a frozen model. The part a person actually runs.

Everything else in this package measures the past. This turns a fitted
:class:`~tennis_edge.residual_model.ResidualModel` on a fixture that has not been played,
and it is therefore the only module where a mistake reaches a decision rather than a report.

**What it produces, and what it deliberately does not.** For each fixture: the de-vigged
market probability, the model's corrected probability, fair odds, the commission-aware
break-even, and the edge against it. It does **not** produce a recommendation.
``recommendation`` is hard-pinned to ``NOT_EVALUATED`` and a test asserts no combination of
inputs can move it — no coefficient, no edge, no price. That is not caution for its own
sake: TE-0007 measured the model's exchange performance as undecided at the available power,
and a tool that emitted "BET" off an undecided measurement would be converting a statistical
non-result into a financial one.

**Break-even is commission-aware, and that is not a detail.** On an exchange, commission is
charged on net winnings, so the price at which a bet breaks even is
``p = 1 / (1 + (O-1)(1-c))``, not ``1/O``. Using ``1/O`` makes two errors at once: it accepts
bets that are not actually positive-EV, and then settles them at the gross price. This is the
SPEC-110 formula and it is exact-arithmetic on the price side.

**Features come from the same builder as the evidence.** A fixture is priced from the state
of the rating, serve and pyramid engines advanced to the day before it — the identical code
path that produced every number in TE-0005 through TE-0007. A predictor that computed its
features differently from the harness that validated it would be an untested model wearing a
tested one's confidence interval.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from tennis_edge.devig import DevigMethod, devig
from tennis_edge.exchange import COMMISSION
from tennis_edge.residual_model import ResidualModel

__all__ = [
    "Fixture",
    "UpcomingPrediction",
    "break_even_probability",
    "price_fixture",
]


@dataclass(frozen=True)
class Fixture:
    """A match that has not been played, with the prices currently quoted on it."""

    date: dt.date
    tour: str
    player_a: str
    player_b: str
    surface: str
    best_of: int
    odds_a: Decimal
    odds_b: Decimal


@dataclass(frozen=True)
class UpcomingPrediction:
    """One fixture priced, with everything needed to audit the number later."""

    fixture: Fixture
    market_probability_a: float
    market_probability_b: float
    probability_a: float
    probability_b: float
    fair_odds_a: Decimal
    fair_odds_b: Decimal
    break_even_a: float
    break_even_b: float
    edge_a: float
    edge_b: float
    commission: Decimal
    features: Mapping[str, float]
    model_digest: str
    #: Hard-pinned. This tool states probabilities; it never authorises a bet.
    recommendation: str = "NOT_EVALUATED"

    def render(self) -> str:
        return (
            f"{self.fixture.date} {self.fixture.tour}  "
            f"{self.fixture.player_a} v {self.fixture.player_b}\n"
            f"    market {self.market_probability_a:.4f} / "
            f"{self.market_probability_b:.4f}   "
            f"model {self.probability_a:.4f} / {self.probability_b:.4f}\n"
            f"    quoted {self.fixture.odds_a} / {self.fixture.odds_b}   "
            f"fair {self.fair_odds_a} / {self.fair_odds_b}\n"
            f"    edge over commission-aware break-even: "
            f"A {self.edge_a:+.4f}  B {self.edge_b:+.4f}\n"
            f"    recommendation: {self.recommendation}  "
            f"(research/shadow only — this authorises no stake)"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "date": self.fixture.date.isoformat(),
            "tour": self.fixture.tour,
            "player_a": self.fixture.player_a,
            "player_b": self.fixture.player_b,
            "surface": self.fixture.surface,
            "best_of": self.fixture.best_of,
            "odds_a": str(self.fixture.odds_a),
            "odds_b": str(self.fixture.odds_b),
            "market_probability_a": self.market_probability_a,
            "probability_a": self.probability_a,
            "fair_odds_a": str(self.fair_odds_a),
            "fair_odds_b": str(self.fair_odds_b),
            "break_even_a": self.break_even_a,
            "break_even_b": self.break_even_b,
            "edge_a": self.edge_a,
            "edge_b": self.edge_b,
            "commission": str(self.commission),
            "features": dict(sorted(self.features.items())),
            "model_digest": self.model_digest,
            "recommendation": self.recommendation,
        }


def break_even_probability(odds: Decimal, *, commission: Decimal = COMMISSION) -> float:
    """``1 / (1 + (O-1)(1-c))`` — the probability at which a back bet breaks even.

    Not ``1/O``. Commission is charged on net winnings, so it raises the bar twice over:
    the bet needs a higher true probability to be worth taking, and the settlement pays less
    than the quote implies. Conflating the two credits a strategy with money the exchange
    keeps, and the error is invisible in a backtest that makes it consistently.
    """
    if odds <= 1:
        raise ValueError(f"decimal odds must be above 1, got {odds}")
    net = Decimal(1) + (odds - Decimal(1)) * (Decimal(1) - commission)
    return float(Decimal(1) / net)


def _fair(probability: float) -> Decimal:
    return (Decimal(1) / Decimal(str(probability))).quantize(Decimal("0.001"))


def price_fixture(
    fixture: Fixture,
    features: Mapping[str, float],
    model: ResidualModel,
    *,
    commission: Decimal = COMMISSION,
    method: DevigMethod = DevigMethod.POWER,
) -> UpcomingPrediction:
    """Turn a fixture and its features into a probability, fair odds and an edge.

    The market probability is de-vigged from the quoted pair by the same method used
    throughout the evidence, so the offset the model corrects is the same quantity it was
    fitted against. Feeding a raw ``1/O`` in here instead would shift every prediction by the
    market's margin.
    """
    # Decimal on the price side, float for the de-vig: the margin removal is an iterative
    # numerical solve with no exact rational answer, so carrying Decimal into it would be a
    # precision claim the method cannot support. Money arithmetic stays Decimal.
    market_a, market_b = devig(
        (float(fixture.odds_a), float(fixture.odds_b)), method
    ).probabilities
    market_logit = math.log(
        min(max(market_a, 1e-12), 1 - 1e-12) / (1 - min(max(market_a, 1e-12), 1 - 1e-12))
    )
    probability_a = model.probability(market_logit, features)
    probability_b = 1.0 - probability_a
    break_even_a = break_even_probability(fixture.odds_a, commission=commission)
    break_even_b = break_even_probability(fixture.odds_b, commission=commission)
    return UpcomingPrediction(
        fixture=fixture,
        market_probability_a=market_a,
        market_probability_b=market_b,
        probability_a=probability_a,
        probability_b=probability_b,
        fair_odds_a=_fair(probability_a),
        fair_odds_b=_fair(probability_b),
        break_even_a=break_even_a,
        break_even_b=break_even_b,
        edge_a=probability_a - break_even_a,
        edge_b=probability_b - break_even_b,
        commission=commission,
        features=dict(features),
        model_digest=model.digest,
    )
