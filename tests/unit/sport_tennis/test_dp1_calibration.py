"""SPEC-107 — AFFINE_LOGIT_CALIBRATION_FOR_DP1 (Stage 2G Slice 3; red tests first).

Registration: specs/programme/dp1-glicko2-registration-v1.yaml `calibration` block.
The ONLY registered form: z = logit(p_raw); z_cal = intercept + z/temperature;
p_cal = sigmoid(z_cal). Fitted ONLY on leakage-safe out-of-fold DP1 predictions
(SPEC-031 refusal at consumption, reusing the crossfit contamination check);
ATP/WTA separate; raw and calibrated both retained; choice-set coherence preserved
by calibrating the canonical (lower runner id) orientation and complementing.

"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest

from l4_pricing.crossfit import CrossFitViolation, OOFFundamental, StageOneProvenance
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow
from sport_core.clustering import ChronologyKey, calendar_day_assignment
from sport_tennis.dp1_calibration import (
    AFFINE_CALIBRATION_VERSION,
    DET_EPSILON,
    MAX_NEWTON_ITERATIONS,
    STEP_EPSILON,
    AffineLogitCalibration,
    CalibrationFitError,
    fit_affine_logit_calibration,
    hessian_is_singular,
    newton_iteration_allowed,
    parameters_finite,
    slope_is_valid,
    step_has_converged,
)

pytestmark = pytest.mark.spec("SPEC-107")

_HORIZON = HorizonLabel("pre-off-tennis")
_D0 = Decimal("0")


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _race(race_id: str, day: date, a: int, b: int, winner: int) -> Race:
    return Race(
        race_id=race_id,
        cluster=calendar_day_assignment("tennis", day),
        runners=(
            RunnerRow(runner_id=a, features={"placeholder": _D0}),
            RunnerRow(runner_id=b, features={"placeholder": _D0}),
        ),
        winner_id=winner,
    )


def _oof_row(race: Race, runner_id: int, p: float, *, trained_through: int) -> OOFFundamental:
    return OOFFundamental(
        race_id=race.race_id,
        runner_id=runner_id,
        p_fundamental=p,
        provenance=StageOneProvenance(
            trained_through=ChronologyKey(ordinal=trained_through),
            training_race_ids=frozenset(),
            training_race_ids_digest="0" * 64,
            horizon=_HORIZON,
        ),
    )


def _synthetic_corpus(
    intercept: float, temperature: float, n: int = 4000
) -> tuple[list[Race], list[OOFFundamental]]:
    """Deterministic corpus whose TRUE win law is sigmoid(intercept + z/temperature)
    of the raw prediction's logit — the fit must recover (intercept, temperature).
    Outcomes are assigned by deterministic quantile striping, not randomness."""
    races: list[Race] = []
    rows: list[OOFFundamental] = []
    day0 = date(2024, 1, 1)
    counter = 0
    for i in range(n):
        z = -2.0 + 4.0 * i / (n - 1)
        p_raw = _sigmoid(z)
        p_true = _sigmoid(intercept + z / temperature)
        # deterministic outcome striping: winner 'a' on a fraction ~ p_true of slots
        counter += 1
        frac = (i * 0.6180339887498949) % 1.0  # low-discrepancy, deterministic
        a_wins = frac < p_true
        day = day0
        race = _race(f"s{i}", day, 1, 2, winner=1 if a_wins else 2)
        races.append(race)
        rows.append(_oof_row(race, 1, p_raw, trained_through=day.toordinal() - 1))
        rows.append(_oof_row(race, 2, 1.0 - p_raw, trained_through=day.toordinal() - 1))
    return races, rows


class TestAffineLogitCalibrationObject:
    def test_version_pinned(self) -> None:
        assert AFFINE_CALIBRATION_VERSION == "affine-logit-dp1-v1"

    def test_identity_parameters_reproduce_raw_exactly(self) -> None:
        cal = AffineLogitCalibration(intercept=0.0, temperature=1.0, tour="atp", n_rows=10)
        for p in (1e-9, 0.2, 0.5, 0.731, 1.0 - 1e-9):
            assert cal.apply(p) == p  # exact, not approximate

    def test_output_varies_with_intercept_and_temperature(self) -> None:
        base = AffineLogitCalibration(intercept=0.0, temperature=1.2, tour="atp", n_rows=10)
        shifted = AffineLogitCalibration(intercept=0.3, temperature=1.2, tour="atp", n_rows=10)
        heated = AffineLogitCalibration(intercept=0.0, temperature=1.5, tour="atp", n_rows=10)
        p = 0.7
        assert base.apply(p) != shifted.apply(p)
        assert base.apply(p) != heated.apply(p)

    def test_temperature_shrinks_toward_half(self) -> None:
        cal = AffineLogitCalibration(intercept=0.0, temperature=2.0, tour="atp", n_rows=10)
        assert 0.5 < cal.apply(0.8) < 0.8
        assert 0.2 < cal.apply(0.2) < 0.5  # symmetric side moves up toward 1/2

    def test_pair_application_is_coherent(self) -> None:
        cal = AffineLogitCalibration(intercept=0.15, temperature=1.3, tour="wta", n_rows=10)
        p_a, p_b = cal.apply_pair(0.65)
        assert p_a + p_b == 1.0  # exact complement
        assert p_a == cal.apply(0.65)

    def test_invalid_parameters_refused(self) -> None:
        with pytest.raises(CalibrationFitError):
            AffineLogitCalibration(intercept=0.0, temperature=0.0, tour="atp", n_rows=1)
        with pytest.raises(CalibrationFitError):
            AffineLogitCalibration(intercept=0.0, temperature=-1.0, tour="atp", n_rows=1)
        with pytest.raises(CalibrationFitError):
            AffineLogitCalibration(intercept=math.nan, temperature=1.0, tour="atp", n_rows=1)
        with pytest.raises(CalibrationFitError):
            AffineLogitCalibration(intercept=0.0, temperature=1.0, tour="", n_rows=1)

    def test_frozen(self) -> None:
        import dataclasses

        cal = AffineLogitCalibration(intercept=0.0, temperature=1.0, tour="atp", n_rows=1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            cal.temperature = 2.0  # type: ignore[misc]


class TestFit:
    def test_recovers_known_miscalibration(self) -> None:
        races, rows = _synthetic_corpus(intercept=0.4, temperature=1.5)
        cal = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        assert cal.tour == "atp"
        assert cal.intercept == pytest.approx(0.4, abs=0.1)
        assert cal.temperature == pytest.approx(1.5, abs=0.15)
        assert cal.n_rows == len(races)

    def test_deterministic(self) -> None:
        races, rows = _synthetic_corpus(intercept=0.2, temperature=1.2, n=1000)
        c1 = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        c2 = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        assert (c1.intercept, c1.temperature) == (c2.intercept, c2.temperature)

    def test_contaminated_row_refused_not_downweighted(self) -> None:
        races, rows = _synthetic_corpus(intercept=0.0, temperature=1.0, n=50)
        race = races[0]
        bad = _oof_row(race, 1, 0.6, trained_through=race.cluster.chronology.ordinal)
        with pytest.raises(CrossFitViolation):
            fit_affine_logit_calibration(
                races, [bad] + rows[1:], horizon=_HORIZON, tour="atp"
            )

    def test_horizon_mismatch_refused(self) -> None:
        races, rows = _synthetic_corpus(intercept=0.0, temperature=1.0, n=50)
        with pytest.raises(CrossFitViolation):
            fit_affine_logit_calibration(
                races, rows, horizon=HorizonLabel("other-horizon"), tour="atp"
            )

    def test_empty_corpus_refused(self) -> None:
        with pytest.raises(CalibrationFitError):
            fit_affine_logit_calibration([], [], horizon=_HORIZON, tour="atp")

    def test_anti_informative_predictions_refused(self) -> None:
        """A negative fitted slope would mean temperature < 0 — the registered form
        cannot represent it; the fit must refuse, never emit a nonsense temperature."""
        races, rows = _synthetic_corpus(intercept=0.0, temperature=1.0, n=2000)
        flipped_races = [
            _race(r.race_id, date.fromordinal(r.cluster.chronology.ordinal), 1, 2,
                  winner=2 if r.winner_id == 1 else 1)
            for r in races
        ]
        with pytest.raises(CalibrationFitError):
            fit_affine_logit_calibration(flipped_races, rows, horizon=_HORIZON, tour="atp")

    def test_raw_probabilities_unchanged_by_fitting(self) -> None:
        races, rows = _synthetic_corpus(intercept=0.3, temperature=1.4, n=500)
        before = [(r.race_id, r.runner_id, r.p_fundamental) for r in rows]
        fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        assert [(r.race_id, r.runner_id, r.p_fundamental) for r in rows] == before


class TestGovernedClampAmendment:
    """DP1-CALIBRATION-CLAMP-AMENDMENT-V1 pins (founder §2/§4 kill classes: allow
    exact zero or one; clamp only one side; substitute raw for calibrated)."""

    def test_saturation_clamps_to_exact_bounds_both_sides(self) -> None:
        sharp = AffineLogitCalibration(intercept=0.0, temperature=0.01, tour="atp", n_rows=1)
        assert sharp.apply(0.9) == 1.0 - 1e-12  # upper clamp, exactly
        assert sharp.apply(0.1) == 1e-12  # lower clamp, exactly
        shifted = AffineLogitCalibration(intercept=50.0, temperature=1.0, tour="atp", n_rows=1)
        assert shifted.apply(0.5) == 1.0 - 1e-12
        shifted_dn = AffineLogitCalibration(intercept=-50.0, temperature=1.0, tour="atp", n_rows=1)
        assert shifted_dn.apply(0.5) == 1e-12

    def test_never_exactly_zero_or_one(self) -> None:
        for intercept in (-800.0, 800.0):
            cal = AffineLogitCalibration(intercept=intercept, temperature=0.05, tour="wta", n_rows=1)
            for p in (1e-9, 0.5, 1.0 - 1e-9):
                out = cal.apply(p)
                assert 0.0 < out < 1.0
                assert math.isfinite(out)

    def test_calibrated_never_silently_raw(self) -> None:
        """Non-identity parameters must actually transform (kills raw-substitution)."""
        cal = AffineLogitCalibration(intercept=0.2, temperature=1.3, tour="atp", n_rows=1)
        for p in (0.2, 0.5, 0.73):
            assert cal.apply(p) != p

    def test_temperature_direction_not_reversed(self) -> None:
        """z/T vs z*T are distinguishable: T=2 must SHRINK the logit magnitude."""
        cool = AffineLogitCalibration(intercept=0.0, temperature=2.0, tour="atp", n_rows=1)
        assert 0.5 < cool.apply(0.9) < 0.9  # shrink toward half, never sharpen
        expected = 1.0 / (1.0 + math.exp(-(math.log(0.9 / 0.1) / 2.0)))
        assert cool.apply(0.9) == pytest.approx(expected, abs=1e-15)

    def test_tour_is_pinned_on_the_object(self) -> None:
        """Cross-tour application is structurally visible: the fitted object carries
        its tour and callers must match it (script-level pairing is pinned by the
        evidence-role tests)."""
        cal = AffineLogitCalibration(intercept=0.1, temperature=1.1, tour="atp", n_rows=5)
        assert cal.tour == "atp"


def _golden_corpus(
    true_a: float, true_t: float, n: int, base: int
) -> tuple[list[Race], list[OOFFundamental]]:
    """Deterministic corpus with LARGE non-interned runner ids (base+), so canonical
    selection and the win label cannot pass via int interning; winner is sometimes the
    higher id so `==` is distinguishable from `<=`."""
    races: list[Race] = []
    rows: list[OOFFundamental] = []
    for i in range(n):
        z = -2.5 + 5.0 * i / (n - 1)
        p_raw = _sigmoid(z)
        p_true = _sigmoid(true_a + z / true_t)
        frac = ((i + base) * 0.6180339887498949) % 1.0
        a_id, b_id = base + i * 2, base + i * 2 + 1
        winner = a_id if frac < p_true else b_id
        race = Race(
            race_id=f"c{base}_{i}",
            cluster=calendar_day_assignment("tennis", date(2024, 1, 1)),
            runners=(
                RunnerRow(runner_id=a_id, features={"placeholder": _D0}),
                RunnerRow(runner_id=b_id, features={"placeholder": _D0}),
            ),
            winner_id=winner,
        )
        races.append(race)
        prov = StageOneProvenance(
            trained_through=ChronologyKey(ordinal=date(2024, 1, 1).toordinal() - 1),
            training_race_ids=frozenset(),
            training_race_ids_digest="0" * 64,
            horizon=_HORIZON,
        )
        rows.append(OOFFundamental(race_id=race.race_id, runner_id=a_id, p_fundamental=p_raw, provenance=prov))
        rows.append(OOFFundamental(race_id=race.race_id, runner_id=b_id, p_fundamental=1.0 - p_raw, provenance=prov))
    return races, rows


class TestGoldenFitExactPins:
    """Kill class (founder §3, applied to the calibration Newton solver): exact
    bitwise pins of the fitted (intercept, temperature) across THREE corpora with
    distinct true parameters. Any solver-path mutant that shifts the result by one ULP,
    changes the fixed point, or diverges dies here; a mutant that lands bit-identical on
    all three is exact-output evidence of genuine equivalence. Large non-interned ids
    also kill the canonical/label `is` and `<=` comparison mutants (L150/L164)."""

    GOLDEN = [
        (0.4, 1.5, 1500, 1000, 0.41019734330464014, 1.5010428385138586),
        (-0.3, 0.9, 1200, 20000, -0.3075516829965659, 0.8877951096351528),
        (0.0, 1.0, 800, 50000, 0.007361634153820743, 1.0026883507633426),
    ]

    @pytest.mark.parametrize(("true_a", "true_t", "n", "base", "exp_i", "exp_t"), GOLDEN)
    def test_exact_fit_pin(
        self, true_a: float, true_t: float, n: int, base: int, exp_i: float, exp_t: float
    ) -> None:
        races, rows = _golden_corpus(true_a, true_t, n, base)
        cal = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        assert cal.intercept == exp_i  # exact — one ULP is behavioural
        assert cal.temperature == exp_t
        assert cal.n_rows == n

    @pytest.mark.parametrize(("true_a", "true_t", "n", "base"), [g[:4] for g in GOLDEN])
    def test_returned_point_satisfies_the_mle_gradient_condition(
        self, true_a: float, true_t: float, n: int, base: int
    ) -> None:
        """Solver-path-independent semantic contract: the returned (intercept, 1/temperature)
        is the MLE, i.e. the canonical-row score-equation gradient is ~0. A mutant that
        converges to a non-optimal point fails regardless of its path."""
        races, rows = _golden_corpus(true_a, true_t, n, base)
        cal = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        a, b = cal.intercept, 1.0 / cal.temperature
        by_id = {r.race_id: r for r in races}
        low_row = {}
        for row in rows:
            race = by_id[row.race_id]
            low = min(rr.runner_id for rr in race.runners if not rr.non_runner)
            if row.runner_id == low:
                low_row[row.race_id] = row
        g_a: list[float] = []
        g_b: list[float] = []
        for race_id, row in low_row.items():
            race = by_id[race_id]
            y = 1.0 if race.winner_id == row.runner_id else 0.0
            z = math.log(row.p_fundamental / (1.0 - row.p_fundamental))
            p = _sigmoid(a + b * z)
            g_a.append(y - p)
            g_b.append((y - p) * z)
        assert abs(math.fsum(g_a)) < 1e-6
        assert abs(math.fsum(g_b)) < 1e-6


class TestFitGuardKills:
    def test_horizon_guard_uses_value_equality_not_identity(self) -> None:
        """L143 kill: an equal-but-non-identical horizon must be ACCEPTED (kills the
        `is not` mutant), and a lexicographically-smaller foreign horizon must be
        REFUSED (kills the `>` mutant)."""
        races, rows = _golden_corpus(0.0, 1.0, 60, 70000)
        # equal-but-forced-distinct horizon object
        other_equal = HorizonLabel("pre-off-tennis" + "")
        assert other_equal == _HORIZON
        cal = fit_affine_logit_calibration(races, rows, horizon=other_equal, tour="atp")
        assert cal.n_rows == 60  # accepted despite non-identity
        # foreign horizons on BOTH sides of the rows' horizon must be refused — the
        # smaller side alone leaves the `>` mutant alive (rows' horizon > smaller is
        # already True), so a LARGER foreign horizon is required to kill it.
        smaller = HorizonLabel("aaa-earlier")
        larger = HorizonLabel("zzz-later")
        assert smaller < _HORIZON < larger
        with pytest.raises(CrossFitViolation):
            fit_affine_logit_calibration(races, rows, horizon=smaller, tour="atp")
        with pytest.raises(CrossFitViolation):
            fit_affine_logit_calibration(races, rows, horizon=larger, tour="atp")

    def test_canonical_selection_rejects_duplicate_and_missing(self) -> None:
        """L150 kill: `<=` would mark BOTH rows canonical (duplicate → refuse); `is`
        with large ids would mark NONE canonical (no rows → refuse). The correct `==`
        selects exactly one per match and fits."""
        races, rows = _golden_corpus(0.2, 1.3, 80, 90000)
        cal = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        assert cal.n_rows == 80  # exactly one canonical row per match


class TestCalibrationPredicateSeams:
    """Exact-boundary kills for the Newton predicate seams (founder round-3 pattern
    applied to the calibration solver): the < vs <= vs != boundary is pinned with
    math.nextafter so a one-ULP boundary shift dies."""

    def test_newton_iteration_allowed_boundary(self) -> None:
        m = MAX_NEWTON_ITERATIONS
        assert newton_iteration_allowed(m - 1, m)
        assert not newton_iteration_allowed(m, m)
        assert not newton_iteration_allowed(m + 1, m)

    def test_hessian_singular_boundary_exact(self) -> None:
        eps = DET_EPSILON
        assert hessian_is_singular(eps)  # <= boundary included
        assert hessian_is_singular(-eps)
        assert hessian_is_singular(math.nextafter(eps, 0.0))
        assert not hessian_is_singular(math.nextafter(eps, math.inf))

    def test_step_converged_boundary_exact(self) -> None:
        eps = STEP_EPSILON
        assert step_has_converged(eps)
        assert step_has_converged(math.nextafter(eps, 0.0))
        assert not step_has_converged(math.nextafter(eps, math.inf))


class TestConstructorAndSignatureKills:
    def test_zero_n_rows_is_valid_metadata(self) -> None:
        """L98 kill: only a NEGATIVE count is invalid; zero is a representable count
        (kills n_rows < 1, <= 0, == 0)."""
        cal = AffineLogitCalibration(intercept=0.0, temperature=1.0, tour="atp", n_rows=0)
        assert cal.n_rows == 0
        with pytest.raises(CalibrationFitError):
            AffineLogitCalibration(intercept=0.0, temperature=1.0, tour="atp", n_rows=-1)

    def test_tour_rejects_leading_and_trailing_whitespace(self) -> None:
        """L96 kill: untrimmed tour is refused on BOTH sides (kills > and <, which each
        miss one side because the space char sorts below letters)."""
        with pytest.raises(CalibrationFitError):
            AffineLogitCalibration(intercept=0.0, temperature=1.0, tour=" atp", n_rows=1)
        with pytest.raises(CalibrationFitError):
            AffineLogitCalibration(intercept=0.0, temperature=1.0, tour="atp ", n_rows=1)

    def test_fit_horizon_and_tour_are_keyword_only(self) -> None:
        """L122 kill: the `*` marker makes horizon and tour keyword-only."""
        import inspect

        params = inspect.signature(fit_affine_logit_calibration).parameters
        assert params["horizon"].kind is inspect.Parameter.KEYWORD_ONLY
        assert params["tour"].kind is inspect.Parameter.KEYWORD_ONLY


class TestCalibrationBudgetSeam:
    """Founder §5: iteration-budget behaviour via an injected small maximum (registered
    default MAX_NEWTON_ITERATIONS unchanged). A known corpus converges in exactly K=6
    Newton steps. Kills counter start/increment and cap-boundary mutants."""

    K = 6

    def _corpus(self) -> tuple[list[Race], list[OOFFundamental]]:
        return _golden_corpus(0.4, 1.5, 400, 80000)

    def test_cap_equal_to_exact_count_permits_convergence(self) -> None:
        races, rows = self._corpus()
        got = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp", maximum=self.K)
        default = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        assert (got.intercept, got.temperature) == (default.intercept, default.temperature)

    def test_cap_below_exact_count_refuses(self) -> None:
        races, rows = self._corpus()
        with pytest.raises(CalibrationFitError, match="did not converge"):
            fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp", maximum=self.K - 1)

    def test_registered_default_cap_pinned(self) -> None:
        assert MAX_NEWTON_ITERATIONS == 100


class TestSingularityPredicateAbsoluteBoundary:
    """Founder §9: pin hessian_is_singular against the LITERAL 1e-12 boundary (not the
    DET_EPSILON symbol), so a NumberReplacer on DET_EPSILON (1e-12 -> ~1.0) dies."""

    def test_exact_boundary(self) -> None:
        assert hessian_is_singular(1e-12) is True
        assert hessian_is_singular(-1e-12) is True
        assert hessian_is_singular(math.nextafter(1e-12, 0.0)) is True
        assert hessian_is_singular(math.nextafter(1e-12, math.inf)) is False

    def test_well_conditioned_determinants_are_not_singular(self) -> None:
        # kills DET_EPSILON -> ~1.0: these would be wrongly flagged singular under the mutant
        for det in (1e-6, 1e-3, 0.5, 1.0, 42.0):
            assert hessian_is_singular(det) is False
            assert hessian_is_singular(-det) is False


class TestFiniteParameterPredicate:
    """Founder §10: BOTH parameters must be finite; a one-sided non-finite is refused."""

    def test_one_sided_non_finite_is_not_finite(self) -> None:
        nan, inf = float("nan"), float("inf")
        assert parameters_finite(0.1, 0.2) is True
        assert parameters_finite(0.1, nan) is False   # finite / NaN
        assert parameters_finite(nan, 0.2) is False   # NaN / finite
        assert parameters_finite(0.1, inf) is False   # finite / +inf
        assert parameters_finite(-inf, 0.2) is False  # -inf / finite
        assert parameters_finite(nan, inf) is False


class TestSlopeValidator:
    """Founder §11: every non-positive OR non-finite slope is refused before the
    reciprocal temperature is computed."""

    def test_slope_boundary_cases(self) -> None:
        assert slope_is_valid(1.0) is True
        assert slope_is_valid(math.nextafter(0.0, 1.0)) is True  # smallest positive
        assert slope_is_valid(0.0) is False
        assert slope_is_valid(-0.0) is False
        assert slope_is_valid(-1e-9) is False
        assert slope_is_valid(-3.0) is False
        assert slope_is_valid(float("nan")) is False
        assert slope_is_valid(float("inf")) is False   # inf slope -> temperature 0, invalid
        assert slope_is_valid(float("-inf")) is False


class TestCanonicalDistinctObjectIdentity:
    """Founder §6: equality (not object identity) must control canonical-row selection
    and the win label. Uses runtime-distinct but equal competitor ids parsed
    independently (int(str(...)) for values > 256 that are never interned)."""

    def _distinct(self, n: int) -> int:
        return int(str(n))  # a fresh int object, equal to n but not `is` n

    def test_equal_but_distinct_ids_still_fit(self) -> None:
        races: list[Race] = []
        rows: list[OOFFundamental] = []
        for i in range(60):
            base = 100000 + i * 2
            # Race carries one set of id objects; the OOF rows carry INDEPENDENT equal objects.
            a_race, b_race = self._distinct(base), self._distinct(base + 1)
            a_oof, b_oof = self._distinct(base), self._distinct(base + 1)
            assert a_race is not a_oof and a_race == a_oof  # equal, distinct objects
            z = -1.5 + 3.0 * i / 59
            p = _sigmoid(z)
            frac = (i * 0.6180339887498949) % 1.0
            a_wins = frac < p  # label correlated with the canonical raw prob -> positive slope
            race = Race(
                race_id=f"d{i}",
                cluster=calendar_day_assignment("tennis", date(2024, 1, 1)),
                runners=(
                    RunnerRow(runner_id=a_race, features={"placeholder": _D0}),
                    RunnerRow(runner_id=b_race, features={"placeholder": _D0}),
                ),
                winner_id=self._distinct(base) if a_wins else self._distinct(base + 1),
            )
            races.append(race)
            prov = StageOneProvenance(
                trained_through=ChronologyKey(ordinal=date(2024, 1, 1).toordinal() - 1),
                training_race_ids=frozenset(), training_race_ids_digest="0" * 64, horizon=_HORIZON,
            )
            rows.append(OOFFundamental(race_id=race.race_id, runner_id=a_oof, p_fundamental=p, provenance=prov))
            rows.append(OOFFundamental(race_id=race.race_id, runner_id=b_oof, p_fundamental=1.0 - p, provenance=prov))
        # `is` mutants would select NO canonical row (identity fails) -> refuse; `==` fits.
        cal = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        assert cal.n_rows == 60
