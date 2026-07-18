"""Stage 2C §8 — SPEC-032 combination REGISTRATION binding tests (NO fitting).

Binds specs/programme/spec032-combination-registration-v1.yaml to the frozen SPEC-032
combiner (l4_pricing.stage_two.combine) WITHOUT fitting alpha or beta. Fitting happens later
on the pre-June market-development block; here we only assert that the registered FORM, input
type-separation, determinism and metamorphic properties hold on synthetic inputs, and that the
registration file pins its frozen fields. No June data, no odds, no outcome fitting.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from l4_pricing.stage_two import combine
from l4_pricing.races import RaceValidationError
from l5_decision.prices import MarketInfoPrice

pytestmark = pytest.mark.spec("SPEC-032")

REGISTRATION = Path("specs/programme/spec032-combination-registration-v1.yaml")


def _mkt(p: str) -> MarketInfoPrice:
    return MarketInfoPrice(implied_probability=Decimal(p))


class TestRegistrationDocument:
    def test_registration_pins_frozen_fields(self) -> None:
        reg = yaml.safe_load(REGISTRATION.read_text())
        assert reg["spec_id"] == "SPEC-032"
        assert reg["registration_id"] == "SPEC-032-COMBINATION-v1"
        # NOT fitted yet — the whole point of preparing the registration.
        assert "NOT FITTED" in reg["status"]
        # exactly two scalars, no formula contest.
        assert "no formula contest" in reg["form"]["frozen"].lower()
        forbidden = reg["inputs"]["forbidden_inputs"].lower()
        for banned in ("odds", "p_close", "june"):
            assert banned in forbidden
        # p_fundamental is the affine-calibrated F2, not raw Elo.
        assert "affine-calibrated" in reg["inputs"]["p_fundamental"]
        # final alpha/beta must be frozen before June.
        assert reg["freezing"]["no_june_in_fit"]


class TestRegisteredForm:
    """combine() = softmax(alpha·ln p_fund + beta·ln p_market) — exercised, not fitted."""

    def test_probabilities_sum_to_one(self) -> None:
        c = combine(alpha=1.0, beta=1.0,
                    p_fundamental={1: 0.6, 2: 0.4},
                    p_market={1: _mkt("0.55"), 2: _mkt("0.45")})
        assert abs(sum(c.values()) - 1.0) < 1e-12

    def test_output_varies_with_alpha(self) -> None:
        pf = {1: 0.7, 2: 0.3}
        pm = {1: _mkt("0.5"), 2: _mkt("0.5")}
        lo = combine(alpha=0.5, beta=1.0, p_fundamental=pf, p_market=pm)
        hi = combine(alpha=2.0, beta=1.0, p_fundamental=pf, p_market=pm)
        assert lo[1] != hi[1]

    def test_output_varies_with_beta(self) -> None:
        pf = {1: 0.5, 2: 0.5}
        pm = {1: _mkt("0.7"), 2: _mkt("0.3")}
        lo = combine(alpha=1.0, beta=0.5, p_fundamental=pf, p_market=pm)
        hi = combine(alpha=1.0, beta=2.0, p_fundamental=pf, p_market=pm)
        assert lo[1] != hi[1]

    def test_monotone_in_fundamental_at_positive_alpha(self) -> None:
        pm = {1: _mkt("0.5"), 2: _mkt("0.5")}
        low = combine(alpha=1.0, beta=1.0, p_fundamental={1: 0.55, 2: 0.45}, p_market=pm)
        high = combine(alpha=1.0, beta=1.0, p_fundamental={1: 0.65, 2: 0.35}, p_market=pm)
        assert high[1] > low[1]

    def test_order_independent(self) -> None:
        a = combine(alpha=1.3, beta=0.8, p_fundamental={1: 0.6, 2: 0.4},
                    p_market={1: _mkt("0.55"), 2: _mkt("0.45")})
        b = combine(alpha=1.3, beta=0.8, p_fundamental={2: 0.4, 1: 0.6},
                    p_market={2: _mkt("0.45"), 1: _mkt("0.55")})
        assert a == b


class TestTypeSeparation:
    """SPEC-051 extends upstream: a bare float (or p_close) cannot type in as the market."""

    def test_bare_float_market_refused(self) -> None:
        with pytest.raises(RaceValidationError):
            combine(alpha=1.0, beta=1.0, p_fundamental={1: 0.6, 2: 0.4},
                    p_market={1: 0.55, 2: 0.45})  # type: ignore[dict-item]

    def test_out_of_range_fundamental_refused(self) -> None:
        with pytest.raises(RaceValidationError):
            combine(alpha=1.0, beta=1.0, p_fundamental={1: 1.0, 2: 0.0},
                    p_market={1: _mkt("0.5"), 2: _mkt("0.5")})
