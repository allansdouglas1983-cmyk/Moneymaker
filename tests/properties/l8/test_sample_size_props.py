"""SPEC-094 properties: sample-size monotonicity and digest determinism.

SPECIFICATION.md §9.2: ``N ~ (z_alpha + z_beta)^2 * sigma_d^2 / delta^2``. These
properties pin the DIRECTION every input must move ``n_required`` (or must not decrease
it) so a future edit cannot silently invert the arithmetic, plus digest determinism for
the pre-registration flow documented in ``l8_evidence.sample_size``.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l8_evidence.sample_size import PowerAssumptions, derive_sample_size

pytestmark = pytest.mark.spec("SPEC-094")

_ALPHA = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.20"), places=3)
_POWER = st.decimals(min_value=Decimal("0.55"), max_value=Decimal("0.95"), places=3)
_SIGMA_D = st.decimals(min_value=Decimal("0.10"), max_value=Decimal("5.00"), places=2)
_DELTA = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("2.00"), places=2)
_TWO_SIDED = st.booleans()


def _assumptions(
    *, alpha: Decimal, power: Decimal, sigma_d: Decimal, delta: Decimal, two_sided: bool
) -> PowerAssumptions:
    return PowerAssumptions(alpha=alpha, power=power, sigma_d=sigma_d, delta=delta, two_sided=two_sided)


@given(
    alpha=_ALPHA,
    power=_POWER,
    sigma_d=_SIGMA_D,
    delta_small=_DELTA,
    delta_bump=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1.00"), places=2),
    two_sided=_TWO_SIDED,
)
@settings(max_examples=100)
def test_n_required_is_non_increasing_in_delta(
    alpha: Decimal, power: Decimal, sigma_d: Decimal, delta_small: Decimal, delta_bump: Decimal, two_sided: bool
) -> None:
    delta_large = delta_small + delta_bump
    smaller_delta_plan = derive_sample_size(
        _assumptions(alpha=alpha, power=power, sigma_d=sigma_d, delta=delta_small, two_sided=two_sided)
    )
    larger_delta_plan = derive_sample_size(
        _assumptions(alpha=alpha, power=power, sigma_d=sigma_d, delta=delta_large, two_sided=two_sided)
    )
    # A larger minimum meaningful effect (delta) requires no MORE races, never more.
    assert larger_delta_plan.n_required <= smaller_delta_plan.n_required


@given(
    alpha=_ALPHA,
    power=_POWER,
    sigma_d_small=_SIGMA_D,
    sigma_d_bump=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1.00"), places=2),
    delta=_DELTA,
    two_sided=_TWO_SIDED,
)
@settings(max_examples=100)
def test_n_required_is_non_decreasing_in_sigma_d(
    alpha: Decimal, power: Decimal, sigma_d_small: Decimal, sigma_d_bump: Decimal, delta: Decimal, two_sided: bool
) -> None:
    sigma_d_large = sigma_d_small + sigma_d_bump
    smaller_sigma_plan = derive_sample_size(
        _assumptions(alpha=alpha, power=power, sigma_d=sigma_d_small, delta=delta, two_sided=two_sided)
    )
    larger_sigma_plan = derive_sample_size(
        _assumptions(alpha=alpha, power=power, sigma_d=sigma_d_large, delta=delta, two_sided=two_sided)
    )
    # Noisier races (larger sigma_d) never require FEWER observations.
    assert larger_sigma_plan.n_required >= smaller_sigma_plan.n_required


@given(
    alpha=_ALPHA,
    power_small=st.decimals(min_value=Decimal("0.55"), max_value=Decimal("0.80"), places=3),
    power_bump=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.10"), places=3),
    sigma_d=_SIGMA_D,
    delta=_DELTA,
    two_sided=_TWO_SIDED,
)
@settings(max_examples=100)
def test_n_required_is_non_decreasing_in_power(
    alpha: Decimal, power_small: Decimal, power_bump: Decimal, sigma_d: Decimal, delta: Decimal, two_sided: bool
) -> None:
    power_large = power_small + power_bump
    lower_power_plan = derive_sample_size(
        _assumptions(alpha=alpha, power=power_small, sigma_d=sigma_d, delta=delta, two_sided=two_sided)
    )
    higher_power_plan = derive_sample_size(
        _assumptions(alpha=alpha, power=power_large, sigma_d=sigma_d, delta=delta, two_sided=two_sided)
    )
    # Demanding more power never requires FEWER observations.
    assert higher_power_plan.n_required >= lower_power_plan.n_required


@given(alpha=_ALPHA, power=_POWER, sigma_d=_SIGMA_D, delta=_DELTA, two_sided=_TWO_SIDED)
@settings(max_examples=50)
def test_content_digest_is_deterministic_across_rebuilds(
    alpha: Decimal, power: Decimal, sigma_d: Decimal, delta: Decimal, two_sided: bool
) -> None:
    first = derive_sample_size(
        _assumptions(alpha=alpha, power=power, sigma_d=sigma_d, delta=delta, two_sided=two_sided)
    )
    second = derive_sample_size(
        _assumptions(alpha=alpha, power=power, sigma_d=sigma_d, delta=delta, two_sided=two_sided)
    )
    assert first.content_digest() == second.content_digest()
    assert first.n_required == second.n_required


@given(alpha=_ALPHA, power=_POWER, sigma_d=_SIGMA_D, delta=_DELTA, two_sided=_TWO_SIDED)
@settings(max_examples=50)
def test_n_required_is_always_a_positive_integer(
    alpha: Decimal, power: Decimal, sigma_d: Decimal, delta: Decimal, two_sided: bool
) -> None:
    plan = derive_sample_size(_assumptions(alpha=alpha, power=power, sigma_d=sigma_d, delta=delta, two_sided=two_sided))
    assert isinstance(plan.n_required, int)
    assert plan.n_required >= 1
