"""SPEC-094: pre-registered sample size, power assumptions and borrowed-constant hygiene.

SPECIFICATION.md §9.2 ("Sample size is derived, not asserted") and §9.3 ("No borrowed
thresholds"), plus ``.claude/rules/evidence.md``'s "No borrowed thresholds" section.
Covers ``PowerAssumptions``/``SampleSizePlan`` shape validation, the deterministic
standard-normal inverse-CDF anchors, a hand-computed sample-size fixture, digest
determinism, the borrowed-constant static scan (including a run over the real
``specs/gates/v1.yaml`` and ``specs/gates/predictor-p1.yaml``), and the no-default-
arguments discipline for ``PowerAssumptions``.
"""
from __future__ import annotations

import inspect
import math
from decimal import Decimal
from pathlib import Path

import pytest

from l8_evidence.sample_size import (
    BORROWED_CONSTANTS,
    BorrowedConstantError,
    FORMULA,
    PowerAssumptions,
    SampleSizeError,
    SampleSizePlan,
    assert_no_borrowed_gate_constants,
    derive_sample_size,
    plan_for_registration,
    standard_normal_inverse_cdf,
)

pytestmark = pytest.mark.spec("SPEC-094")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_V1_GATE_SPEC = _REPO_ROOT / "specs" / "gates" / "v1.yaml"
_PREDICTOR_P1_GATE_SPEC = _REPO_ROOT / "specs" / "gates" / "predictor-p1.yaml"


def _assumptions(
    *,
    alpha: Decimal = Decimal("0.05"),
    power: Decimal = Decimal("0.8"),
    sigma_d: Decimal = Decimal("1"),
    delta: Decimal = Decimal("0.1"),
    two_sided: bool = True,
) -> PowerAssumptions:
    return PowerAssumptions(
        alpha=alpha, power=power, sigma_d=sigma_d, delta=delta, two_sided=two_sided
    )


# --------------------------------------------------------------------------------------
# PowerAssumptions validation
# --------------------------------------------------------------------------------------


def test_power_assumptions_accepts_valid_shape() -> None:
    assumptions = _assumptions()
    assert assumptions.alpha == Decimal("0.05")
    assert assumptions.power == Decimal("0.8")
    assert assumptions.beta == Decimal("0.2")


@pytest.mark.parametrize("alpha", [Decimal("0"), Decimal("1"), Decimal("-0.01"), Decimal("1.5")])
def test_power_assumptions_refuses_alpha_outside_open_unit_interval(alpha: Decimal) -> None:
    with pytest.raises(SampleSizeError):
        _assumptions(alpha=alpha)


@pytest.mark.parametrize("power", [Decimal("0"), Decimal("1"), Decimal("-0.1"), Decimal("2")])
def test_power_assumptions_refuses_power_outside_open_unit_interval(power: Decimal) -> None:
    with pytest.raises(SampleSizeError):
        _assumptions(power=power)


@pytest.mark.parametrize("sigma_d", [Decimal("0"), Decimal("-1")])
def test_power_assumptions_refuses_non_positive_sigma_d(sigma_d: Decimal) -> None:
    with pytest.raises(SampleSizeError):
        _assumptions(sigma_d=sigma_d)


@pytest.mark.parametrize("delta", [Decimal("0"), Decimal("-0.5")])
def test_power_assumptions_refuses_non_positive_delta(delta: Decimal) -> None:
    with pytest.raises(SampleSizeError):
        _assumptions(delta=delta)


def test_power_assumptions_refuses_float_alpha() -> None:
    with pytest.raises(SampleSizeError):
        PowerAssumptions(alpha=0.05, power=Decimal("0.8"), sigma_d=Decimal("1"), delta=Decimal("0.1"), two_sided=True)  # type: ignore[arg-type]


def test_power_assumptions_is_frozen() -> None:
    assumptions = _assumptions()
    with pytest.raises(Exception):  # noqa: PT011 - dataclasses raise FrozenInstanceError
        assumptions.alpha = Decimal("0.10")  # type: ignore[misc]


