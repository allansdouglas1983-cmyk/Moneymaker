"""Point-model tests, checked against the published closed forms.

The recursions are the implementation; O'Malley's and Klaassen & Magnus's closed forms are
the independent check. Testing a recursion against itself would prove nothing, so every
structural identity here comes from the literature or from the rules of tennis.
"""
from __future__ import annotations

import pytest

from tennis_edge.point_model import (
    game_probability,
    match_probability,
    serve_difference_sensitivity,
    set_probability,
    tiebreak_probability,
)


def _omalley_game(p: float) -> float:
    """O'Malley (2008) eq. 9 closed form for P(hold)."""
    return p**4 * (15.0 - 4.0 * p - (10.0 * p**2) / (1.0 - 2.0 * p * (1.0 - p)))


def _klaassen_magnus_game(p: float) -> float:
    """Klaassen & Magnus (2003) eq. 1 — algebraically identical, independently stated."""
    return (
        p**4 * (-8.0 * p**3 + 28.0 * p**2 - 34.0 * p + 15.0) / (p**2 + (1.0 - p) ** 2)
    )


@pytest.mark.parametrize("p", [0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75, 0.80])
def test_game_recursion_matches_both_published_closed_forms(p: float) -> None:
    recursion = game_probability(p)
    assert recursion == pytest.approx(_omalley_game(p), abs=1e-12)
    assert recursion == pytest.approx(_klaassen_magnus_game(p), abs=1e-12)


def test_published_hold_probabilities() -> None:
    """Spot values quoted in the literature."""
    assert game_probability(0.50) == pytest.approx(0.5, abs=1e-12)
    assert game_probability(0.60) == pytest.approx(0.735729, abs=1e-6)
    assert game_probability(0.65) == pytest.approx(0.829645, abs=1e-6)
    assert game_probability(0.70) == pytest.approx(0.900789, abs=1e-6)


def test_no_advantage_scoring_makes_breaks_more_likely() -> None:
    """A single deciding point at deuce favours the returner relative to two-clear."""
    standard = game_probability(0.65)
    sudden = game_probability(0.65, no_advantage=True)
    assert sudden < standard
    assert sudden == pytest.approx(0.800, abs=1e-3)
    assert standard == pytest.approx(0.830, abs=1e-3)


@pytest.mark.parametrize("p", [0.5, 0.6, 0.62, 0.7])
def test_a_perfectly_matched_pair_is_a_coin_flip_at_every_level(p: float) -> None:
    """The identity that catches an argument-order mix-up: if A's serve strength equals B's,
    every level of the hierarchy must return exactly one half."""
    assert tiebreak_probability(p, 1.0 - p) == pytest.approx(0.5, abs=1e-9)
    assert set_probability(p, 1.0 - p) == pytest.approx(0.5, abs=1e-9)
    assert match_probability(p, 1.0 - p, best_of=3) == pytest.approx(0.5, abs=1e-9)
    assert match_probability(p, 1.0 - p, best_of=5) == pytest.approx(0.5, abs=1e-9)


def test_every_level_is_monotone_in_serve_strength() -> None:
    previous_set = previous_match = 0.0
    for p in (0.55, 0.58, 0.61, 0.64, 0.67, 0.70):
        current_set = set_probability(p, 1.0 - 0.62)
        current_match = match_probability(p, 1.0 - 0.62)
        assert current_set > previous_set
        assert current_match > previous_match
        previous_set, previous_match = current_set, current_match


def test_best_of_five_amplifies_the_stronger_player() -> None:
    """More sets means less variance, so the favourite's edge grows."""
    three = match_probability(0.65, 1.0 - 0.60, best_of=3)
    five = match_probability(0.65, 1.0 - 0.60, best_of=5)
    assert five > three > 0.5


def test_only_best_of_three_or_five_are_accepted() -> None:
    with pytest.raises(ValueError):
        match_probability(0.62, 0.38, best_of=4)


def test_the_difference_dominates_the_sum() -> None:
    """Klaassen & Magnus's central finding, and the reason the serve estimator matters more
    than the scoring model: hold the difference fixed, sweep the sum across its whole
    empirical range, and the match probability barely moves."""
    outcomes = []
    for total in (1.10, 1.20, 1.30, 1.40):
        p_a = (total + 0.05) / 2.0
        p_b = (total - 0.05) / 2.0
        outcomes.append(match_probability(p_a, 1.0 - p_b))
    assert max(outcomes) - min(outcomes) < 0.04, "the sum should barely matter"
    assert all(value > 0.70 for value in outcomes), "the difference should dominate"


def test_leverage_is_about_five_points_per_point_of_serve_difference() -> None:
    """Pins the sensitivity that sets the precision requirement on the serve estimator."""
    sensitivity = serve_difference_sensitivity(0.62, 0.01, best_of=3)
    assert 4.0 < sensitivity < 6.0


def test_an_advantage_final_set_helps_the_stronger_server() -> None:
    tiebreak = match_probability(0.66, 1.0 - 0.60, best_of=5)
    advantage = match_probability(0.66, 1.0 - 0.60, best_of=5, advantage_final_set=True)
    assert advantage >= tiebreak


def test_probabilities_stay_inside_the_unit_interval_at_the_extremes() -> None:
    for p_serve, p_return in ((0.99, 0.99), (0.01, 0.01), (0.99, 0.01), (0.01, 0.99)):
        for best_of in (3, 5):
            value = match_probability(p_serve, p_return, best_of=best_of)
            assert 0.0 <= value <= 1.0
