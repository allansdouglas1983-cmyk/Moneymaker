"""SPEC-034: a DISTRIBUTION over win probability — never a point estimate (§6.4).

v1 uses the time-fold ensemble sanctioned by §6.4. The only route into the decision layer is
``conservative_lower_bound``, which returns l5's ``WinProbabilityLowerBound``; the type cannot
be truth-tested or float-coerced, and deliberately has no mean/median accessor. Samples stay
readable for l8 calibration diagnostics — the prohibition is on the DECISION layer, whose
typed entry is the enforcement point (ADR 0012 decision 7).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from l5_decision.ev import WinProbabilityLowerBound


@dataclass(frozen=True)
class WinProbabilityDistribution:
    """An ensemble of win-probability samples for one runner (sorted at construction)."""

    samples: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.samples) < 2:
            raise ValueError("a distribution needs at least two ensemble samples")
        if not all(0.0 < s < 1.0 for s in self.samples):
            raise ValueError("every sample must be in the open interval (0, 1)")
        object.__setattr__(self, "samples", tuple(sorted(self.samples)))

    def __bool__(self) -> bool:
        raise TypeError("a probability distribution is not a truth value (SPEC-034)")

    def __float__(self) -> float:
        raise TypeError(
            "a probability distribution has no point estimate; use "
            "conservative_lower_bound(quantile) (SPEC-034)"
        )

    def conservative_lower_bound(self, quantile: Decimal) -> WinProbabilityLowerBound:
        """The lower order statistic at ``quantile`` — the sole decision-layer exit.

        Index = floor(q·(n−1)): exactly deterministic, no interpolation, conservative by
        construction. The quantile itself is a pre-registered experiment parameter, never a
        constant of this module (§9.3 no borrowed thresholds).
        """
        if not Decimal(0) < quantile < Decimal(1):
            raise ValueError(f"quantile must be in the open interval (0, 1), got {quantile}")
        index = int(quantile * Decimal(len(self.samples) - 1))
        return WinProbabilityLowerBound(value=Decimal(repr(self.samples[index])))
