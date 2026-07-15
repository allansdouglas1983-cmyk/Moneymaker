"""Expected value at executable prices (SPEC-050).

``EV = p·(O−1)·(1−c) − (1−p)`` per unit stake, valid ONLY for a single position in a market
(commission on the net market result makes multi-position attribution path-dependent — hence
one-runner-per-market, SPEC-054). The odds come from ``odds_exec`` (SPEC-051) — never
``p_market_info``, never ``p_close`` — and the probability is a **conservative lower bound**,
never a point estimate (SPEC-050; the type also anticipates SPEC-034's "point estimate must not
be consumable by the decision layer").

All arithmetic is exact ``Decimal``. No float, and no LLM, ever reaches this computation.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from l5_decision.prices import OddsExec


class WinProbabilityLowerBound(BaseModel):
    """A conservative LOWER BOUND of the win-probability / edge distribution (SPEC-050).

    Distinct from a bare probability or a point estimate: the decision layer consumes only this
    type, so a point estimate cannot be passed where a conservative bound is required. Producing
    a genuine lower bound from the edge distribution is L4's responsibility (SPEC-034); this is
    the consumption contract the EV function requires.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    value: Decimal

    @model_validator(mode="after")
    def _in_unit_interval(self) -> WinProbabilityLowerBound:
        if not Decimal(0) <= self.value <= Decimal(1):
            raise ValueError(f"win probability {self.value!r} must be in [0, 1]")
        return self


class CommissionRate(BaseModel):
    """Exchange commission rate in [0, 1) — charged on the net market result (SPEC-080)."""

    model_config = ConfigDict(frozen=True, strict=True)

    rate: Decimal

    @model_validator(mode="after")
    def _in_range(self) -> CommissionRate:
        if not Decimal(0) <= self.rate < Decimal(1):
            raise ValueError(f"commission rate {self.rate!r} must be in [0, 1)")
        return self


def expected_value(
    win_probability: WinProbabilityLowerBound,
    odds_exec: OddsExec,
    commission: CommissionRate,
) -> Decimal:
    """EV per unit stake for a single back position (SPEC-050).

    The parameter types already prevent conflation statically; the runtime ``isinstance`` guards
    below make the same guarantee for dynamically-typed call sites — a ``p_close`` or
    ``p_market_info`` handed in as the odds, or a bare probability as the win probability, raises
    ``TypeError`` rather than silently pricing a bet on the wrong quantity.
    """
    if not isinstance(win_probability, WinProbabilityLowerBound):
        raise TypeError(
            "win_probability must be a WinProbabilityLowerBound (a conservative lower bound), "
            f"not {type(win_probability).__name__}"
        )
    if not isinstance(odds_exec, OddsExec):
        raise TypeError(
            f"odds must be odds_exec (OddsExec), not {type(odds_exec).__name__}; "
            "p_market_info and p_close must never reach EV"
        )
    if not isinstance(commission, CommissionRate):
        raise TypeError(f"commission must be a CommissionRate, not {type(commission).__name__}")

    p = win_probability.value
    o = odds_exec.decimal_odds
    c = commission.rate
    return p * (o - Decimal(1)) * (Decimal(1) - c) - (Decimal(1) - p)
