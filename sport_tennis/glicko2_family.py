"""DP1 — DYNAMIC_GLICKO2_V1, one governed implementation behind the StageOneFamily seam
(SPEC-105; registration: specs/programme/dp1-glicko2-registration-v1.yaml; ADR 0019).

Canonical Glicko-2 exactly as the pinned primary source (Glickman, "Example of the
Glicko-2 system"). Constants are founder-frozen (directive §5) and NOT tunable against
model performance — the family therefore takes NO constructor parameter. Scale
conversion mu = (r-1500)/173.7178, phi = RD/173.7178. Rating period = one UTC calendar
day; matches on a date are expected-scored against START-of-date states and updated as
ONE batch (a day's outcome can never inform a same-day prediction; results are
invariant to row permutation within a date). For every elapsed empty period a player's
phi inflates by the paper's no-game rule phi <- sqrt(phi^2 + sigma^2) — uncertainty
NEVER shrinks without new evidence. ATP/WTA separation is upstream (separate identity
namespaces feed separate fits); this module never sees a name, an odds value, a
surface, or a bookmaker field — only Race objects with integer runner ids.

Prediction through the seam is the SPEC-106 central probability: the frozen 20-node
Gauss-Hermite posterior mean of sigmoid(delta + s*sqrt(2)*x) with delta = mu_a - mu_b
and s^2 = phi_a^2 + phi_b^2 (phis first inflated for elapsed inactive periods).
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping, Sequence

from sport_core.clustering import ChronologyKey

from l4_pricing.stage_one import StageOneFitRefusal

if TYPE_CHECKING:
    from l4_pricing.horizon import HorizonLabel
    from l4_pricing.races import FeatureSchema, Race

__all__ = [
    "GLICKO2_CONVERGENCE_TOLERANCE",
    "GLICKO2_INITIAL_RATING",
    "GLICKO2_INITIAL_RD",
    "GLICKO2_INITIAL_VOLATILITY",
    "GLICKO2_SCALE",
    "GLICKO2_TAU",
    "INITIAL_PLAYER_STATE",
    "MAX_VOLATILITY_ITERATIONS",
    "Glicko2ConvergenceError",
    "Glicko2Family",
    "PlayerState",
    "brackets_root_or_touches_zero",
    "inactivity_step",
    "initial_bracket",
    "new_volatility",
    "rate_player",
    "volatility_converged",
    "volatility_iteration_allowed",
]

# Founder-frozen configuration (directive §5) — never tuned against performance.
GLICKO2_INITIAL_RATING = 1500.0
GLICKO2_INITIAL_RD = 350.0
GLICKO2_INITIAL_VOLATILITY = 0.06
GLICKO2_TAU = 0.5
GLICKO2_CONVERGENCE_TOLERANCE = 1e-6
GLICKO2_SCALE = 173.7178

# Defensive cap on the Illinois iteration. The paper's algorithm converges in a handful
# of steps; exhausting the cap is a typed refusal (never a silent fallback value).
MAX_VOLATILITY_ITERATIONS = 100


class Glicko2ConvergenceError(StageOneFitRefusal):
    """The volatility iteration failed to converge — a typed fit refusal."""


@dataclass(frozen=True)
class PlayerState:
    """One player's Glicko-2 state on the internal scale."""

    mu: float
    phi: float
    sigma: float

    @property
    def rating(self) -> float:
        return GLICKO2_SCALE * self.mu + GLICKO2_INITIAL_RATING

    @property
    def rating_deviation(self) -> float:
        return GLICKO2_SCALE * self.phi


INITIAL_PLAYER_STATE = PlayerState(
    mu=0.0, phi=GLICKO2_INITIAL_RD / GLICKO2_SCALE, sigma=GLICKO2_INITIAL_VOLATILITY
)


def volatility_iteration_allowed(iterations: int, maximum: int) -> bool:
    """Predicate seam: may the Illinois iteration take another step?"""
    return iterations < maximum


