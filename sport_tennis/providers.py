"""Tennis-flavoured provider/model protocol seams (A5; audit F-07): CONTRACTS ONLY.

Relocated from ``sport_core/interfaces.py`` (their own docstrings there recommended it):
a serve, a surface, and player fitness have no football, racing, or binary-market
analogue, so these are SPORT-ADAPTER-LEVEL seams — exposed to the Core only through the
generic ``FeatureGenerator`` seam, never depended on by sport-agnostic callers.

Competitors are keyed by :class:`sport_core.competitors.CompetitorId` — the stable,
namespaced, opaque STRING identity — never by a Betfair selection integer (the int↔player
translation lives where it belongs, in :class:`sport_tennis.domain.MarketSelection`).

Same binding invariants as every other seam module: ``@runtime_checkable`` Protocols,
docstring+``...`` bodies only, zero numeric literals, deterministic implementations only,
no LLM may implement or back any seam (CLAUDE.md rule 3), versioned identity mandatory,
knowledge-time discipline via the mandatory ``as_of`` parameter.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from sport_core.competitors import CompetitorId

__all__ = [
    "SurfaceRatingProvider",
    "FitnessSignalProvider",
    "ServeStrengthProvider",
    "ReturnStrengthProvider",
    "SurfaceEloModel",
]


@runtime_checkable
class SurfaceRatingProvider(Protocol):
    """Sport-adapter-level: a player's surface-conditioned rating as of a decision time.

    Not a generic Core seam — concrete implementations are exposed to the Core only
    through ``FeatureGenerator``. Deterministic given the declared rating artefact. No
    LLM may implement or back this seam. Versioned identity mandatory via ``model_id``/
    ``model_version``. Knowledge-time discipline via the mandatory ``as_of`` parameter —
    a concrete implementation must not read information published after it.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def rating(
        self, competitor_id: CompetitorId, surface: str, *, as_of: datetime
    ) -> Decimal: ...


@runtime_checkable
class FitnessSignalProvider(Protocol):
    """Sport-adapter-level: a player's fitness/fatigue/injury signal as of a decision time.

    Not a generic Core seam. Deterministic given the declared signal artefact. No LLM may
    implement or back this seam. Versioned identity mandatory via ``model_id``/
    ``model_version``. Knowledge-time discipline via the mandatory ``as_of`` parameter.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def signal(self, competitor_id: CompetitorId, *, as_of: datetime) -> Decimal: ...


@runtime_checkable
class ServeStrengthProvider(Protocol):
    """Sport-adapter-level: a player's surface-conditioned serve-strength signal.

    Not a generic Core seam. Deterministic given the declared signal artefact. No LLM may
    implement or back this seam. Versioned identity mandatory via ``model_id``/
    ``model_version``. Knowledge-time discipline via the mandatory ``as_of`` parameter.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def serve_strength(
        self, competitor_id: CompetitorId, surface: str, *, as_of: datetime
    ) -> Decimal: ...


@runtime_checkable
class ReturnStrengthProvider(Protocol):
    """Sport-adapter-level: a player's surface-conditioned return-strength signal.

    Not a generic Core seam. Deterministic given the declared signal artefact. No LLM may
    implement or back this seam. Versioned identity mandatory via ``model_id``/
    ``model_version``. Knowledge-time discipline via the mandatory ``as_of`` parameter.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def return_strength(
        self, competitor_id: CompetitorId, surface: str, *, as_of: datetime
    ) -> Decimal: ...


@runtime_checkable
class SurfaceEloModel(Protocol):
    """A future surface-conditioned Elo rating system — tennis-flavoured (a surface is a
    tennis concept), relocated here with the provider seams (A5/F-07). Deterministic
    given its declared update rule and rating history. No LLM may implement or back this
    model. Versioned identity mandatory via ``model_id``/``model_version``.
    Knowledge-time discipline via the mandatory ``as_of`` parameter on every query.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def rating(
        self, competitor_id: CompetitorId, surface: str, *, as_of: datetime
    ) -> Decimal: ...
