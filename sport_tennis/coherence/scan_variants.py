"""CROSS_MARKET_COHERENCE_DISCRETISATION_STABILITY_AMENDMENT_V1 — frozen scan-variant registry.

STAGE3-0006C-D-A3 §5. The immutable vocabulary of registered scan variants and their exact
lattice constructions, transcribed from the STAGE3-0006C-D-A2 frozen definitions (verified
reproducible against the committed SOLVER_DEGENERACY_GRID_* artifacts before implementation —
the §1.1 distinct-perturbation gate). G0 is the unchanged production axis; G1/G2 are the
founder-selected registered VALIDATION variants — they never contribute a coordinate, root or
status to any published output. G3 (NESTED_DOUBLE_DENSITY_PHASE_SHIFT) is diagnostic-only and
deliberately absent from this vocabulary: it must never be runtime-reachable.
"""
from __future__ import annotations

import enum
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from sport_tennis.coherence.solver_scan import build_scan_axis

# The G0 base resolution, frozen as part of the registered variant definitions. Pinned by test
# to equal the solver's _COARSE_N; the variant registry must not drift from production.
G0_NODE_COUNT = 13


class ScanVariant(enum.Enum):
    """Closed registered-variant vocabulary. Append-only by governed amendment."""

    G0_BASELINE = "G0_BASELINE"
    G1_REGISTERED_VALIDATION = "G1_REGISTERED_VALIDATION"
    G2_REGISTERED_VALIDATION = "G2_REGISTERED_VALIDATION"


# Execution order is registered and fixed: G0 first, then the validation variants.
REGISTERED_VARIANT_ORDER: tuple[ScanVariant, ScanVariant, ScanVariant] = (
    ScanVariant.G0_BASELINE,
    ScanVariant.G1_REGISTERED_VALIDATION,
    ScanVariant.G2_REGISTERED_VALIDATION,
)

# A2 frozen lattice-rule names (cross-market-coherence-discretisation-stability-amendment-v1).
LATTICE_RULES: dict[ScanVariant, str] = {
    ScanVariant.G0_BASELINE: "FROZEN_PRODUCTION",
    ScanVariant.G1_REGISTERED_VALIDATION: "NESTED_DOUBLE_DENSITY",
    ScanVariant.G2_REGISTERED_VALIDATION: "HALF_CELL_PHASE_SHIFT",
}

# sha256 of the committed A2 evidence artifact each definition was verified against.
A2_ARTIFACT_SHA256: dict[ScanVariant, str] = {
    ScanVariant.G0_BASELINE:
        "d475777faa77bbbd1dd5d0cfa90ccab22a44ea0639a5092922b734d06b891392",
    ScanVariant.G1_REGISTERED_VALIDATION:
        "0651629e54f46222030ab64031e356083dd49a4d7e2a4681c69a619c15d1a62a",
    ScanVariant.G2_REGISTERED_VALIDATION:
        "412473b1a48276af8a94b5b887305e83ae28fa1d908f773d97790674eaafcd8b",
}


def _g1_axis(g0: list[float]) -> list[float]:
    """NESTED_DOUBLE_DENSITY: every G0 coordinate + the exact midpoint of every adjacent pair
    (A2 §5 rule, transcribed float-exactly)."""
    out: list[float] = []
    for a, b in zip(g0, g0[1:]):
        out.extend([a, (a + b) / 2])
    out.append(g0[-1])
    return out


def _g2_axis(g0: list[float]) -> list[float]:
    """HALF_CELL_PHASE_SHIFT: boundaries retained exactly; every interior coordinate shifted by
    half its local (right-hand) G0 cell width; exact duplicates dropped deterministically
    (A2 §5 rule, transcribed float-exactly)."""
    out = [g0[0]]
    for i in range(1, len(g0) - 1):
        shifted = g0[i] + (g0[i + 1] - g0[i]) / 2
        if shifted not in out and shifted != g0[-1]:
            out.append(shifted)
    out.append(g0[-1])
    return out


def variant_axis(variant: ScanVariant, lo: float, hi: float) -> list[float]:
    """The registered scan axis for ``variant`` over the domain [lo, hi]. G0 is byte-identical
    to the production ``build_scan_axis``; G1/G2 apply the frozen A2 rules to that G0 axis."""
    g0 = build_scan_axis(lo, hi, G0_NODE_COUNT)
    if variant is ScanVariant.G0_BASELINE:
        return g0
    if variant is ScanVariant.G1_REGISTERED_VALIDATION:
        return _g1_axis(g0)
    if variant is ScanVariant.G2_REGISTERED_VALIDATION:
        return _g2_axis(g0)
    raise ValueError(f"unregistered scan variant: {variant!r}")


def axis_digest(axis: Sequence[float]) -> str:
    """Content digest of an axis: sha256 over the exact float.hex() of every coordinate."""
    return hashlib.sha256(
        "|".join(float(x).hex() for x in axis).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ScanVariantDefinition:
    """Immutable materialised variant definition: rule, provenance and the exact axis."""

    variant: ScanVariant
    lattice_rule: str
    a2_artifact_sha256: str
    axis: tuple[float, ...]
    axis_digest: str


def variant_definition(variant: ScanVariant, lo: float, hi: float) -> ScanVariantDefinition:
    axis = tuple(variant_axis(variant, lo, hi))
    return ScanVariantDefinition(
        variant=variant,
        lattice_rule=LATTICE_RULES[variant],
        a2_artifact_sha256=A2_ARTIFACT_SHA256[variant],
        axis=axis,
        axis_digest=axis_digest(axis),
    )
