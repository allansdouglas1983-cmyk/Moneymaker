"""SPEC-105 — DYNAMIC_GLICKO2_V1 (Stage 2G Slice 2; red tests first).

Registration: specs/programme/dp1-glicko2-registration-v1.yaml. Constants are
founder-frozen (directive §5) and NOT tunable against performance; the family takes NO
tuning parameter. Golden values come from the pinned primary source (Glickman, "Example
of the Glicko-2 system", glicko.net/glicko/glicko2.pdf) — the worked example is encoded
verbatim as the canonical correctness witness.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
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
    initial_bracket,
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


class TestVolatilityRootCondition:
    """Kill class: any mutant of the paper's f(x) converges to the WRONG root.

    The test recomputes f from the primary source independently and asserts the
    solver's returned sigma' zeroes the TRUE f. Grid spans both initialisation
    branches (Delta^2 > phi^2 + v and the k-search branch)."""

    @staticmethod
    def _paper_f(x: float, phi: float, v: float, delta: float, sigma: float, tau: float) -> float:
        ex = math.exp(x)
        first = (ex * (delta * delta - phi * phi - v - ex)) / (2.0 * (phi * phi + v + ex) ** 2)
        return first - (x - math.log(sigma * sigma)) / (tau * tau)

    @pytest.mark.parametrize(
        ("phi", "v", "delta", "sigma"),
        [
            (0.5, 1.2, 0.3, 0.06),
            (1.5, 0.8, 1.2, 0.06),
            (0.2, 0.5, 0.6, 0.1),
            (2.0, 4.0, 2.0, 0.03),
            (1.1547, 1.7785, -0.4834, 0.06),  # the paper's worked-example magnitudes
            (0.9, 1.0, 1.3, 0.2),
            (0.5, 0.4, 0.9, 0.3),  # exercises the Delta^2 > phi^2 + v branch
            (0.3, 0.2, 1.1, 0.05),  # also the B = log(...) branch
        ],
    )
    def test_returned_volatility_zeroes_the_true_f(
        self, phi: float, v: float, delta: float, sigma: float
    ) -> None:
        sigma_prime = new_volatility(
            phi=phi, v=v, delta=delta, sigma=sigma, tau=GLICKO2_TAU,
            tolerance=GLICKO2_CONVERGENCE_TOLERANCE,
        )
        x_star = 2.0 * math.log(sigma_prime)
        assert abs(self._paper_f(x_star, phi, v, delta, sigma, GLICKO2_TAU)) < 1e-3

    def test_iteration_cap_constant_pinned(self) -> None:
        assert MAX_VOLATILITY_ITERATIONS == 100


class TestExactPredictionReconstruction:
    """Kill class: inactivity step-count off-by-ones and the s-formula in predict.

    The family's prediction is reconstructed manually from the PUBLIC primitives with
    the registered rule (a player last active on day L, predicted on day D, takes
    exactly D - L - 1 inactivity steps), then compared EXACTLY — any deviation in the
    step count, the delta, or the s combination changes the float and fails."""

    @pytest.mark.parametrize("gap_days", [1, 2, 3, 11, 40])
    def test_predict_equals_manual_reconstruction(self, gap_days: int) -> None:
        from sport_tennis.dp1_distribution import central_win_probability

        fam = Glicko2Family()
        d1, d2 = date(2025, 2, 1), date(2025, 2, 2)
        train = [
            _race("t1", d1, 1, 2, winner=1),
            _race("t2", d2, 1, 2, winner=1),
        ]
        model = fam.fit(train, _SCHEMA, horizon=_HORIZON, max_iter=10)
        pred_day = d2 + timedelta(days=gap_days)
        got = fam.predict(model, _race("p", pred_day, 1, 2, winner=None), horizon=_HORIZON)

        # manual replay from public primitives
        s1 = rate_player(INITIAL_PLAYER_STATE, [(INITIAL_PLAYER_STATE, 1.0)])
        s2_opp = rate_player(INITIAL_PLAYER_STATE, [(INITIAL_PLAYER_STATE, 0.0)])
        sa = rate_player(s1, [(s2_opp, 1.0)])
        sb = rate_player(s2_opp, [(s1, 0.0)])
        for _ in range(gap_days - 1):  # the registered D - L - 1 rule
            sa = inactivity_step(sa)
            sb = inactivity_step(sb)
        delta = sa.mu - sb.mu
        s = math.sqrt(sa.phi * sa.phi + sb.phi * sb.phi)
        expected = central_win_probability(delta, s)
        assert got[1] == expected  # exact float equality
        assert got[2] == 1.0 - expected

    def test_winner_identity_not_used_for_score(self) -> None:
        """Kill class: `winner_id is a` — non-interned equal ints must still score."""
        fam = Glicko2Family()
        big_a, big_b = 100000, 100001
        race = Race(
            race_id="big",
            cluster=calendar_day_assignment("tennis", date(2025, 2, 1)),
            runners=(
                RunnerRow(runner_id=big_a, features={"placeholder": _D0}),
                RunnerRow(runner_id=big_b, features={"placeholder": _D0}),
            ),
            winner_id=int("100000"),  # equal to big_a, distinct object
        )
        model = fam.fit([race], _SCHEMA, horizon=_HORIZON, max_iter=10)
        probs = fam.predict(
            model, _race("p", date(2025, 2, 5), big_a, big_b, None), horizon=_HORIZON
        )
        assert probs[big_a] > 0.5  # the winner must have been credited


class TestIndependentRatePlayerWitness:
    """Kill class: any deviation in rate_player's composition of steps 3-8 (including
    what it PASSES to the volatility solver, e.g. Delta = v * sum) diverges from a
    test-side reimplementation of the primary source using bisection for step 5."""

    @staticmethod
    def _reference(state: PlayerState, results: list[tuple[PlayerState, float]]) -> PlayerState:
        def g(phi: float) -> float:
            return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))

        def e_fn(mu: float, mu_j: float, phi_j: float) -> float:
            return 1.0 / (1.0 + math.exp(-g(phi_j) * (mu - mu_j)))

        v = 1.0 / math.fsum(
            g(o.phi) ** 2 * e_fn(state.mu, o.mu, o.phi) * (1.0 - e_fn(state.mu, o.mu, o.phi))
            for o, _s in results
        )
        imp = math.fsum(g(o.phi) * (sc - e_fn(state.mu, o.mu, o.phi)) for o, sc in results)
        delta = v * imp
        a = math.log(state.sigma**2)

        def f(x: float) -> float:
            ex = math.exp(x)
            return (ex * (delta**2 - state.phi**2 - v - ex)) / (
                2.0 * (state.phi**2 + v + ex) ** 2
            ) - (x - a) / (GLICKO2_TAU**2)

        lo, hi = a - 40.0, a + 40.0
        if f(lo) * f(hi) > 0:  # widen until bracketed (f -> +inf at -inf, -inf at +inf)
            raise AssertionError("reference bracket failed")
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if f(lo) * f(mid) <= 0:
                hi = mid
            else:
                lo = mid
        sigma_prime = math.exp((lo + hi) / 4.0)
        phi_star = math.sqrt(state.phi**2 + sigma_prime**2)
        phi_prime = 1.0 / math.sqrt(1.0 / phi_star**2 + 1.0 / v)
        mu_prime = state.mu + phi_prime**2 * imp
        return PlayerState(mu=mu_prime, phi=phi_prime, sigma=sigma_prime)

    @pytest.mark.parametrize(
        "case",
        [
            # calm case
            [(PlayerState(mu=0.2, phi=0.8, sigma=0.06), 1.0)],
            # the paper's shape
            [
                (PlayerState(mu=-0.5756, phi=0.1727, sigma=0.06), 1.0),
                (PlayerState(mu=0.2878, phi=0.5756, sigma=0.06), 0.0),
                (PlayerState(mu=1.1513, phi=1.7269, sigma=0.06), 0.0),
            ],
            # HIGH-SURPRISE: strong opponent set, all lost, high own phi — the
            # volatility must move materially; Delta mutants shift sigma' visibly
            [
                (PlayerState(mu=2.5, phi=0.2, sigma=0.06), 1.0),
                (PlayerState(mu=2.6, phi=0.2, sigma=0.06), 1.0),
                (PlayerState(mu=2.4, phi=0.2, sigma=0.06), 1.0),
                (PlayerState(mu=2.7, phi=0.2, sigma=0.06), 1.0),
            ],
        ],
    )
    def test_rate_player_matches_reference(
        self, case: list[tuple[PlayerState, float]]
    ) -> None:
        state = PlayerState(mu=0.0, phi=1.1513, sigma=0.06)
        got = rate_player(state, case)
        ref = self._reference(state, case)
        assert got.mu == pytest.approx(ref.mu, abs=1e-9)
        assert got.phi == pytest.approx(ref.phi, abs=1e-9)
        assert got.sigma == pytest.approx(ref.sigma, abs=1e-7)


class TestStructuralContracts:
    def test_player_state_is_frozen(self) -> None:
        import dataclasses

        state = PlayerState(mu=0.0, phi=1.0, sigma=0.06)
        with pytest.raises(dataclasses.FrozenInstanceError):
            state.mu = 1.0  # type: ignore[misc]

    def test_fitted_artefact_is_frozen(self) -> None:
        import dataclasses

        fam = Glicko2Family()
        model = fam.fit(
            [_race("t", date(2025, 1, 1), 1, 2, winner=1)], _SCHEMA, horizon=_HORIZON, max_iter=10
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            model.states = {}  # type: ignore[misc]

    def test_seam_parameters_are_keyword_only(self) -> None:
        """The `*` markers are contractual: horizon can never be passed positionally."""
        import inspect

        fit_params = inspect.signature(Glicko2Family.fit).parameters
        assert fit_params["horizon"].kind is inspect.Parameter.KEYWORD_ONLY
        assert fit_params["max_iter"].kind is inspect.Parameter.KEYWORD_ONLY
        predict_params = inspect.signature(Glicko2Family.predict).parameters
        assert predict_params["horizon"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_predict_refuses_three_active_with_the_typed_message(self) -> None:
        fam = Glicko2Family()
        model = fam.fit(
            [_race("t", date(2025, 1, 1), 1, 2, winner=1)], _SCHEMA, horizon=_HORIZON, max_iter=10
        )
        race = Race(
            race_id="r3p",
            cluster=calendar_day_assignment("tennis", date(2025, 1, 2)),
            runners=(
                RunnerRow(runner_id=1, features={"placeholder": _D0}),
                RunnerRow(runner_id=2, features={"placeholder": _D0}),
                RunnerRow(runner_id=3, features={"placeholder": _D0}),
            ),
            winner_id=None,
        )
        with pytest.raises(ValueError, match="two-player"):
            fam.predict(model, race, horizon=_HORIZON)


class TestVolatilityGoldenGrid:
    """Finite-execution pins (founder §2E): exact float reprs of new_volatility over the
    extreme grid (tiny/large sigma, phi extremes, surprising and near-expected outcomes,
    weak/strong information, both bracket branches, near-boundary inputs). A convergence-
    path mutant that shifts the returned value by ONE ULP anywhere here dies. Values were
    generated from the pre-refactor implementation, so this grid also proves the
    initial_bracket seam extraction is bit-identical."""

    GRID = [
        (0.05, 0.1, 0.02, 0.01, 0.009999393289421026),
        (0.05, 0.1, 1.5, 0.01, 0.010012790291663744),
        (2.0148, 50.0, 0.1, 0.06, 0.05999975033975754),
        (0.1727, 1.7785, -0.4834, 0.06, 0.05999351169008403),
        (1.0, 0.5, 2.5, 0.06, 0.060028375534275126),
        (0.5, 0.4, 0.9, 0.3, 0.3002156262253414),
        (3.0, 10.0, 0.5, 1.0, 0.996936714724098),
        (0.02, 0.05, 0.0, 0.06, 0.05975243473796183),
        (1.5, 2.0, -2.1, 0.8, 0.7993600303613275),
        (0.8, 0.6, 1.1832159566199232, 0.06, 0.06000136531614448),
        (5.0, 30.0, 4.0, 19.0, 18.0511825754742),
        (0.3, 0.2, 1.05, 0.05, 0.050074234028394726),
    ]

    @pytest.mark.parametrize(("phi", "v", "delta", "sigma", "expected"), GRID)
    def test_exact_bitwise_pin(
        self, phi: float, v: float, delta: float, sigma: float, expected: float
    ) -> None:
        got = new_volatility(
            phi=phi, v=v, delta=delta, sigma=sigma,
            tau=GLICKO2_TAU, tolerance=GLICKO2_CONVERGENCE_TOLERANCE,
        )
        assert got == expected  # exact — one ULP is behavioural (founder ruling)


class TestInitialBracketSeam:
    """Pure-seam contract for the paper's step-5 bracket initialisation (founder §2
    option A/B/C resolution).

    Registered pure domain (module docstring): finite inputs, phi > 0, v > 0,
    sigma > 0, tau > 0 — the mathematical domain of the paper's algorithm; callers
    (rate_player) construct values inside it by construction. The public model API's
    accepted domain is unchanged by the seam."""

    def test_b_branch_exact(self) -> None:
        # Delta^2 > phi^2 + v: B = ln(Delta^2 - phi^2 - v)
        a, b = initial_bracket(phi=0.5, v=0.4, delta=0.9, sigma=0.3, tau=GLICKO2_TAU)
        assert a == math.log(0.3 * 0.3)
        assert b == math.log(0.9 * 0.9 - 0.5 * 0.5 - 0.4)

    def test_k_branch_exact(self) -> None:
        # Delta^2 <= phi^2 + v: k-search; the loop body is unreachable (see below), so
        # B = a - tau exactly.
        a, b = initial_bracket(phi=0.5, v=1.2, delta=0.3, sigma=0.06, tau=GLICKO2_TAU)
        assert a == math.log(0.06 * 0.06)
        assert b == a - GLICKO2_TAU

    def test_exact_equality_takes_the_k_branch(self) -> None:
        """The paper's case split is STRICT Delta^2 > phi^2 + v; equality must use the
        k-branch (the B-branch would be ln(0)). Paper-fidelity pin, not a mutant hack."""
        phi, v = 0.6, 0.28
        delta = math.sqrt(phi * phi + v)
        assert delta * delta <= phi * phi + v  # constructed at/below exact equality
        a, b = initial_bracket(phi=phi, v=v, delta=delta, sigma=0.06, tau=GLICKO2_TAU)
        assert b == a - GLICKO2_TAU  # k-branch, never ln(~0)

    def test_k_search_body_is_structurally_unreachable(self) -> None:
        """Analytic invariant (packet Class-E/B proof): on the k-branch D = Delta^2 -
        phi^2 - v <= 0, so the first term of f at x = a - k*tau is bounded in
        (-1/2, 1/2] in magnitude, while -(x - a)/tau^2 contributes +k/tau = +2k.
        Hence f(a - k*tau) > 3/2 > 0 for every k >= 1 at tau = 0.5: the while
        condition is False at k = 1 for EVERY input in the registered domain.
        Verified numerically over a wide domain grid here; the algebraic bound is in
        the survivor packet."""
        for phi in (0.01, 0.1727, 0.5, 2.0148, 5.0, 50.0):
            for v in (0.01, 0.5, 1.7785, 50.0, 1000.0):
                for frac in (0.0, 0.3, 0.9, 1.0):
                    delta = math.sqrt((phi * phi + v) * frac)
                    for sigma in (1e-6, 0.06, 1.0, 19.0, 100.0):
                        a = math.log(sigma * sigma)
                        x = a - GLICKO2_TAU
                        ex = math.exp(x)
                        first = (ex * (delta * delta - phi * phi - v - ex)) / (
                            2.0 * (phi * phi + v + ex) ** 2
                        )
                        f_val = first - (x - a) / (GLICKO2_TAU * GLICKO2_TAU)
                        assert f_val > 0.0, (phi, v, delta, sigma)
