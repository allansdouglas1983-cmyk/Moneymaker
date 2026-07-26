"""Tests for the residual-model policy.

v1 treats the market as the answer and the model as a labelled challenger, because when it
was frozen four architectures had come back flat. TE-0007 changed that premise: a model that
beats the closing price now exists. v2 is a *new vintage* rather than an edit — v1's ledger
rows still mean what they meant, and these tests pin the boundary between them as much as
they pin the new rule.
"""
from __future__ import annotations

import datetime as dt

import pytest

from tennis_edge.policy import POLICY_VERSION as V1_VERSION
from tennis_edge.policy import policy_digest as v1_digest
from tennis_edge.policy_v2 import (
    MIN_EDGE,
    POLICY_VERSION,
    Status,
    decide_v2,
    policy_digest_v2,
)
from tennis_edge.residual_model import ResidualModel


def model(**coefficients: float) -> ResidualModel:
    return ResidualModel(
        coefficients=dict(coefficients) or {"rank_gap": 0.0},
        feature_names=tuple(coefficients) or ("rank_gap",),
        l2=25.0, trained_rows=90_000,
        trained_from=dt.date(2002, 6, 10), trained_through=dt.date(2026, 7, 12),
        feature_set_version="residual-v1",
    )


class TestVintageSeparation:
    """v2 must never be mistakable for v1 in a ledger row."""

    def test_the_versions_differ(self) -> None:
        assert POLICY_VERSION != V1_VERSION

    def test_the_digests_differ(self) -> None:
        assert policy_digest_v2(model(rank_gap=0.1)) != v1_digest()

    def test_the_digest_includes_the_model(self) -> None:
        """Two policies with identical thresholds but different models are different rules."""
        assert (policy_digest_v2(model(rank_gap=0.1))
                != policy_digest_v2(model(rank_gap=0.2)))

    def test_the_digest_is_stable_for_the_same_model(self) -> None:
        assert policy_digest_v2(model(rank_gap=0.1)) == policy_digest_v2(
            model(rank_gap=0.1))


class TestDecisions:
    def test_no_price_blocks(self) -> None:
        """A rule that guessed a price would be recording fiction, not evidence."""
        decision = decide_v2(market_probability_a=None, features={},
                             odds_a=2.0, odds_b=2.0, model=model(rank_gap=0.1))
        assert decision.status is Status.BLOCKED

    def test_no_edge_is_no_bet(self) -> None:
        decision = decide_v2(market_probability_a=0.5, features={},
                             odds_a=2.0, odds_b=2.0, model=model(rank_gap=0.0))
        assert decision.status is Status.NO_BET

    def test_a_large_positive_edge_recommends_that_side(self) -> None:
        decision = decide_v2(market_probability_a=0.5, features={"rank_gap": 5.0},
                             odds_a=3.0, odds_b=1.5, model=model(rank_gap=0.5))
        assert decision.status is Status.RECOMMEND_A
        assert decision.side == "A"

    def test_the_other_side_is_reachable(self) -> None:
        decision = decide_v2(market_probability_a=0.5, features={"rank_gap": -5.0},
                             odds_a=1.5, odds_b=3.0, model=model(rank_gap=0.5))
        assert decision.status is Status.RECOMMEND_B
        assert decision.side == "B"

    def test_edge_below_the_minimum_only_watches(self) -> None:
        """The threshold exists so a rule that fires on every match cannot look selective."""
        tiny = MIN_EDGE / 2
        decision = decide_v2(market_probability_a=0.5 + tiny, features={},
                             odds_a=2.0, odds_b=2.0, model=model(rank_gap=0.0))
        assert decision.status in {Status.WATCH, Status.NO_BET}
        assert decision.status is not Status.RECOMMEND_A


class TestCommission:
    def test_commission_is_charged_on_the_break_even(self) -> None:
        """Without it the rule takes bets that are not actually positive-expectation."""
        # p = 0.51 at evens clears 1/O = 0.50 but not the commission-aware break-even.
        decision = decide_v2(market_probability_a=0.51, features={},
                             odds_a=2.0, odds_b=2.0, model=model(rank_gap=0.0))
        assert decision.status is not Status.RECOMMEND_A

    def test_worse_odds_never_improve_the_decision(self) -> None:
        strong = decide_v2(market_probability_a=0.6, features={}, odds_a=3.0,
                           odds_b=1.5, model=model(rank_gap=0.0))
        weak = decide_v2(market_probability_a=0.6, features={}, odds_a=1.7,
                         odds_b=1.5, model=model(rank_gap=0.0))
        assert not (weak.status is Status.RECOMMEND_A
                    and strong.status is not Status.RECOMMEND_A)


class TestMetamorphic:
    def test_raising_the_model_probability_never_worsens_side_a(self) -> None:
        statuses = []
        for value in (-3.0, 0.0, 3.0):
            statuses.append(decide_v2(
                market_probability_a=0.5, features={"rank_gap": value},
                odds_a=2.2, odds_b=1.8, model=model(rank_gap=0.4)).edge_a)
        assert statuses == sorted(statuses)

    def test_the_decision_is_symmetric_under_relabelling(self) -> None:
        """Swapping the two players must swap the recommendation, never invent one."""
        forward = decide_v2(market_probability_a=0.4, features={"rank_gap": 2.0},
                            odds_a=3.0, odds_b=1.4, model=model(rank_gap=0.3))
        mirrored = decide_v2(market_probability_a=0.6, features={"rank_gap": -2.0},
                             odds_a=1.4, odds_b=3.0, model=model(rank_gap=0.3))
        assert forward.edge_a == pytest.approx(mirrored.edge_b)


def test_min_edge_is_a_declared_constant() -> None:
    """Part of the digest, so a change starts a new vintage rather than redefining this one."""
    assert MIN_EDGE > 0.0
