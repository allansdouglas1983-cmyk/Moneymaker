"""SPEC-032 properties — the manifest's declared metamorphic set:

- output must vary with both alpha and beta (in the specified region: informative inputs);
- output must sum to 1 within each race;
- increasing p_fundamental at fixed p_market_info and alpha>0 must not decrease c_i;
plus bit-exact permutation invariance of the pure combiner.
"""
from __future__ import annotations

import math
from decimal import Decimal

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from l4_pricing.stage_two import combine
from l5_decision.prices import MarketInfoPrice

pytestmark = pytest.mark.spec("SPEC-032")

_P = st.floats(min_value=0.05, max_value=0.95, allow_nan=False, allow_infinity=False)
_COEF = st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False)
_MKT = st.decimals(min_value=Decimal("0.05"), max_value=Decimal("0.95"), places=2)


@st.composite
def _inputs(draw: st.DrawFn) -> tuple[dict[int, float], dict[int, MarketInfoPrice]]:
    field = draw(st.integers(min_value=2, max_value=6))
    p_fundamental = {i + 1: draw(_P) for i in range(field)}
    p_market = {i + 1: MarketInfoPrice(implied_probability=draw(_MKT)) for i in range(field)}
    return p_fundamental, p_market


@settings(max_examples=200)
@given(inputs=_inputs(), alpha=_COEF, beta=_COEF)
def test_output_sums_to_one_within_the_race(
    inputs: tuple[dict[int, float], dict[int, MarketInfoPrice]], alpha: float, beta: float
) -> None:
    p_fundamental, p_market = inputs
    c = combine(alpha=alpha, beta=beta, p_fundamental=p_fundamental, p_market=p_market)
    assert set(c) == set(p_fundamental)
    assert abs(math.fsum(c.values()) - 1.0) < 1e-12
    assert all(p > 0.0 for p in c.values())


@settings(max_examples=200)
@given(inputs=_inputs(), alpha_one=_COEF, alpha_two=_COEF, beta=_COEF)
def test_output_varies_with_alpha(
    inputs: tuple[dict[int, float], dict[int, MarketInfoPrice]],
    alpha_one: float,
    alpha_two: float,
    beta: float,
) -> None:
    p_fundamental, p_market = inputs
    assume(abs(alpha_one - alpha_two) > 1e-3)
    assume(len(set(p_fundamental.values())) > 1)  # the specified region: informative input
    a = combine(alpha=alpha_one, beta=beta, p_fundamental=p_fundamental, p_market=p_market)
    b = combine(alpha=alpha_two, beta=beta, p_fundamental=p_fundamental, p_market=p_market)
    assert a != b


@settings(max_examples=200)
@given(inputs=_inputs(), alpha=_COEF, beta_one=_COEF, beta_two=_COEF)
def test_output_varies_with_beta(
    inputs: tuple[dict[int, float], dict[int, MarketInfoPrice]],
    alpha: float,
    beta_one: float,
    beta_two: float,
) -> None:
    p_fundamental, p_market = inputs
    assume(abs(beta_one - beta_two) > 1e-3)
    assume(len({p.implied_probability for p in p_market.values()}) > 1)
    a = combine(alpha=alpha, beta=beta_one, p_fundamental=p_fundamental, p_market=p_market)
    b = combine(alpha=alpha, beta=beta_two, p_fundamental=p_fundamental, p_market=p_market)
    assert a != b


@settings(max_examples=200)
@given(inputs=_inputs(), alpha=st.floats(min_value=0.05, max_value=3.0), beta=_COEF,
       bump=st.floats(min_value=1e-6, max_value=0.04))
def test_increasing_a_fundamental_never_decreases_its_combined_probability(
    inputs: tuple[dict[int, float], dict[int, MarketInfoPrice]],
    alpha: float,
    beta: float,
    bump: float,
) -> None:
    p_fundamental, p_market = inputs
    target = min(p_fundamental)  # deterministic choice of the bumped runner
    before = combine(alpha=alpha, beta=beta, p_fundamental=p_fundamental, p_market=p_market)
    bumped = dict(p_fundamental)
    bumped[target] = p_fundamental[target] + bump
    after = combine(alpha=alpha, beta=beta, p_fundamental=bumped, p_market=p_market)
    assert after[target] >= before[target] - 1e-12


@settings(max_examples=100)
@given(inputs=_inputs(), alpha=_COEF, beta=_COEF)
def test_combiner_is_permutation_invariant_bit_exactly(
    inputs: tuple[dict[int, float], dict[int, MarketInfoPrice]], alpha: float, beta: float
) -> None:
    p_fundamental, p_market = inputs
    forward = combine(alpha=alpha, beta=beta, p_fundamental=p_fundamental, p_market=p_market)
    reversed_fund = dict(reversed(list(p_fundamental.items())))
    reversed_mkt = dict(reversed(list(p_market.items())))
    backward = combine(alpha=alpha, beta=beta, p_fundamental=reversed_fund, p_market=reversed_mkt)
    assert forward == backward
