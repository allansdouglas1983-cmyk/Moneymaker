"""ADR 0017 S5 — uncertainty-bearing model interfaces (Phases 4-5): CONTRACTS ONLY.

These three seams live in the PRICING layer, not ``sport_core``, deliberately: each
returns SPEC-034's :class:`~l4_pricing.distribution.WinProbabilityDistribution`, whose
sole sanctioned exit is the decision-layer typed lower bound
(``l5_decision.ev.WinProbabilityLowerBound``) — the type reaches ``l5_decision`` by
construction. ``sport_core`` sits on the ADR 0013 read-only analytics boundary
(tests/unit/governance/test_analytics_import_boundary.py) and must never reach
``l5_decision``, directly or transitively. A seam that returns an edge/uncertainty
distribution is a pricing-layer contract feeding the decision layer, never part of the
read-only analytics surface (analytics consumers see SPEC-037's snapshot-level
uncertainty summary instead, which is a separate representation).

Everything else about these contracts matches :mod:`sport_core.interfaces` (the
sport-agnostic seam module this file splits from): every class is a
``@runtime_checkable`` ``typing.Protocol`` with docstring+``...`` bodies only, no
implementation, no numeric literal, no estimate. The binding invariants — determinism,
no LLM may implement or back any seam (CLAUDE.md rule 3), mandatory versioned identity,
knowledge-time discipline on all inputs — are restated on each protocol below.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Protocol, runtime_checkable

from l4_pricing.distribution import WinProbabilityDistribution
from l4_pricing.races import Race

__all__ = [
    "UncertaintyProvider",
    "BayesianModel",
    "EnsembleModel",
]


@runtime_checkable
class UncertaintyProvider(Protocol):
    """Produces a SPEC-034 ``WinProbabilityDistribution`` per active runner — an ensemble,
    never a point estimate. The only sanctioned exit downstream remains
    ``WinProbabilityDistribution.conservative_lower_bound``; this seam is not itself that
    exit and must not be treated as one.

    Deterministic given a declared, versioned resampling/ensembling procedure (a random
    seed, if the concrete implementation uses one, is part of that procedure's declared,
    versioned identity — never an undeclared source of nondeterminism). No LLM may
    implement or back this seam. Versioned identity mandatory via ``model_id``/
    ``model_version``. Knowledge-time discipline inherited from ``race``'s already-guarded
    features.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def distribution(
        self, race: Race, *, as_of: datetime
    ) -> Mapping[int, WinProbabilityDistribution]: ...


@runtime_checkable
class BayesianModel(Protocol):
    """Future marker: a Bayesian probability model whose posterior is itself the SPEC-034
    ensemble (no separate point estimate exists to leak into the decision layer).
    Deterministic given its declared prior and likelihood specification. No LLM may
    implement or back this model. Versioned identity mandatory via ``model_id``/
    ``model_version``. Knowledge-time discipline inherited from ``race``'s already-guarded
    features. Design of the prior/likelihood is explicitly future work — this marker fixes
    only the seam, not the statistical design.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def posterior_samples(
        self, race: Race, *, as_of: datetime
    ) -> Mapping[int, WinProbabilityDistribution]: ...


@runtime_checkable
class EnsembleModel(Protocol):
    """Future marker: an ensemble over other named model contracts. ``member_model_ids``
    is the ensemble's own declared, versioned membership list — an ensemble whose
    membership is not enumerable is not a versioned artefact and does not satisfy this
    contract. Deterministic given that declared membership and combination rule. No LLM
    may implement or back this model. Versioned identity mandatory via ``model_id``/
    ``model_version`` for the ensemble itself, in addition to each member's own identity.
    Knowledge-time discipline inherited from ``race``'s already-guarded features. Design of
    the combination rule is explicitly future work — this marker fixes only the seam.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    @property
    def member_model_ids(self) -> tuple[str, ...]: ...

    def posterior_samples(
        self, race: Race, *, as_of: datetime
    ) -> Mapping[int, WinProbabilityDistribution]: ...
