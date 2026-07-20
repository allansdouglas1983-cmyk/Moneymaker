"""SPEC-106 — WinProbabilityDistribution output contract (Stage 2G Slice 2; red first).

Registration: specs/programme/dp1-glicko2-registration-v1.yaml `prediction` block.
Central = frozen 20-node Gauss-Hermite posterior mean of sigmoid(delta + s*sqrt(2)*x)
over N(0,1); interval = exact sigmoid image of delta +/- 1.644854*s (ANALYTIC_
PROPAGATION); coherence P(B) = 1 - P(A) exactly; bounds strictly inside
(1e-12, 1 - 1e-12). Uncertainty derives from the rating state — never a fabricated
percentage.
"""
from __future__ import annotations

import dataclasses
import math
from datetime import date

import pytest

from sport_tennis.dp1_distribution import (
    DP1_MODEL_VERSION,
    GH_NODE_COUNT,
    INTERVAL_Z,
    PROBABILITY_FLOOR,
    UNCERTAINTY_METHOD,
    DistributionValidationError,
    WinProbabilityDistribution,
    central_win_probability,
    gauss_hermite_nodes,
    interval_bounds,
    win_probability_distributions,
)
from sport_tennis.glicko2_family import PlayerState

pytestmark = pytest.mark.spec("SPEC-106")


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class TestFrozenPredictionConstants:
    def test_frozen_values(self) -> None:
        assert GH_NODE_COUNT == 20
        assert INTERVAL_Z == 1.644854
        assert PROBABILITY_FLOOR == 1e-12
        assert UNCERTAINTY_METHOD == "ANALYTIC_PROPAGATION"
        assert DP1_MODEL_VERSION == "dynamic-glicko2-v1"


class TestGaussHermiteRule:
    """The quadrature rule is self-verified, not trusted from a tabulation."""

    def test_node_count_and_symmetry(self) -> None:
        rule = gauss_hermite_nodes(GH_NODE_COUNT)
        assert len(rule) == GH_NODE_COUNT
        nodes = [x for x, _ in rule]
        assert nodes == sorted(nodes)
        for x, w in rule:
            assert w > 0.0
            # the rule is symmetric: -x appears with the same weight
            match = [w2 for x2, w2 in rule if x2 == pytest.approx(-x, abs=1e-12)]
            assert match and match[0] == pytest.approx(w, rel=1e-12)

    def test_weights_sum_to_sqrt_pi(self) -> None:
        rule = gauss_hermite_nodes(GH_NODE_COUNT)
        assert math.fsum(w for _, w in rule) == pytest.approx(math.sqrt(math.pi), abs=1e-12)

    def test_polynomial_exactness(self) -> None:
        """Integral of x^(2k) e^(-x^2) = Gamma(k + 1/2); exact for degree <= 2n-1."""
        rule = gauss_hermite_nodes(GH_NODE_COUNT)
        for k in (1, 2, 5, 10):
            quad = math.fsum(w * x ** (2 * k) for x, w in rule)
            exact = math.gamma(k + 0.5)
            assert quad == pytest.approx(exact, rel=1e-10)

    def test_determinism(self) -> None:
        assert gauss_hermite_nodes(GH_NODE_COUNT) == gauss_hermite_nodes(GH_NODE_COUNT)


class TestCentralProbability:
    def test_zero_uncertainty_is_the_sigmoid(self) -> None:
        assert central_win_probability(0.7, 0.0) == pytest.approx(_sigmoid(0.7), abs=1e-15)

    def test_zero_delta_is_exactly_half(self) -> None:
        assert central_win_probability(0.0, 1.3) == pytest.approx(0.5, abs=1e-14)

    def test_uncertainty_shrinks_toward_half(self) -> None:
        """The posterior mean of a sigmoid under widening normal uncertainty moves
        toward 1/2 (an implementation ignoring s must fail here)."""
        p0 = central_win_probability(1.0, 0.0)
        p1 = central_win_probability(1.0, 1.0)
        p2 = central_win_probability(1.0, 3.0)
        assert 0.5 < p2 < p1 < p0

    def test_monotone_in_delta(self) -> None:
        s = 0.8
        probs = [central_win_probability(d, s) for d in (-2.0, -0.5, 0.0, 0.5, 2.0)]
        assert probs == sorted(probs)
        assert all(0.0 < p < 1.0 for p in probs)


