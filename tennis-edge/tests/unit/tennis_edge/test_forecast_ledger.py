"""The automatic forecast ledger — the scorecard that fills itself.

The manual ledger only grows when a price is typed in, and after a month live it holds
zero rows. This module scores the served model against the Bet365 baseline on every
completed corpus match, using the PREVIOUS week's committed state — a file that provably
existed in git before the matches were played, so knowledge-time is enforced by the
commit history rather than by trust.

What must hold: a match the state has already absorbed is refused, never scored; a match
already in the ledger is never re-emitted; a missing market price is a typed exclusion,
never a default; a player the state cannot support is a typed exclusion; and the emitted
probability is exactly the one the site would have served — same features, same model,
same arithmetic.
"""
from __future__ import annotations

import datetime as dt
import math

from tennis_edge.corpus import Completion, Match, OddsQuotes
from tennis_edge.forecast_ledger import weekly_forecasts
from tennis_edge.live_state import PlayerState, StateSnapshot, live_features
from tennis_edge.residual_model import ResidualModel


def player(**overrides: object) -> PlayerState:
    fields: dict[str, object] = {
        "elo": 1600.0, "weighted_elo": 1580.0, "surface_elo": {"Hard": 1620.0},
        "matches": 40, "last_played": "2026-07-01",
        "serve_rate": 0.64, "return_rate": 0.37, "serve_points": 900.0,
        "serve_matches": 30,
        "pyramid_elo": 1650.0, "pyramid_surface_elo": {"Hard": 1660.0},
        "pyramid_matches": 120, "pyramid_tour_share": 0.6,
        "pyramid_last_played": "2026-07-01", "pyramid_recent_14d": 2,
    }
    fields.update(overrides)
    return PlayerState(**fields)  # type: ignore[arg-type]


def snapshot(**overrides: object) -> StateSnapshot:
    fields: dict[str, object] = {
        "as_of": dt.date(2026, 7, 20),
        "corpus_vintage": "vintage-2026-07-18",
        "players": {("ATP", "Smith A."): player(),
                    ("ATP", "Jones B."): player(elo=1500.0, weighted_elo=1490.0,
                                                surface_elo={"Hard": 1510.0},
                                                pyramid_elo=1520.0,
                                                pyramid_surface_elo={"Hard": 1530.0},
                                                pyramid_tour_share=0.2,
                                                pyramid_recent_14d=0)},
        "tour_serve_baseline": {"ATP": 0.63},
    }
    fields.update(overrides)
    return StateSnapshot(**fields)  # type: ignore[arg-type]


def model() -> ResidualModel:
    from tennis_edge.residual_features import RESIDUAL_FEATURE_NAMES
    return ResidualModel(
        coefficients={name: 0.05 for name in RESIDUAL_FEATURE_NAMES},
        feature_names=tuple(RESIDUAL_FEATURE_NAMES),
        l2=25.0, trained_rows=1000,
        trained_from=dt.date(2020, 1, 1), trained_through=dt.date(2026, 7, 12),
        feature_set_version="residual-v1",
    )


def match(**overrides: object) -> Match:
    fields: dict[str, object] = {
        "match_date": dt.date(2026, 7, 22), "tour": "ATP", "tournament": "Test Open",
        "location": "Testville", "tier": "ATP250", "court": "Outdoor",
        "surface": "Hard", "round_name": "1st Round", "best_of": 3,
        "player_a": "Smith A.", "player_b": "Jones B.", "winner_is_a": True,
        "rank_a": 10, "rank_b": 60, "points_a": None, "points_b": None,
        "games_a": None, "games_b": None, "sets_a": 2, "sets_b": 0,
        "completion": Completion.COMPLETED,
        "odds": OddsQuotes(b365_a=1.5, b365_b=2.6), "source_file": "test.xlsx",
    }
    fields.update(overrides)
    return Match(**fields)  # type: ignore[arg-type]


class TestKnowledgeTime:
    def test_a_match_the_state_already_absorbed_is_refused_not_scored(self) -> None:
        """A match before as_of is inside the state's own training walk — scoring it
        would grade the model on a result it had already been told."""
        rows, exclusions = weekly_forecasts(
            snapshot(), model(), [match(match_date=dt.date(2026, 7, 19))], set())
        assert rows == []
        assert exclusions["STATE_ALREADY_ABSORBED"] == 1


class TestDedup:
    def test_a_match_already_in_the_ledger_is_never_re_emitted(self) -> None:
        m = match()
        key = (m.match_date.isoformat(), m.tour, m.player_a, m.player_b)
        rows, exclusions = weekly_forecasts(snapshot(), model(), [m], {key})
        assert rows == []
        assert exclusions["ALREADY_RECORDED"] == 1


class TestTypedAbsence:
    def test_a_missing_market_price_is_an_exclusion_not_a_default(self) -> None:
        m = match(odds=OddsQuotes())
        rows, exclusions = weekly_forecasts(snapshot(), model(), [m], set())
        assert rows == []
        assert exclusions["NO_MARKET_PRICE"] == 1

    def test_a_player_the_state_cannot_support_is_an_exclusion(self) -> None:
        m = match(player_a="Nobody C.", winner_is_a=False)
        rows, exclusions = weekly_forecasts(snapshot(), model(), [m], set())
        assert rows == []
        assert exclusions["INSUFFICIENT_STATE"] == 1


class TestServedProbability:
    def test_the_row_reproduces_the_served_probability_exactly(self) -> None:
        """The ledger grades what the site would have shown — same features, same model,
        same arithmetic — or it grades a fiction."""
        snap, mod, m = snapshot(), model(), match()
        rows, _ = weekly_forecasts(snap, mod, [m], set())
        assert len(rows) == 1
        row = rows[0]
        p_market = (1 / 1.5) / (1 / 1.5 + 1 / 2.6)
        features = live_features(
            snap, "ATP", "Smith A.", "Jones B.", surface="Hard", best_of=3,
            market_probability=p_market, match_date=m.match_date,
            rank_a=10, rank_b=60)
        expected = mod.probability(math.log(p_market / (1 - p_market)), features)
        assert row["p_model"] == expected
        assert row["p_market"] == p_market
        assert row["won_a"] is True
        assert row["state_as_of"] == "2026-07-20"
        assert row["model_digest"] == mod.digest
