"""CROSS_MARKET_COHERENCE_V1 — closed, immutable solver contracts (STAGE3-0006C Milestone A).

Replaces opaque tuples/strings in the identification solver with named, immutable, directly
testable semantics. SYNTHETIC-ONLY; reads no market prices and no outcomes. Import-quarantined
from execution/pricing/V0.

Public-contract preservation (STAGE3-0006C §3): the wired validators reproduce the solver's
existing refusal behaviour byte-for-byte (``validate_domain`` == the old ``0 < lo < hi < 1`` chain;
``validate_targets`` == the old ``0 <= t <= 1`` chain). ``SolverStatus`` values equal the existing
status strings, so the public ``IdentificationResult.status`` is unchanged. The enum additionally
REGISTERS ``INVALID_TARGET``/``INVALID_DOMAIN``/``NON_CONVERGED``/``NONFINITE_ARITHMETIC`` (target
vocabulary) but they are NOT emitted here — the current public behaviour RAISES ``CoherenceMathError``
for those conditions, and mapping raise->status is a governed contract amendment, not this refactor.
``FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD`` is retained because ``identify`` currently emits it.
"""
from __future__ import annotations

import enum
import hashlib
import json
import math
from dataclasses import dataclass

from sport_tennis.coherence.scoring import CoherenceMathError


class SolverStatus(enum.Enum):
    """Governed solver status vocabulary. Values equal the historical status strings so the public
    output contract is byte-identical. Never a raw string, never a generic SUCCESS/FAIL."""

    IDENTIFIED = "IDENTIFIED"
    NO_ROOT = "NO_ROOT"
    MULTIPLE_ROOTS = "MULTIPLE_ROOTS"
    NON_IDENTIFIABLE = "NON_IDENTIFIABLE"
    BOUNDARY_SOLUTION = "BOUNDARY_SOLUTION"
    # Emitted today (must be preserved; removing it would be contract drift):
    FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD = "FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD"
    # Registered target vocabulary — NOT emitted yet (current behaviour raises; see module docstring):
    NON_CONVERGED = "NON_CONVERGED"
    INVALID_TARGET = "INVALID_TARGET"
    INVALID_DOMAIN = "INVALID_DOMAIN"
    NONFINITE_ARITHMETIC = "NONFINITE_ARITHMETIC"


def _finite(*values: float) -> bool:
    return all(math.isfinite(v) for v in values)


@dataclass(frozen=True)
class ParameterDomain:
    """A closed rectangular parameter domain for (p_A, p_B). Immutable; explicit containment; no
    silent clamping. The identification solver uses a symmetric domain (same bounds on both axes),
    constructed via :meth:`from_symmetric`; the contract supports independent axes."""

    lower_a: float
    upper_a: float
    lower_b: float
    upper_b: float

    @classmethod
    def from_symmetric(cls, lo: float, hi: float) -> ParameterDomain:
        return cls(lower_a=lo, upper_a=hi, lower_b=lo, upper_b=hi)

    def validate(self) -> None:
        """Refuse non-finite bounds or a non-ordered axis. Does NOT itself require (0,1) bounds —
        that probability-range check is the solver's ``validate_domain`` seam."""
        if not _finite(self.lower_a, self.upper_a, self.lower_b, self.upper_b):
            raise CoherenceMathError("parameter domain bounds must be finite")
        if not (self.lower_a < self.upper_a and self.lower_b < self.upper_b):
            raise CoherenceMathError("parameter domain requires lower < upper on both axes")

    def contains(self, p_a: float, p_b: float) -> bool:
        return (self.lower_a <= p_a <= self.upper_a and self.lower_b <= p_b <= self.upper_b)

    def serialize(self) -> dict[str, float]:
        return {"lower_a": self.lower_a, "upper_a": self.upper_a,
                "lower_b": self.lower_b, "upper_b": self.upper_b}

    def digest(self) -> str:
        return _digest(self.serialize())


@dataclass(frozen=True)
class ResidualVector2:
    """The two identification residuals for one (p_A, p_B) point and one first-server assignment.
    Canonical component order: (match-odds, total-games). Finite only; immutable."""

    match_odds_residual: float
    total_games_residual: float

    def validate(self) -> None:
        if not _finite(self.match_odds_residual, self.total_games_residual):
            raise CoherenceMathError("residual components must be finite")

    def inf_norm(self) -> float:
        return max(abs(self.match_odds_residual), abs(self.total_games_residual))

    def sum_of_squares(self) -> float:
        return (self.match_odds_residual * self.match_odds_residual
                + self.total_games_residual * self.total_games_residual)

    def serialize(self) -> dict[str, float]:
        return {"match_odds_residual": self.match_odds_residual,
                "total_games_residual": self.total_games_residual}

    def digest(self) -> str:
        return _digest(self.serialize())


@dataclass(frozen=True)
class Jacobian2x2:
    """The 2x2 identification Jacobian. Rows are equations (match-odds, total-games); columns are
    parameters (p_A, p_B). Finite only; immutable."""

    d_mo_d_a: float
    d_mo_d_b: float
    d_tg_d_a: float
    d_tg_d_b: float

    def validate(self) -> None:
        if not _finite(self.d_mo_d_a, self.d_mo_d_b, self.d_tg_d_a, self.d_tg_d_b):
            raise CoherenceMathError("Jacobian entries must be finite")

    def determinant(self) -> float:
        # det = (d MO / d A)(d TG / d B) - (d MO / d B)(d TG / d A)
        return self.d_mo_d_a * self.d_tg_d_b - self.d_mo_d_b * self.d_tg_d_a

    def condition_scale(self) -> float:
        """A finite conditioning diagnostic: the max absolute entry (0 for the zero matrix). Larger
        entries relative to |det| indicate a poorly-conditioned system. Diagnostic only."""
        return max(abs(self.d_mo_d_a), abs(self.d_mo_d_b), abs(self.d_tg_d_a), abs(self.d_tg_d_b))

    def serialize(self) -> dict[str, float]:
        return {"d_mo_d_a": self.d_mo_d_a, "d_mo_d_b": self.d_mo_d_b,
                "d_tg_d_a": self.d_tg_d_a, "d_tg_d_b": self.d_tg_d_b}

    def digest(self) -> str:
        return _digest(self.serialize())


def _digest(obj: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------- pure input validators
def validate_domain(lo: float, hi: float) -> None:
    """Refuse a domain that is not strictly inside (0,1) and strictly ordered. Byte-identical to the
    solver's historical guard ``not (0.0 < lo < hi < 1.0)`` (which also refuses NaN and infinities,
    since every comparison against a non-finite value is False)."""
    if not (0.0 < lo < hi < 1.0):
        raise CoherenceMathError(f"domain must satisfy 0 < lo < hi < 1, got {(lo, hi)}")


def validate_targets(target_match_win_a: float, target_over: float) -> None:
    """Refuse targets outside [0,1]. Byte-identical to the solver's historical guard
    ``not (0.0 <= t <= 1.0 and 0.0 <= t <= 1.0)`` (also refusing NaN via False comparisons)."""
    if not (0.0 <= target_match_win_a <= 1.0 and 0.0 <= target_over <= 1.0):
        raise CoherenceMathError("targets must be probabilities in [0,1]")
