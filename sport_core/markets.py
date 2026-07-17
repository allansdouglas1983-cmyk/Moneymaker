"""SPEC-095 support / ADR 0017 S8: market-kind abstraction.

Phase 9 of ADR 0017 asks for the MARKET abstraction only: an enum naming the kinds of
Betfair market this platform's sport adapters can in principle describe, plus a frozen
POLICY declaring which of those kinds are actually enabled for research right now. This
module contains **no algorithms and no benchmark selection** — it is the enums/interface
half of S8 (the benchmark half is ``sport_core.benchmarks``).

Why only WIN and MATCH_ODDS are enabled in v1
----------------------------------------------
``docs/architecture/sport-agnostic-audit.md`` (ADR 0017 Phase-1 audit) frames Betfair
markets as "one mutually exclusive choice set whose outcome probabilities sum to 1" —
that is sport-neutral. Racing's WIN market and pre-match tennis's MATCH_ODDS market are
both instances of it and are the only markets this platform has evidence-gated pricing
and settlement machinery for today (``l4_pricing``, ``l7_settle``). Every other kind named
here is a **declared-but-refused** future market: naming it lets the rest of the platform
(feature registries, settlement contracts, docs) refer to it without inventing new
vocabulary later, while ``MarketKindPolicy`` keeps it structurally unreachable until a
human enables it.

``GAME_MARKETS`` is named for completeness even though the founder's tennis data-sourcing
research (DR-TENNIS-BENCHMARK-001 in ``docs/research/`` — see ``sport_core.benchmarks``
for the fuller citation) found that Betfair's purchasable historical tennis data
**excludes Game markets entirely**. There is consequently no near-term data path to
enabling it even after WIN/MATCH_ODDS pilots conclude; it stays in the closed set only so
a future sport/market that does have Game-market-shaped data does not need a new enum
member, and so the refusal is explicit rather than the market simply not existing.

Enabling any additional kind is a GOVERNED change: it means editing the
``ENABLED_MARKET_KINDS`` constant (never a runtime flag, config file, or environment
variable) and updating this module's pinned tests in the same reviewed slice — exactly
the discipline SPEC-060/094 already use for pre-registered numeric constants. No code
path in this module can enable a kind at runtime.

Founder design check (conceptual, not new enum members)
---------------------------------------------------------
A 3-way football market (home / draw / away) and a binary financial "will X happen"
market are both expressible without adding members:

* football's 3-outcome match result is a ``MATCH_ODDS`` kind — "match odds" already
  means "the market pricing the match's outcome set", and a mutually-exclusive
  three-element choice set is exactly the ``Race``/choice-set abstraction the audit
  found sport-neutral (draws are just a third selection, same as any other runner);
* a binary financial market (two mutually exclusive outcomes, no intermediate sport
  event) is an ``OTHER`` kind until/unless a dedicated member is warranted — ``OTHER``
  exists precisely so a structurally-valid mutually-exclusive market never has to wait
  on an enum change merely to be named, though it remains DISABLED under the v1 policy
  like every kind except WIN/MATCH_ODDS.

No probability, pricing, or benchmark logic lives here. This module is enums and a
frozen policy only.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique

__all__ = [
    "MarketKind",
    "MarketKindDisabledError",
    "MarketKindPolicy",
    "ENABLED_MARKET_KINDS",
    "V1_MARKET_KIND_POLICY",
]


@unique
class MarketKind(Enum):
    """The closed set of Betfair market kinds this platform can name.

    Membership is closed deliberately: adding a member is itself a governed
    specification change (it changes what ``MarketKindPolicy`` can even describe),
    not something a worker or a runtime value should be able to do.
    """

    MATCH_ODDS = "MATCH_ODDS"
    WIN = "WIN"
    SET_WINNER = "SET_WINNER"
    CORRECT_SCORE = "CORRECT_SCORE"
    GAME_MARKETS = "GAME_MARKETS"
    OTHER = "OTHER"


class MarketKindDisabledError(ValueError):
    """Raised by :meth:`MarketKindPolicy.require_enabled` for any kind not in the
    enabled set. Declared-but-refused is the intended, permanent behaviour for a
    disabled kind until a human governs it enabled — this is not a bug to silence."""


@dataclass(frozen=True)
class MarketKindPolicy:
    """A frozen declaration of exactly which :class:`MarketKind` values are enabled
    for research right now. There is no mutation API and no constructor path that
    takes a runtime value (config, env var, request parameter) to decide enablement —
    the only way to change what is enabled is to edit the constant below and land it
    as its own reviewed slice.
    """

    enabled_kinds: frozenset[MarketKind]

    def is_enabled(self, kind: MarketKind) -> bool:
        return kind in self.enabled_kinds

    def require_enabled(self, kind: MarketKind) -> None:
        """Raise :class:`MarketKindDisabledError` unless ``kind`` is enabled.

        SET_WINNER, CORRECT_SCORE and GAME_MARKETS are declared-but-refused in v1:
        naming them does not enable them. Enabling any of them requires a governed
        constant edit plus updated tests, never a runtime toggle.
        """
        if not self.is_enabled(kind):
            raise MarketKindDisabledError(
                f"{kind.name} is declared but not enabled for research "
                f"(enabled kinds: {sorted(k.name for k in self.enabled_kinds)}). "
                "Enabling a new market kind is a governed change: edit "
                "ENABLED_MARKET_KINDS/V1_MARKET_KIND_POLICY and its pinned tests in "
                "their own reviewed slice — it is never a runtime configuration value."
            )


# v1: racing WIN + pre-match tennis MATCH_ODDS only. See module docstring for why every
# other kind stays declared-but-refused, including GAME_MARKETS (no purchasable
# historical data path per DR-TENNIS-BENCHMARK-001's sourcing research).
ENABLED_MARKET_KINDS: frozenset[MarketKind] = frozenset({MarketKind.WIN, MarketKind.MATCH_ODDS})

V1_MARKET_KIND_POLICY = MarketKindPolicy(enabled_kinds=ENABLED_MARKET_KINDS)
