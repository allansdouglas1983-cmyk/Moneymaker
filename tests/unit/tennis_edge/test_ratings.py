"""Rating engine tests. The engine is a feature producer, but a broken one would poison
every feature downstream, so its update rules are pinned."""
from __future__ import annotations

import datetime as dt

import pytest

from tennis_edge.corpus import Completion, Match, OddsQuotes
from tennis_edge.features import (
    BANNED_FEATURE_TOKENS,
    FEATURE_NAMES,
    assert_no_price_features,
    build_features,
)
from tennis_edge.ratings import INITIAL_RATING, RatingConfig, RatingEngine, elo_expected


def _match(day: int, winner: str, loser: str, *, surface: str = "Hard",
           tier: str = "ATP250", games_w: int = 12, games_l: int = 7,
           month: int = 1) -> Match:
    winner_is_a = winner < loser
    a, b = (winner, loser) if winner_is_a else (loser, winner)
    games_a, games_b = (games_w, games_l) if winner_is_a else (games_l, games_w)
    return Match(
        match_date=dt.date(2024, month, day), tour="ATP", tournament="T", location="L",
        tier=tier, court="Outdoor", surface=surface, round_name="R1", best_of=3,
        player_a=a, player_b=b, winner_is_a=winner_is_a,
        rank_a=10, rank_b=20, points_a=1000, points_b=500,
        games_a=games_a, games_b=games_b, sets_a=2, sets_b=0,
        completion=Completion.COMPLETED, odds=OddsQuotes(), source_file="test",
    )


def test_equal_ratings_give_exactly_a_coin_flip() -> None:
    assert elo_expected(1500.0, 1500.0) == 0.5


def test_a_four_hundred_point_lead_is_ten_to_one() -> None:
    assert elo_expected(1900.0, 1500.0) == pytest.approx(10 / 11)


def test_everyone_starts_at_the_initial_rating() -> None:
    engine = RatingEngine()
    assert engine.elo("ATP", "nobody") == INITIAL_RATING
    assert engine.surface_elo("ATP", "nobody", "Clay") == INITIAL_RATING


def test_winning_raises_the_winner_and_lowers_the_loser_symmetrically() -> None:
    engine = RatingEngine()
    engine.observe([_match(1, "Alice", "Bob")])
    assert engine.elo("ATP", "Alice") > INITIAL_RATING
    assert engine.elo("ATP", "Bob") < INITIAL_RATING
    gained = engine.elo("ATP", "Alice") - INITIAL_RATING
    lost = INITIAL_RATING - engine.elo("ATP", "Bob")
    assert gained == pytest.approx(lost), "the first update must be zero-sum"


def test_a_days_results_are_invariant_to_the_order_they_are_listed() -> None:
    """Batch updating is what stops a morning result informing an afternoon prediction. If
    ordering mattered, that guarantee would be false."""
    day = [_match(1, "Alice", "Bob"), _match(1, "Cara", "Alice"), _match(1, "Bob", "Dan")]
    forward, backward = RatingEngine(), RatingEngine()
    forward.observe(day)
    backward.observe(list(reversed(day)))
    for player in ("Alice", "Bob", "Cara", "Dan"):
        assert forward.elo("ATP", player) == pytest.approx(backward.elo("ATP", player))


def test_the_k_factor_decays_with_experience() -> None:
    config = RatingConfig()
    assert config.k_factor(0, grand_slam=False) > config.k_factor(50, grand_slam=False)
    assert config.k_factor(50, grand_slam=False) > config.k_factor(500, grand_slam=False)


def test_grand_slams_move_ratings_further() -> None:
    config = RatingConfig()
    assert config.k_factor(10, grand_slam=True) == pytest.approx(
        config.k_factor(10, grand_slam=False) * 1.1
    )


def test_a_surface_rating_starts_from_the_overall_rating_not_from_scratch() -> None:
    """A top player's first clay match must not price them as average."""
    engine = RatingEngine()
    for day in range(1, 15):
        engine.observe([_match(day, "Alice", f"Opp{day}")])
    assert engine.elo("ATP", "Alice") > INITIAL_RATING + 20
    assert engine.surface_elo("ATP", "Alice", "Clay") == engine.elo("ATP", "Alice")