def test_power_assumptions_has_no_default_arguments() -> None:
    """No borrowed defaults (SPEC-094): every argument to PowerAssumptions is explicit."""
    for name, parameter in inspect.signature(PowerAssumptions).parameters.items():
        assert parameter.default is inspect.Parameter.empty, f"{name} must not have a default"


def test_derive_sample_size_has_no_default_arguments() -> None:
    for name, parameter in inspect.signature(derive_sample_size).parameters.items():
        assert parameter.default is inspect.Parameter.empty, f"{name} must not have a default"


# --------------------------------------------------------------------------------------
# standard_normal_inverse_cdf anchors
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("p", "expected"),
    [
        (0.975, 1.959964),
        (0.95, 1.644854),
        (0.90, 1.281552),
    ],
)
def test_standard_normal_inverse_cdf_matches_known_anchors_to_4dp(p: float, expected: float) -> None:
    # Anchors are quoted to 6 significant decimals; requiring agreement well inside 1e-6
    # comfortably exceeds "correct to 4 decimal places" while pinning the exact expected
    # values a reviewer can check against a statistics table.
    assert standard_normal_inverse_cdf(p) == pytest.approx(expected, abs=1e-6)


def test_standard_normal_inverse_cdf_is_antisymmetric_around_one_half() -> None:
    assert standard_normal_inverse_cdf(0.5) == pytest.approx(0.0, abs=1e-12)
    assert standard_normal_inverse_cdf(0.025) == pytest.approx(-standard_normal_inverse_cdf(0.975), abs=1e-9)


@pytest.mark.parametrize("p", [0.0, 1.0, -0.1, 1.1])
def test_standard_normal_inverse_cdf_refuses_out_of_range_p(p: float) -> None:
    with pytest.raises(SampleSizeError):
        standard_normal_inverse_cdf(p)


def test_standard_normal_inverse_cdf_covers_the_low_tail_branch() -> None:
    # p < 0.02425 exercises the low-tail rational-approximation branch explicitly.
    z = standard_normal_inverse_cdf(0.001)
    assert z < -2.5


def test_standard_normal_inverse_cdf_covers_the_high_tail_branch() -> None:
    # p > 1 - 0.02425 exercises the high-tail rational-approximation branch explicitly.
    z = standard_normal_inverse_cdf(0.999)
    assert z > 2.5


# --------------------------------------------------------------------------------------
# z_alpha: two-sided vs one-sided
# --------------------------------------------------------------------------------------


def test_two_sided_alpha_uses_half_the_tail() -> None:
    two_sided_plan = derive_sample_size(_assumptions(alpha=Decimal("0.05"), two_sided=True))
    one_sided_plan = derive_sample_size(_assumptions(alpha=Decimal("0.05"), two_sided=False))
    assert two_sided_plan.z_alpha == pytest.approx(standard_normal_inverse_cdf(1 - 0.025), abs=1e-9)
    assert one_sided_plan.z_alpha == pytest.approx(standard_normal_inverse_cdf(1 - 0.05), abs=1e-9)
    assert two_sided_plan.z_alpha > one_sided_plan.z_alpha


# --------------------------------------------------------------------------------------
# derive_sample_size: hand-computed fixture
# --------------------------------------------------------------------------------------


def test_derive_sample_size_matches_hand_computed_fixture() -> None:
    # alpha=0.05 two-sided, power=0.8, sigma_d=1, delta=0.1
    # z_alpha = Phi^-1(0.975) ~ 1.959964 ; z_beta = Phi^-1(0.8) ~ 0.841621
    # N = ceil((1.959964 + 0.841621)^2 * 1^2 / 0.1^2)
    plan = derive_sample_size(
        _assumptions(alpha=Decimal("0.05"), power=Decimal("0.8"), sigma_d=Decimal("1"), delta=Decimal("0.1"), two_sided=True)
    )
    z_alpha = standard_normal_inverse_cdf(0.975)
    z_beta = standard_normal_inverse_cdf(0.8)
    expected_n = math.ceil(((z_alpha + z_beta) ** 2) * (1.0**2) / (0.1**2))
    assert expected_n == 785
    assert plan.n_required == expected_n
    assert plan.n_required == 785
    assert plan.formula == FORMULA
    assert plan.formula == "N = (z_alpha + z_beta)^2 * sigma_d^2 / delta^2"


