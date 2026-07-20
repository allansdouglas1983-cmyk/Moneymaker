"""SPEC-105/SPEC-106 properties (Stage 2G Slice 2; founder directive §20).

Required properties encoded here:
- probabilities coherent and finite;
- higher player strength increases win probability;
- greater uncertainty widens the interval;
- inactivity cannot reduce uncertainty without new evidence;
- row order within a day does not alter predictions (EXACT — batch update via fsum);
- winner/loser reversal is direction-visible (reversal mutants die).
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow
from sport_core.clustering import calendar_day_assignment
from sport_tennis.dp1_distribution import (
    PROBABILITY_FLOOR,
    central_win_probability,
    interval_bounds,
)
from sport_tennis.glicko2_family import (
    Glicko2Family,
    PlayerState,
    inactivity_step,
    rate_player,
)

pytestmark = [pytest.mark.spec("SPEC-105"), pytest.mark.spec("SPEC-106")]

_SCHEMA = FeatureSchema(names=("placeholder",))
_HORIZON = HorizonLabel("pre-off-tennis")
_D0 = Decimal("0")

_mu = st.floats(min_value=-3.0, max_value=3.0, allow_nan=False)
_phi = st.floats(min_value=0.02, max_value=2.5, allow_nan=False)
_sigma = st.floats(min_value=0.01, max_value=0.12, allow_nan=False)
_s = st.floats(min_value=0.0, max_value=4.0, allow_nan=False)


def _race(race_id: str, day: date, a: int, b: int, winner: int | None) -> Race:
    return Race(
        race_id=race_id,
        cluster=calendar_day_assignment("tennis", day),
        runners=(
            RunnerRow(runner_id=a, features={"placeholder": _D0}),
            RunnerRow(runner_id=b, features={"placeholder": _D0}),
        ),
        winner_id=winner,
    )


@given(delta=st.floats(min_value=-6.0, max_value=6.0), s=_s)
@settings(max_examples=200, deadline=None)
def test_central_probability_coherent_and_finite(delta: float, s: float) -> None:
    p = central_win_probability(delta, s)
    q = central_win_probability(-delta, s)
    assert math.isfinite(p)
    assert PROBABILITY_FLOOR <= p <= 1.0 - PROBABILITY_FLOOR
    # complement symmetry of the frozen symmetric quadrature rule
    assert p + q == pytest.approx(1.0, abs=1e-12)


@given(
    delta_lo=st.floats(min_value=-4.0, max_value=4.0),
    bump=st.floats(min_value=1e-3, max_value=3.0),
    s=_s,
)
@settings(max_examples=200, deadline=None)
def test_higher_strength_increases_probability(delta_lo: float, bump: float, s: float) -> None:
    assert central_win_probability(delta_lo + bump, s) > central_win_probability(delta_lo, s)


@given(
    delta=st.floats(min_value=-4.0, max_value=4.0),
    s_lo=st.floats(min_value=0.0, max_value=3.0),
    bump=st.floats(min_value=1e-3, max_value=2.0),
)
@settings(max_examples=200, deadline=None)
def test_greater_uncertainty_widens_interval(delta: float, s_lo: float, bump: float) -> None:
    lo1, up1 = interval_bounds(delta, s_lo)
    lo2, up2 = interval_bounds(delta, s_lo + bump)
    assert (up2 - lo2) > (up1 - lo1)
    assert lo2 <= lo1 and up2 >= up1


@given(mu=_mu, phi=_phi, sigma=_sigma, steps=st.integers(min_value=1, max_value=40))
@settings(max_examples=200, deadline=None)
def test_inactivity_never_reduces_uncertainty(mu: float, phi: float, sigma: float, steps: int) -> None:
    state = PlayerState(mu=mu, phi=phi, sigma=sigma)
    for _ in range(steps):
        nxt = inactivity_step(state)
        assert nxt.phi > state.phi
        assert nxt.mu == state.mu
        assert nxt.sigma == state.sigma
        state = nxt


@given(mu=_mu, phi=_phi, sigma=_sigma, opp_mu=_mu, opp_phi=_phi)
@settings(max_examples=200, deadline=None)
def test_win_moves_rating_up_loss_moves_it_down(
    mu: float, phi: float, sigma: float, opp_mu: float, opp_phi: float
) -> None:
    """Winner/loser reversal is visible in the update direction (kills reversal mutants)."""
    player = PlayerState(mu=mu, phi=phi, sigma=sigma)
    opp = PlayerState(mu=opp_mu, phi=opp_phi, sigma=sigma)
    won = rate_player(player, [(opp, 1.0)])
    lost = rate_player(player, [(opp, 0.0)])
    assert won.mu > player.mu
    assert lost.mu < player.mu
    assert won.mu > lost.mu


@given(
    data=st.lists(
        st.tuples(st.integers(min_value=0, max_value=5), st.booleans()),
        min_size=1,
        max_size=8,
    ),
    seed=st.randoms(use_true_random=False),
)
@settings(max_examples=60, deadline=None)
def test_same_day_permutation_invariance(data: list[tuple[int, bool]], seed: random.Random) -> None:
    """Row order within a UTC day never alters the fitted model's predictions — EXACT."""
    day = date(2025, 4, 1)
    players = [(10 + i, 20 + i) for i, _ in enumerate(data)]
    races = [
        _race(f"m{i}", day, a, b, winner=(a if first_wins else b))
        for i, ((_, first_wins), (a, b)) in enumerate(zip(data, players))
    ]
    shuffled = list(races)
    seed.shuffle(shuffled)
    fam = Glicko2Family()
    m1 = fam.fit(races, _SCHEMA, horizon=_HORIZON, max_iter=10)
    m2 = fam.fit(shuffled, _SCHEMA, horizon=_HORIZON, max_iter=10)
    probe_day = day + timedelta(days=3)
    for a, b in players:
        p1 = fam.predict(m1, _race("probe", probe_day, a, b, None), horizon=_HORIZON)
        p2 = fam.predict(m2, _race("probe", probe_day, a, b, None), horizon=_HORIZON)
        assert p1 == p2  # exact equality, not approximate


@given(gap=st.integers(min_value=1, max_value=400))
@settings(max_examples=60, deadline=None)
def test_longer_gap_never_sharpens_a_prediction(gap: int) -> None:
    """Elapsed idle time monotonically shrinks the favourite's edge toward 1/2."""
    fam = Glicko2Family()
    train = [_race(f"t{i}", date(2025, 1, 1) + timedelta(days=i), 1, 2, winner=1) for i in range(3)]
    model = fam.fit(train, _SCHEMA, horizon=_HORIZON, max_iter=10)
    base_day = date(2025, 1, 4)
    p_base = fam.predict(model, _race("p0", base_day, 1, 2, None), horizon=_HORIZON)[1]
    p_gap = fam.predict(model, _race("p1", base_day + timedelta(days=gap), 1, 2, None), horizon=_HORIZON)[1]
    assert 0.5 < p_gap <= p_base