def test_weighted_elo_never_exceeds_plain_elo_for_a_winner() -> None:
    """Angelini's margin weight is at most 1, so the weighted rating is bounded above by
    the plain one — the gap between them is the form signal the features use."""
    engine = RatingEngine()
    for day in range(1, 10):
        engine.observe([_match(day, "Alice", f"Opp{day}", games_w=7, games_l=6)])
    assert engine.weighted_elo("ATP", "Alice") <= engine.elo("ATP", "Alice") + 1e-9


def test_a_crushing_win_moves_weighted_elo_more_than_a_narrow_one() -> None:
    crush, narrow = RatingEngine(), RatingEngine()
    crush.observe([_match(1, "Alice", "Bob", games_w=12, games_l=0)])
    narrow.observe([_match(1, "Alice", "Bob", games_w=13, games_l=12)])
    assert crush.weighted_elo("ATP", "Alice") > narrow.weighted_elo("ATP", "Alice")


def test_head_to_head_is_reported_from_the_asking_players_side() -> None:
    engine = RatingEngine()
    engine.observe([_match(1, "Alice", "Bob")])
    engine.observe([_match(2, "Alice", "Bob")])
    engine.observe([_match(3, "Bob", "Alice")])
    assert engine.head_to_head("ATP", "Alice", "Bob") == (2, 1)
    assert engine.head_to_head("ATP", "Bob", "Alice") == (1, 2)


def test_rest_and_workload_track_the_calendar() -> None:
    engine = RatingEngine()
    engine.observe([_match(1, "Alice", "Bob", games_w=12, games_l=7)])
    assert engine.days_since_last("ATP", "Alice", dt.date(2024, 1, 8)) == 7
    assert engine.games_in_last("ATP", "Alice", dt.date(2024, 1, 8), 14) == 19
    assert engine.games_in_last("ATP", "Alice", dt.date(2024, 3, 1), 14) == 0


def test_unfinished_matches_do_not_move_ratings() -> None:
    engine = RatingEngine()
    retired = Match(
        match_date=dt.date(2024, 1, 1), tour="ATP", tournament="T", location="L",
        tier="ATP250", court="Outdoor", surface="Hard", round_name="R1", best_of=3,
        player_a="Alice", player_b="Bob", winner_is_a=True,
        rank_a=1, rank_b=2, points_a=None, points_b=None,
        games_a=6, games_b=2, sets_a=1, sets_b=0, completion=Completion.RETIRED,
        odds=OddsQuotes(), source_file="test",
    )
    engine.observe([retired])
    assert engine.elo("ATP", "Alice") == INITIAL_RATING


# ------------------------------------------------------------------------ features


def test_no_feature_is_derived_from_a_price() -> None:
    """The guard that keeps the experiment honest: the market may only enter as an offset."""
    assert_no_price_features()
    for name in FEATURE_NAMES:
        assert not any(token in name.lower() for token in BANNED_FEATURE_TOKENS)


def test_a_price_shaped_feature_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        assert_no_price_features(["elo_diff", "market_implied_probability"])


def test_the_feature_vector_matches_the_declared_names() -> None:
    engine = RatingEngine()
    values = build_features(engine, _match(1, "Alice", "Bob"))
    assert len(values) == len(FEATURE_NAMES)


def test_features_of_an_unplayed_pairing_are_symmetric_and_neutral() -> None:
    """With no history, every difference feature must be exactly zero. A non-zero value
    would mean the builder is leaking something about the fixture itself."""
    engine = RatingEngine()
    values = dict(zip(FEATURE_NAMES, build_features(engine, _match(1, "Alice", "Bob"))))
    for name in ("elo_diff", "surface_elo_diff", "blended_elo_diff", "weighted_elo_diff",
                 "h2h_diff", "h2h_total", "experience_diff", "rest_diff"):
        assert values[name] == 0.0, f"{name} should be neutral with no history"


def test_features_reflect_history_once_it_exists() -> None:
    engine = RatingEngine()
    for day in range(1, 6):
        engine.observe([_match(day, "Alice", f"Opp{day}")])
    values = dict(zip(FEATURE_NAMES, build_features(engine, _match(10, "Alice", "Bob"))))
    assert values["elo_diff"] > 0.0
    assert values["experience_diff"] > 0.0
