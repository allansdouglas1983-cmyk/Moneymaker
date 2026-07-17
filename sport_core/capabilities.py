"""Sport capability matrix (ADR 0017 S1, founder-directed design).

The Core's philosophical boundary is "any mutually exclusive Betfair market". The Core
therefore never asks *which sport* it is running — it asks what the sport's markets
support. Each :class:`~sport_core.adapter.SportAdapter` declares one immutable
:class:`SportCapabilities`; core code branches on ``capabilities.supports_*``, never on
sport identity (a structural test enforces the absence of ``if sport == ...``).

Every field is a REQUIRED boolean with no default: an adapter must state every
capability explicitly. Silence is not a capability statement — an undeclared
capability would be exactly the silent assumption this matrix exists to eliminate.

``supports_in_play`` describes the SPORT'S MARKET STRUCTURE (whether Betfair turns
these markets in-play), not a permission: the platform's hard prohibition on in-play
trading (CLAUDE.md) stands for every sport regardless of this flag. It exists so core
code can reason about suspension/turn-in-play semantics in the DATA.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SportCapabilities:
    """What one sport's Betfair markets structurally support.

    Coherence rules (refusals, not warnings):

    * a sport must support at least one market arity (multi-runner or binary);
    * reduction factors exist only where a selection can be REMOVED from a live
      multi-runner book (racing's non-runner mechanism) — declaring them without
      multi-runner support is a contradiction;
    * dead heats are a multi-runner tie-settlement mechanism — same constraint;
    * ``supports_pre_match_only`` (markets never turn in-play) contradicts
      ``supports_in_play``.
    """

    supports_multi_runner: bool
    supports_binary: bool
    supports_bsp: bool
    supports_dead_heat: bool
    supports_reduction_factor: bool
    supports_retirements: bool
    supports_draw: bool
    supports_partial_settlement: bool
    supports_void_rules: bool
    supports_in_play: bool
    supports_pre_match_only: bool

    def __post_init__(self) -> None:
        if not (self.supports_multi_runner or self.supports_binary):
            raise ValueError(
                "a sport must support at least one market arity "
                "(supports_multi_runner or supports_binary)"
            )
        if self.supports_reduction_factor and not self.supports_multi_runner:
            raise ValueError(
                "supports_reduction_factor requires supports_multi_runner: reduction "
                "factors only exist where a selection can be removed from a "
                "multi-runner book"
            )
        if self.supports_dead_heat and not self.supports_multi_runner:
            raise ValueError(
                "supports_dead_heat requires supports_multi_runner: dead heats are a "
                "multi-runner tie-settlement mechanism"
            )
        if self.supports_pre_match_only and self.supports_in_play:
            raise ValueError(
                "supports_pre_match_only contradicts supports_in_play: markets cannot "
                "both never and sometimes turn in-play"
            )