def test_derive_sample_size_n_required_is_at_least_one_even_for_tiny_requirement() -> None:
    # A trivially achievable target (huge delta relative to sigma_d) still floors at 1.
    plan = derive_sample_size(
        _assumptions(alpha=Decimal("0.5") - Decimal("0.001"), power=Decimal("0.51"), sigma_d=Decimal("0.001"), delta=Decimal("100"))
    )
    assert plan.n_required >= 1


def test_plan_for_registration_is_the_same_as_derive_sample_size() -> None:
    assumptions = _assumptions()
    assert plan_for_registration(assumptions) == derive_sample_size(assumptions)


# --------------------------------------------------------------------------------------
# SampleSizePlan shape / digest
# --------------------------------------------------------------------------------------


def test_sample_size_plan_is_frozen() -> None:
    plan = derive_sample_size(_assumptions())
    with pytest.raises(Exception):  # noqa: PT011
        plan.n_required = 1  # type: ignore[misc]


def test_sample_size_plan_refuses_n_required_below_one() -> None:
    with pytest.raises(SampleSizeError):
        SampleSizePlan(assumptions=_assumptions(), z_alpha=1.96, z_beta=0.84, n_required=0)


def test_sample_size_plan_refuses_a_tampered_formula() -> None:
    with pytest.raises(SampleSizeError):
        SampleSizePlan(assumptions=_assumptions(), z_alpha=1.96, z_beta=0.84, n_required=10, formula="N = anything else")


def test_content_digest_is_deterministic_for_identical_plans() -> None:
    a = derive_sample_size(_assumptions())
    b = derive_sample_size(_assumptions())
    assert a.content_digest() == b.content_digest()
    assert a.content_digest().startswith("sha256:")


def test_content_digest_changes_when_delta_changes() -> None:
    a = derive_sample_size(_assumptions(delta=Decimal("0.1")))
    b = derive_sample_size(_assumptions(delta=Decimal("0.2")))
    assert a.content_digest() != b.content_digest()


# --------------------------------------------------------------------------------------
# Borrowed-constant hygiene
# --------------------------------------------------------------------------------------


def test_borrowed_constants_registry_names_the_four_rejected_thresholds() -> None:
    assert BORROWED_CONSTANTS == ("dR2>=0.01", "t>=3", "ECE<=0.02", "2000 bets")


def test_assert_no_borrowed_gate_constants_passes_on_clean_text() -> None:
    assert_no_borrowed_gate_constants("gates:\n  - gate_id: GATE-1\n    kind: evidence\n")


@pytest.mark.parametrize(
    "bad_text",
    [
        "# a stray note: dR2>=0.01 was the old rule\n",
        "# ECE<=0.02 used to be a gate\n",
        "# once observed t >= 3 we used to stop\n",
        "# roughly 2000 races should do it\n",
    ],
)
def test_assert_no_borrowed_gate_constants_raises_on_constructed_bad_yaml(bad_text: str) -> None:
    with pytest.raises(BorrowedConstantError):
        assert_no_borrowed_gate_constants(bad_text)


def test_assert_no_borrowed_gate_constants_does_not_false_positive_on_unrelated_numbers() -> None:
    # "2,000" style numbers elsewhere (e.g. an unrelated year-like or ID-like token that is
    # not the standalone number 2000) must not trip the scan.
    assert_no_borrowed_gate_constants("spec_section: SPECIFICATION.md section 20001\n")
    assert_no_borrowed_gate_constants("item_id: SPEC-036_to_045_lineage\n")


def test_the_real_v1_gate_spec_passes_the_borrowed_constant_scan() -> None:
    assert_no_borrowed_gate_constants(_V1_GATE_SPEC.read_text(encoding="utf-8"))


def test_the_real_predictor_p1_gate_spec_passes_the_borrowed_constant_scan() -> None:
    assert_no_borrowed_gate_constants(_PREDICTOR_P1_GATE_SPEC.read_text(encoding="utf-8"))
