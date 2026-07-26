"""Stable, namespaced, opaque competitor identity (A5; audit F-07).

A competitor's identity is an opaque STRING in mandatory ``namespace:identifier`` form
(``atp:104925``, ``wta:230234``) — never a Betfair selection integer. Selection ids are
per-market wire facts that change across markets and data sources; competitor identity
is cross-market and cross-source, and the namespace names the issuing scheme so two
sources' numbering can never collide silently.

Display names and aliases are a SEPARATE type (:class:`CompetitorDisplay`): identity
never carries presentation, an alias is never an identity, and nothing compares or
joins on names anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CompetitorId", "CompetitorDisplay"]


@dataclass(frozen=True)
class CompetitorId:
    """Opaque ``namespace:identifier`` competitor identity. Hashable, equal by value."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValueError(
                f"CompetitorId must be a namespaced string, got {type(self.value).__name__}"
            )
        namespace, sep, identifier = self.value.partition(":")
        if not sep or not namespace.strip() or not identifier.strip():
            raise ValueError(
                f"CompetitorId must be 'namespace:identifier' with both parts non-empty, "
                f"got {self.value!r}"
            )

    @property
    def namespace(self) -> str:
        return self.value.partition(":")[0]

    @property
    def identifier(self) -> str:
        return self.value.partition(":")[2]


@dataclass(frozen=True)
class CompetitorDisplay:
    """Presentation for one competitor — display name plus known aliases.

    Deliberately NOT an identity: nothing may join, compare, or key on names or
    aliases; the only identity-bearing field is the referenced :class:`CompetitorId`.
    """

    competitor_id: CompetitorId
    display_name: str
    aliases: frozenset[str]

    def __post_init__(self) -> None:
        if not self.display_name or not self.display_name.strip():
            raise ValueError("display_name must be non-empty")
