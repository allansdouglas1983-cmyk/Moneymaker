"""SPEC-105 — DYNAMIC_GLICKO2_V1 (Stage 2G Slice 2; red tests first).

Registration: specs/programme/dp1-glicko2-registration-v1.yaml. Constants are
founder-frozen (directive §5) and NOT tunable against performance; the family takes NO
tuning parameter. Golden values come from the pinned primary source (Glickman, "Example
of the Glicko-2 system", glicko.net/glicko/glicko2.pdf) — the worked example is encoded
verbatim as the canonical correctness witness.
"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest

from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow
from l4_pricing.stage_one import StageOneFamily, StageOneFitRefusal
from sport_core.clustering import calendar_day_assignment
from sport_tennis.glicko2_family import (
    GLICKO2_CONVERGENCE_TOLERANCE,
    GLICKO2_INITIAL_RATING,
    GLICKO2_INITIAL_RD,
    GLICKO2_INITIAL_VOLATILITY,
    GLICKO2_SCALE,
    GLICKO2_TAU,
    INITIAL_PLAYER_STATE,
    MAX_VOLATILITY_ITERATIONS,
    Glicko2ConvergenceError,
    Glicko2Family,
    PlayerState,
    inactivity_step,
    new_volatility,
    rate_player,
    volatility_converged,
    volatility_iteration_allowed,
)

pytestmark = pytest.mark.spec("SPEC-105")

_SCHEMA = FeatureSchema(names=("placeholder",))
_HORIZON = HorizonLabel("pre-off-tennis")


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


_D0 = Decimal("0")


class TestFrozenConstants:
    """Directive §5: one predeclared configuration, never tuned."""

    def test_exact_frozen_values(self) -> None:
        assert GLICKO2_INITIAL_RATING == 1500.0
        assert GLICKO2_INITIAL_RD == 350.0
        assert GLICKO2_INITIAL_VOLATILITY == 0.06
        assert GLICKO2_TAU == 0.5
        assert GLICKO2_CONVERGENCE_TOLERANCE == 1e-6
        assert GLICKO2_SCALE == 173.7178

    def test_family_takes_no_tuning_parameter(self) -> None:
        import inspect

        params = inspect.signature(Glicko2Family.__init__).parameters
        assert list(params) == ["self"], (
            "the constants are founder-frozen; a constructor knob would make them "
            f"tunable against performance — got parameters {list(params)}"
        )

    def test_initial_state_is_the_scaled_prior(self) -> None:
        assert INITIAL_PLAYER_STATE.mu == 0.0
        assert INITIAL_PLAYER_STATE.phi == pytest.approx(350.0 / GLICKO2_SCALE)
        assert INITIAL_PLAYER_STATE.sigma == 0.06
        assert INITIAL_PLAYER_STATE.rating == pytest.approx(1500.0)
        assert INITIAL_PLAYER_STATE.rating_deviation == pytest.approx(350.0)

    def test_family_conforms_to_the_stage_one_seam(self) -> None:
        assert isinstance(Glicko2Family(), StageOneFamily)
        assert Glicko2Family().family_id == "dynamic-glicko2-v1"


class TestGlickmanWorkedExample:
    """The paper's worked example, encoded verbatim (primary-source witness).

    Player r=1500 RD=200 sigma=0.06, tau=0.5; period results: beat (1400, RD 30),
    lost to (1550, RD 100), lost to (1700, RD 300). Paper's results: r'=1464.06,
    RD'=151.52, sigma'=0.05999.
    """

    def _updated(self) -> PlayerState:
        player = PlayerState(mu=0.0, phi=200.0 / GLICKO2_SCALE, sigma=0.06)
        opponents = [
            (PlayerState(mu=(1400.0 - 1500.0) / GLICKO2_SCALE, phi=30.0 / GLICKO2_SCALE, sigma=0.06), 1.0),
            (PlayerState(mu=(1550.0 - 1500.0) / GLICKO2_SCALE, phi=100.0 / GLICKO2_SCALE, sigma=0.06), 0.0),
            (PlayerState(mu=(1700.0 - 1500.0) / GLICKO2_SCALE, phi=300.0 / GLICKO2_SCALE, sigma=0.06), 0.0),
        ]
        return rate_player(player, opponents)

    def test_updated_rating_matches_the_paper(self) -> None:
        assert self._updated().rating == pytest.approx(1464.06, abs=0.05)

    def test_updated_deviation_matches_the_paper(self) -> None:
        assert self._updated().rating_deviation == pytest.approx(151.52, abs=0.05)

    def test_updated_volatility_matches_the_paper(self) -> None:
        assert self._updated().sigma == pytest.approx(0.05999, abs=5e-5)


class TestInactivity:
    """Registration: phi <- sqrt(phi^2 + sigma^2) per empty period; mu, sigma unchanged;
    RD NEVER decreases without new evidence."""

    def test_single_step_formula_exact(self) -> None:
        state = PlayerState(mu=0.3, phi=0.5, sigma=0.06)
        stepped = inactivity_step(state)
        assert stepped.phi == pytest.approx(math.sqrt(0.5**2 + 0.06**2), abs=1e-15)
        assert stepped.mu == 0.3
        assert stepped.sigma == 0.06

    def test_inactivity_never_reduces_phi(self) -> None:
        state = PlayerState(mu=-1.2, phi=0.8, sigma=0.03)
        for _ in range(50):
            nxt = inactivity_step(state)
            assert nxt.phi > state.phi
            state = nxt


class TestVolatilityIterationSeam:
    """Predicate seam with exact boundaries (founder round-3 pattern)."""

    def test_iteration_allowed_boundary(self) -> None:
        assert volatility_iteration_allowed(MAX_VOLATILITY_ITERATIONS - 1, MAX_VOLATILITY_ITERATIONS)
        assert not volatility_iteration_allowed(MAX_VOLATILITY_ITERATIONS, MAX_VOLATILITY_ITERATIONS)
        assert not volatility_iteration_allowed(MAX_VOLATILITY_ITERATIONS + 1, MAX_VOLATILITY_ITERATIONS)

    def test_converged_boundary_exact(self) -> None:
        tol = GLICKO2_CONVERGENCE_TOLERANCE
        assert volatility_converged(tol, tol)
        assert volatility_converged(math.nextafter(tol, 0.0), tol)
        assert not volatility_converged(math.nextafter(tol, math.inf), tol)

    def test_exhausted_iteration_raises_typed_refusal(self) -> None:
        with pytest.raises(Glicko2ConvergenceError):
            # tau tiny + absurd tolerance forces non-convergence within the cap
            new_volatility(
                phi=1.0, v=1.0, delta=10.0, sigma=0.06, tau=GLICKO2_TAU, tolerance=0.0
            )

    def test_convergence_error_is_a_fit_refusal(self) -> None:
        assert issubclass(Glicko2ConvergenceError, StageOneFitRefusal)


class TestFitSeam:
    def test_fit_refuses_non_two_player(self) -> None:
        race = Race(
            race_id="r3",
            cluster=calendar_day_assignment("tennis", date(2025, 1, 1)),
            runners=(
                RunnerRow(runner_id=1, features={"placeholder": _D0}),
                RunnerRow(runner_id=2, features={"placeholder": _D0}),
                RunnerRow(runner_id=3, features={"placeholder": _D0}),
            ),
            winner_id=1,
        )
        with pytest.raises(StageOneFitRefusal, match="two-player"):
            Glicko2Family().fit([race], _SCHEMA, horizon=_HORIZON, max_iter=10)

    def test_fit_refuses_unlabelled_race(self) -> None:
        race = _race("r4", date(2025, 1, 1), 1, 2, winner=None)
        with pytest.raises(StageOneFitRefusal, match="unlabelled"):
            Glicko2Family().fit([race], _SCHEMA, horizon=_HORIZON, max_iter=10)

    def test_predict_refuses_foreign_artefact(self) -> None:
        race = _race("r5", date(2025, 1, 2), 1, 2, winner=None)
        with pytest.raises(TypeError):
            Glicko2Family().predict(object(), race, horizon=_HORIZON)

    def test_predict_two_sided_and_coherent(self) -> None:
        fam = Glicko2Family()
        train = [_race("t1", date(2025, 1, 1), 1, 2, winner=1)]
        model = fam.fit(train, _SCHEMA, horizon=_HORIZON, max_iter=10)
        probs = fam.predict(model, _race("p1", date(2025, 1, 5), 1, 2, winner=None), horizon=_HORIZON)
        assert set(probs) == {1, 2}
        assert probs[1] + probs[2] == pytest.approx(1.0, abs=1e-15)
        assert probs[1] > 0.5  # the day-1 winner is now stronger

    def test_winner_direction(self) -> None:
        """Reversing the winner reverses which player is favoured (kills reversal mutants)."""
        fam = Glicko2Family()
        pred = _race("p1", date(2025, 1, 5), 1, 2, winner=None)
        m_a = fam.fit([_race("t1", date(2025, 1, 1), 1, 2, winner=1)], _SCHEMA, horizon=_HORIZON, max_iter=10)
        m_b = fam.fit([_race("t1", date(2025, 1, 1), 1, 2, winner=2)], _SCHEMA, horizon=_HORIZON, max_iter=10)
        assert fam.predict(m_a, pred, horizon=_HORIZON)[1] > 0.5
        assert fam.predict(m_b, pred, horizon=_HORIZON)[1] < 0.5

    def test_same_day_batch_start_of_day_states(self) -> None:
        """Two same-day matches: the second is scored from START-of-day state, so the
        fitted result equals the batch computation, not a sequential one; and row order
        within the day cannot matter."""
        fam = Glicko2Family()
        day = date(2025, 3, 1)
        races = [
            _race("a", day, 1, 2, winner=1),
            _race("b", day, 1, 3, winner=1),
        ]
        m_fwd = fam.fit(races, _SCHEMA, horizon=_HORIZON, max_iter=10)
        m_rev = fam.fit(list(reversed(races)), _SCHEMA, horizon=_HORIZON, max_iter=10)
        pred = _race("p", date(2025, 3, 2), 2, 3, winner=None)
        assert fam.predict(m_fwd, pred, horizon=_HORIZON) == fam.predict(m_rev, pred, horizon=_HORIZON)

    def test_inactivity_widens_uncertainty_between_fit_and_predict(self) -> None:
        """A player idle longer is predicted with MORE uncertainty: the favourite's
        probability against a fixed fresh opponent shrinks toward 1/2 as the gap to the
        prediction day grows (g(phi) damping), and never increases."""
        fam = Glicko2Family()
        train = [
            _race("t1", date(2025, 1, 1), 1, 2, winner=1),
            _race("t2", date(2025, 1, 2), 1, 2, winner=1),
            _race("t3", date(2025, 1, 3), 1, 2, winner=1),
        ]
        model = fam.fit(train, _SCHEMA, horizon=_HORIZON, max_iter=10)
        p_soon = fam.predict(model, _race("p1", date(2025, 1, 5), 1, 2, winner=None), horizon=_HORIZON)[1]
        p_late = fam.predict(model, _race("p2", date(2026, 1, 5), 1, 2, winner=None), horizon=_HORIZON)[1]
        assert 0.5 < p_late < p_soon

    def test_unseen_players_get_exactly_half(self) -> None:
        fam = Glicko2Family()
        model = fam.fit(
            [_race("t1", date(2025, 1, 1), 1, 2, winner=1)], _SCHEMA, horizon=_HORIZON, max_iter=10
        )
        probs = fam.predict(model, _race("p1", date(2025, 1, 5), 8, 9, winner=None), horizon=_HORIZON)
        assert probs[8] == 0.5
        assert probs[9] == 0.5
