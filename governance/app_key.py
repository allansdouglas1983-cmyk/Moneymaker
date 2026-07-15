"""SPEC-102: real-money placement is impossible on a Delayed App Key.

The Delayed App Key is for authentication, schemas, connection handling, integration tests and
non-economic plumbing only (SPECIFICATION.md §13, Phase 3). Real-money placement requires a
``RealMoneyPlacementAuthorization``, whose sole field is a ``LiveAppKey`` — so `mypy --strict`
rejects building one from a delayed key, and the single runtime factory refuses a delayed key.
Impossible by construction, not by policy.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LiveAppKey:
    """The Live App Key — the only key that can authorise real-money placement."""

    key_id: str


@dataclass(frozen=True)
class DelayedAppKey:
    """The Delayed App Key — plumbing/integration only; never real money."""

    key_id: str


AppKey = LiveAppKey | DelayedAppKey


class DelayedKeyRealMoneyError(Exception):
    """Raised on any attempt to authorise real-money placement with a Delayed App Key."""


@dataclass(frozen=True)
class RealMoneyPlacementAuthorization:
    """Proof that real-money placement is permitted; constructable only from a ``LiveAppKey``."""

    live_key: LiveAppKey

    def __post_init__(self) -> None:
        # Runtime backstop for the type barrier: no non-live key can inhabit this proof, even by
        # direct construction or dataclasses.replace — the SPEC-102 guarantee then does not rest
        # solely on the CI mypy step (defence in depth).
        if not isinstance(self.live_key, LiveAppKey):
            raise DelayedKeyRealMoneyError(
                "RealMoneyPlacementAuthorization requires a LiveAppKey — real-money placement is "
                "impossible on any other key"
            )

    @property
    def live_key_id(self) -> str:
        return self.live_key.key_id


def authorize_real_money_placement(key: AppKey) -> RealMoneyPlacementAuthorization:
    """Return a real-money placement authorisation, or raise for a Delayed App Key."""
    if isinstance(key, DelayedAppKey):
        raise DelayedKeyRealMoneyError(
            f"real-money placement is impossible on a Delayed App Key ({key.key_id})"
        )
    return RealMoneyPlacementAuthorization(live_key=key)