def volatility_converged(step: float, tolerance: float) -> bool:
    """Predicate seam: has |b - a| reached the frozen tolerance?"""
    return step <= tolerance


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _expected(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def brackets_root_or_touches_zero(f_c: float, f_b: float) -> bool:
    """Illinois bracket-update sign test as an EXACT pure predicate (founder §4):
    True iff f_c and f_b have opposite signs OR either is exactly zero — i.e. the
    interval [c, b] brackets a root or one endpoint sits on it. Uses the product form
    so it never divides (f_b == 0 is a legitimate zero-touch, not an error) and the
    `<= 0` boundary counts a zero touch as bracketing."""
    return f_c * f_b <= 0.0


def initial_bracket(
    *, phi: float, v: float, delta: float, sigma: float, tau: float
) -> tuple[float, float]:
    """The paper's step-5 bracket initialisation as a PURE seam.

    Registered pure domain: finite inputs with phi > 0, v > 0, sigma > 0, and the
    registered ``tau == GLICKO2_TAU`` (0.5). The case split is STRICT
    ``Delta^2 > phi^2 + v``; exact equality takes the D<=0 branch (the other branch
    would be ln(0)).

    Founder §3 (2026-07-21): on the D = Delta^2 - phi^2 - v <= 0 branch the paper's
    k-search terminates immediately at k = 1 for the registered tau = 0.5 — analytic:
    the first term of the paper's f at x = a - tau has magnitude < 1/2 while
    -(x - a)/tau^2 contributes +1/tau = +2, so f(a - tau) > 3/2 > 0, so the search
    never advances past k = 1 and B = a - tau. The dead sign-only f and the
    never-executing search loop are therefore REMOVED and the analytically-established
    bracket is returned directly. This is valid ONLY at tau = 0.5; a future tau is a
    new registered version (hence the guard). Every golden volatility/rating/RD/
    probability/uncertainty/state/replay value is preserved byte-identically.
    """
    if tau != GLICKO2_TAU:
        raise ValueError(
            f"initial_bracket is registered for tau == {GLICKO2_TAU} only (the D<=0 "
            f"direct return is analytically established at that tau); got tau={tau!r} — "
            "a different tau requires a new registered version"
        )
    a = math.log(sigma * sigma)
    delta_sq = delta * delta
    phi_sq = phi * phi
    if delta_sq > phi_sq + v:
        return a, math.log(delta_sq - phi_sq - v)
    # D <= 0: k-search terminates at k = 1 for tau = 0.5 (see docstring).
    return a, a - tau


def new_volatility(
    *,
    phi: float,
    v: float,
    delta: float,
    sigma: float,
    tau: float,
    tolerance: float,
    maximum: int = MAX_VOLATILITY_ITERATIONS,
) -> float:
    """Step 5 of the paper: sigma' via the Illinois-algorithm iteration on f(x).

    ``maximum`` defaults to the registered MAX_VOLATILITY_ITERATIONS and is injectable
    ONLY so the iteration-budget seam (start=0, +1, cap boundary) is directly testable
    with synthetic small budgets (founder §5); rate_player always uses the default, so
    production output is unchanged.
    """
    a = math.log(sigma * sigma)
    delta_sq = delta * delta
    phi_sq = phi * phi

    def f(x: float) -> float:
        ex = math.exp(x)
        num = ex * (delta_sq - phi_sq - v - ex)
        den = 2.0 * (phi_sq + v + ex) ** 2
        return num / den - (x - a) / (tau * tau)

    big_a, big_b = initial_bracket(phi=phi, v=v, delta=delta, sigma=sigma, tau=tau)

    f_a = f(big_a)
    f_b = f(big_b)
    iterations = 0
    while not volatility_converged(abs(big_b - big_a), tolerance):
        if not volatility_iteration_allowed(iterations, maximum):
            raise Glicko2ConvergenceError(
                f"volatility iteration exhausted {maximum} steps "
                f"(|b-a|={abs(big_b - big_a)!r}, tolerance={tolerance!r}) — refusing, "
                "never substituting an unconverged value"
            )
        big_c = big_a + (big_a - big_b) * f_a / (f_b - f_a)
        f_c = f(big_c)
        if brackets_root_or_touches_zero(f_c, f_b):
            big_a, f_a = big_b, f_b
        else:
            f_a = f_a / 2.0
        big_b, f_b = big_c, f_c
        iterations += 1
    return math.exp(big_a / 2.0)


def inactivity_step(state: PlayerState) -> PlayerState:
    """The paper's no-game rule for one empty rating period: phi inflates, mu and sigma
    are unchanged. Uncertainty NEVER decreases without new evidence."""
    return PlayerState(
        mu=state.mu,
        phi=math.sqrt(state.phi * state.phi + state.sigma * state.sigma),
        sigma=state.sigma,
    )


def rate_player(
    state: PlayerState, results: Sequence[tuple[PlayerState, float]]
) -> PlayerState:
    """Steps 3-8 for one rating period with games: opponents' START-of-period states and
    scores s_j in {0, 1} (1 = this player won)."""
    if not results:
        raise ValueError("rate_player needs at least one result; empty periods use inactivity_step")
    v_inv_terms = []
    delta_terms = []
    for opponent, score in results:
        if score not in (0.0, 1.0):
            raise ValueError(f"score must be 0.0 or 1.0, got {score!r}")
        g_j = _g(opponent.phi)
        e_j = _expected(state.mu, opponent.mu, opponent.phi)
        v_inv_terms.append(g_j * g_j * e_j * (1.0 - e_j))
        delta_terms.append(g_j * (score - e_j))
    v = 1.0 / math.fsum(v_inv_terms)
    improvement_sum = math.fsum(delta_terms)
    delta = v * improvement_sum
    sigma_prime = new_volatility(
        phi=state.phi,
        v=v,
        delta=delta,
        sigma=state.sigma,
        tau=GLICKO2_TAU,
        tolerance=GLICKO2_CONVERGENCE_TOLERANCE,
    )
    phi_star = math.sqrt(state.phi * state.phi + sigma_prime * sigma_prime)
    phi_prime = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_prime = state.mu + phi_prime * phi_prime * improvement_sum
    return PlayerState(mu=mu_prime, phi=phi_prime, sigma=sigma_prime)


@dataclass(frozen=True)
class _FittedGlicko2:
    """Opaque fitted artefact: per-runner states + the UTC-day ordinal each state is
    current through. Carries NO training provenance — that is the orchestrator's
    bookkeeping (stage_one seam contract)."""

    states: Mapping[int, PlayerState]
    state_day: Mapping[int, int]
    match_counts: Mapping[int, int]


def _advance_to(state: PlayerState, current_through: int, target_day: int) -> PlayerState:
    """Apply the no-game rule once per empty UTC-day period strictly between the day the
    state is current through and the target day."""
    for _ in range(max(0, target_day - current_through - 1)):
        state = inactivity_step(state)
    return state


class Glicko2Family:
    """StageOneFamily-conformant DYNAMIC_GLICKO2_V1 (duck-typed against the seam).

    No constructor parameter: every constant is founder-frozen (directive §5).
    """

    def __init__(self) -> None:
        """Deliberately parameterless — the frozen constants are not tunable."""

    @property
    def family_id(self) -> str:
        return "dynamic-glicko2-v1"

    def fit(
        self,
        races: "Sequence[Race]",
        _schema: "FeatureSchema",
        *,
        horizon: "HorizonLabel",  # noqa: ARG002  # pylint: disable=unused-argument
        max_iter: int,  # noqa: ARG002  # pylint: disable=unused-argument
    ) -> _FittedGlicko2:
        states: dict[int, PlayerState] = {}
        state_day: dict[int, int] = {}
        match_counts: dict[int, int] = defaultdict(int)
        by_day: defaultdict[ChronologyKey, list["Race"]] = defaultdict(list)
        for race in races:
            by_day[race.cluster.chronology].append(race)
        for day in sorted(by_day):
            ordinal = day.ordinal
            # START-of-day states: prior state advanced through day ordinal-1.
            start: dict[int, PlayerState] = {}
            day_results: defaultdict[int, list[tuple[int, float]]] = defaultdict(list)
            for race in sorted(by_day[day], key=lambda r: r.race_id):
                active = [r.runner_id for r in race.runners if not r.non_runner]
                if len(active) != 2:
                    raise StageOneFitRefusal(
                        f"Glicko-2 is a two-player family; race {race.race_id!r} has "
                        f"{len(active)} active"
                    )
                if race.winner_id is None:
                    raise StageOneFitRefusal(
                        f"unlabelled race {race.race_id!r} in a Glicko-2 training window — "
                        "the label policy excludes it upstream; reaching here is a defect, "
                        "not a default"
                    )
                a, b = sorted(active)
                for rid in (a, b):
                    if rid not in start:
                        start[rid] = _advance_to(
                            states.get(rid, INITIAL_PLAYER_STATE),
                            state_day.get(rid, ordinal),
                            ordinal,
                        )
                score_a = 1.0 if race.winner_id == a else 0.0
                day_results[a].append((b, score_a))
                day_results[b].append((a, 1.0 - score_a))
            for rid in sorted(day_results):
                results = [
                    (start[opp], score) for opp, score in sorted(day_results[rid])
                ]
                states[rid] = rate_player(start[rid], results)
                state_day[rid] = ordinal
                match_counts[rid] += len(results)
        return _FittedGlicko2(
            states=dict(states), state_day=dict(state_day), match_counts=dict(match_counts)
        )

    def predict(
        self, model: object, race: "Race", *, horizon: "HorizonLabel"  # noqa: ARG002  # pylint: disable=unused-argument
    ) -> Mapping[int, float]:
        if not isinstance(model, _FittedGlicko2):
            raise TypeError(
                f"Glicko2Family.predict needs its own fitted artefact, got {type(model).__name__}"
            )
        active = [r.runner_id for r in race.runners if not r.non_runner]
        if len(active) != 2:
            raise ValueError(
                f"Glicko-2 predicts two-player choice sets only; got {len(active)}"
            )
        a, b = sorted(active)
        day = race.cluster.chronology.ordinal
        state_a = _advance_to(
            model.states.get(a, INITIAL_PLAYER_STATE), model.state_day.get(a, day), day
        )
        state_b = _advance_to(
            model.states.get(b, INITIAL_PLAYER_STATE), model.state_day.get(b, day), day
        )
        # SPEC-106 central probability (frozen quadrature); imported lazily to keep the
        # family module import-light for the seam.
        from sport_tennis.dp1_distribution import central_win_probability

        delta = state_a.mu - state_b.mu
        s = math.sqrt(state_a.phi * state_a.phi + state_b.phi * state_b.phi)
        p_a = central_win_probability(delta, s)
        return {a: p_a, b: 1.0 - p_a}