class TestIntervalBounds:
    def test_exact_sigmoid_image(self) -> None:
        lower, upper = interval_bounds(0.4, 0.9)
        assert lower == pytest.approx(_sigmoid(0.4 - INTERVAL_Z * 0.9), abs=1e-15)
        assert upper == pytest.approx(_sigmoid(0.4 + INTERVAL_Z * 0.9), abs=1e-15)

    def test_wider_uncertainty_widens_the_interval(self) -> None:
        widths = []
        for s in (0.1, 0.5, 1.0, 2.0):
            lower, upper = interval_bounds(0.4, s)
            widths.append(upper - lower)
        assert widths == sorted(widths)

    def test_zero_uncertainty_collapses_to_the_point(self) -> None:
        lower, upper = interval_bounds(-0.3, 0.0)
        assert lower == upper == pytest.approx(_sigmoid(-0.3), abs=1e-15)


def _dist(**overrides: object) -> WinProbabilityDistribution:
    base: dict[str, object] = {
        "central_win_probability": 0.6,
        "lower_probability_bound": 0.4,
        "upper_probability_bound": 0.8,
        "uncertainty_method": UNCERTAINTY_METHOD,
        "rating": 1520.0,
        "rating_deviation": 120.0,
        "volatility": 0.06,
        "prior_match_count": 12,
        "last_active_date": date(2026, 5, 30),
        "data_quality_status": "OK",
        "model_version": DP1_MODEL_VERSION,
        "state_digest": "a" * 64,
        "feature_input_digest": "b" * 64,
    }
    base.update(overrides)
    return WinProbabilityDistribution(**base)  # type: ignore[arg-type]


class TestDistributionContract:
    def test_all_thirteen_fields_present(self) -> None:
        names = {f.name for f in dataclasses.fields(WinProbabilityDistribution)}
        assert names == {
            "central_win_probability",
            "lower_probability_bound",
            "upper_probability_bound",
            "uncertainty_method",
            "rating",
            "rating_deviation",
            "volatility",
            "prior_match_count",
            "last_active_date",
            "data_quality_status",
            "model_version",
            "state_digest",
            "feature_input_digest",
        }

    def test_frozen(self) -> None:
        d = _dist()
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.central_win_probability = 0.9  # type: ignore[misc]

    def test_ordering_enforced(self) -> None:
        with pytest.raises(DistributionValidationError):
            _dist(lower_probability_bound=0.7, central_win_probability=0.6)
        with pytest.raises(DistributionValidationError):
            _dist(upper_probability_bound=0.5, central_win_probability=0.6)

    def test_bounds_enforced(self) -> None:
        with pytest.raises(DistributionValidationError):
            _dist(lower_probability_bound=0.0)
        with pytest.raises(DistributionValidationError):
            _dist(upper_probability_bound=1.0)
        with pytest.raises(DistributionValidationError):
            _dist(central_win_probability=float("nan"))

    def test_negative_history_refused(self) -> None:
        with pytest.raises(DistributionValidationError):
            _dist(prior_match_count=-1)


class TestPairCoherence:
    def test_pair_is_exactly_complementary(self) -> None:
        a = PlayerState(mu=0.8, phi=0.6, sigma=0.06)
        b = PlayerState(mu=-0.1, phi=1.2, sigma=0.06)
        da, db = win_probability_distributions(
            a,
            b,
            prior_match_count_a=30,
            prior_match_count_b=2,
            last_active_date_a=date(2026, 5, 20),
            last_active_date_b=date(2026, 2, 1),
            data_quality_status_a="OK",
            data_quality_status_b="COLD_START",
            feature_input_digest="c" * 64,
        )
        assert da.central_win_probability + db.central_win_probability == pytest.approx(1.0, abs=1e-15)
        assert db.lower_probability_bound == pytest.approx(1.0 - da.upper_probability_bound, abs=1e-15)
        assert db.upper_probability_bound == pytest.approx(1.0 - da.lower_probability_bound, abs=1e-15)
        assert da.central_win_probability > 0.5  # a is rated higher

    def test_state_digest_is_deterministic_and_state_sensitive(self) -> None:
        a = PlayerState(mu=0.8, phi=0.6, sigma=0.06)
        b = PlayerState(mu=-0.1, phi=1.2, sigma=0.06)
        kwargs: dict[str, object] = {
            "prior_match_count_a": 30,
            "prior_match_count_b": 2,
            "last_active_date_a": date(2026, 5, 20),
            "last_active_date_b": date(2026, 2, 1),
            "data_quality_status_a": "OK",
            "data_quality_status_b": "OK",
            "feature_input_digest": "c" * 64,
        }
        d1, _ = win_probability_distributions(a, b, **kwargs)  # type: ignore[arg-type]
        d2, _ = win_probability_distributions(a, b, **kwargs)  # type: ignore[arg-type]
        d3, _ = win_probability_distributions(
            PlayerState(mu=0.8000001, phi=0.6, sigma=0.06), b, **kwargs  # type: ignore[arg-type]
        )
        assert d1.state_digest == d2.state_digest
        assert d1.state_digest != d3.state_digest


def _numeric_central(delta: float, s: float) -> float:
    """Independent reference: Simpson integration of sigmoid(delta + s*sqrt(2)*x)
    against e^(-x^2)/sqrt(pi) — recomputed from the registration, sharing no code
    with the implementation's quadrature."""
    n = 4000
    lo, hi = -12.0, 12.0
    h = (hi - lo) / n
    total = 0.0
    c = s * math.sqrt(2.0)
    for i in range(n + 1):
        x = lo + i * h
        w = 1.0 if i in (0, n) else (4.0 if i % 2 else 2.0)
        total += w * _sigmoid(delta + c * x) * math.exp(-x * x)
    return total * h / 3.0 / math.sqrt(math.pi)


class TestCentralAgainstIndependentIntegral:
    """Kill class: any mutant of the scale, the node evaluation, or the weight
    normalisation deviates from an independently computed reference integral."""

    @pytest.mark.parametrize("delta", [-2.0, -0.4, 0.9, 3.0])
    @pytest.mark.parametrize(
        ("s", "tolerance"), [(0.3, 1e-12), (1.0, 1e-9), (2.5, 2e-4)]
    )
    def test_matches_reference(self, delta: float, s: float, tolerance: float) -> None:
        # tolerance = measured truncation error of the frozen 20-node rule at each s
        # (grows with s; ~5e-5 worst at s=2.5) with margin; mutants deviate by ~1e-2.
        assert central_win_probability(delta, s) == pytest.approx(
            _numeric_central(delta, s), abs=tolerance
        )


class TestNumericalEdges:
    def test_extreme_arguments_do_not_overflow(self) -> None:
        """Kill class: swapping the stable sigmoid branches overflows at |x| ~ 745."""
        lower, upper = interval_bounds(745.0, 0.0)
        assert lower == upper == 1.0 - PROBABILITY_FLOOR
        lower, upper = interval_bounds(-745.0, 0.0)
        assert lower == upper == PROBABILITY_FLOOR

    def test_clamp_is_exact_at_both_floors(self) -> None:
        assert central_win_probability(-50.0, 0.0) == PROBABILITY_FLOOR
        assert central_win_probability(50.0, 0.0) == 1.0 - PROBABILITY_FLOOR

    def test_rule_rejects_invalid_node_counts(self) -> None:
        for bad in (0, 1, 3, -2, 19):
            with pytest.raises(ValueError):
                gauss_hermite_nodes(bad)
        assert len(gauss_hermite_nodes(2)) == 2

    def test_golden_rule_digest_pinned(self) -> None:
        """The frozen 20-node rule is byte-stable: any mutant that changes a single
        node or weight bit fails; mutants that provably cannot change it are the
        classification set."""
        import hashlib

        rule = gauss_hermite_nodes(GH_NODE_COUNT)
        digest = hashlib.sha256(repr(rule).encode("utf-8")).hexdigest()
        assert digest == "3f44c4a04d27f640becf5c5573f82afd6dce05a98f61c46afd33f26a924cffe0"


class TestValidationBoundaries:
    """Exact-boundary kills for the contract guards."""

    def test_digest_guard_boundaries(self) -> None:
        for bad in ("a" * 63, "a" * 65, "A" * 64, "g" * 64, ""):
            with pytest.raises(DistributionValidationError):
                _dist(state_digest=bad)
        _dist(state_digest="0123456789abcdef" * 4)  # exactly 64 lowercase hex: valid

    def test_rating_deviation_zero_boundary(self) -> None:
        with pytest.raises(DistributionValidationError):
            _dist(rating_deviation=0.0)
        _dist(rating_deviation=math.nextafter(0.0, 1.0))  # smallest positive: valid

    def test_volatility_zero_boundary(self) -> None:
        with pytest.raises(DistributionValidationError):
            _dist(volatility=0.0)
        _dist(volatility=math.nextafter(0.0, 1.0))

    def test_probability_floor_boundaries_exact(self) -> None:
        _dist(
            lower_probability_bound=PROBABILITY_FLOOR,
            central_win_probability=0.5,
            upper_probability_bound=1.0 - PROBABILITY_FLOOR,
        )
        with pytest.raises(DistributionValidationError):
            _dist(lower_probability_bound=math.nextafter(PROBABILITY_FLOOR, 0.0))
        with pytest.raises(DistributionValidationError):
            _dist(
                upper_probability_bound=math.nextafter(1.0 - PROBABILITY_FLOOR, 1.0),
                central_win_probability=0.6,
            )

    def test_text_fields_reject_untrimmed(self) -> None:
        for field in ("uncertainty_method", "data_quality_status", "model_version"):
            with pytest.raises(DistributionValidationError):
                _dist(**{field: " padded "})
            with pytest.raises(DistributionValidationError):
                _dist(**{field: ""})

    def test_prior_count_boundary(self) -> None:
        _dist(prior_match_count=0)  # zero is a valid cold start
