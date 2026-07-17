"""Tennis domain contracts (ADR 0017 S4; docs/architecture/sport-agnostic-audit.md slice S4).

Immutable, versioned CONTRACTS only. No algorithms, no probability estimation, no
fabricated data. Every type is a frozen dataclass; every enum is closed (no open
string fields standing in for a classification). Money/no-float discipline
(CLAUDE.md "Types") applies: no field here is a float; stakes/odds/reduction
factors are not modelled in this module at all — they are referenced from the
existing ``l7_settle.outcomes`` contracts, never duplicated (ADR 0017 audit finding
"choice-set + outcome mapping").

Retirement/walkover/qualification status FIELDS are declared here because they are
part of what a Match *is* (structural facts about how it ended), not because this
module implements tennis settlement POLICY. The settlement RULES that consume these
statuses (void semantics, partial-completion handling) are SPEC-084 (``l7_settle``,
``planned``, ADR 0017 S7) and are explicitly NOT implemented in this slice — see
``docs/decisions/0016-tennis-pivot-proposal.md`` §4.2 and
``docs/architecture/sport-agnostic-audit.md`` slice S7.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from l7_settle.outcomes import MarketOutcome, MatchedPosition

SCHEMA_VERSION = "tennis-domain-v1"

__all__ = [
    "SCHEMA_VERSION",
    "Surface",
    "Round",
    "BestOf",
    "RetirementStatus",
    "WalkoverStatus",
    "QualificationStatus",
    "TournamentLevel",
    "Player",
    "Tournament",
    "Match",
    "MarketSelection",
    "MarketSnapshot",
    "SettlementOutcome",
    "ExecutionOutcome",
]


class Surface(Enum):
    """Closed set of tennis court surfaces. No open string field stands in for this."""

    HARD = "HARD"
    CLAY = "CLAY"
    GRASS = "GRASS"
    CARPET_INDOOR = "CARPET_INDOOR"


class Round(Enum):
    """Closed set of tournament rounds, qualifying through final.

    Draw-size-to-round validity (e.g. a 32-draw never reaching R128) is NOT modelled
    here — that is a tournament-format fact, not a domain-contract invariant, and
    inventing a validity table beyond the named contracts is out of scope for this
    slice.
    """

    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    R128 = "R128"
    R64 = "R64"
    R32 = "R32"
    R16 = "R16"
    QF = "QF"
    SF = "SF"
    F = "F"
    RR = "RR"


class BestOf(Enum):
    """Closed set of match formats. Value is the 'best of' N — the maximum number of
    sets playable (winning requires a majority: 2 of 3, or 3 of 5)."""

    THREE = 3
    FIVE = 5


class RetirementStatus(Enum):
    """Closed set. Settlement CONSEQUENCES of a retirement are SPEC-084 (planned), not here."""

    NONE = "NONE"
    RETIRED_BEFORE_SET1_COMPLETE = "RETIRED_BEFORE_SET1_COMPLETE"
    RETIRED_AFTER_SET1_COMPLETE = "RETIRED_AFTER_SET1_COMPLETE"


class WalkoverStatus(Enum):
    """Closed set. Settlement CONSEQUENCES of a walkover are SPEC-084 (planned), not here."""

    NONE = "NONE"
    WALKOVER = "WALKOVER"


class QualificationStatus(Enum):
    """Closed set describing how a player entered the main draw."""

    MAIN_DRAW = "MAIN_DRAW"
    QUALIFIER = "QUALIFIER"
    LUCKY_LOSER = "LUCKY_LOSER"
    WILD_CARD = "WILD_CARD"


class TournamentLevel(Enum):
    """Closed set of tournament tiers. No invented tiers beyond the named set."""

    ATP_250 = "ATP_250"
    ATP_500 = "ATP_500"
    ATP_1000 = "ATP_1000"
    GRAND_SLAM = "GRAND_SLAM"
    WTA_250 = "WTA_250"
    WTA_500 = "WTA_500"
    WTA_1000 = "WTA_1000"
    CHALLENGER = "CHALLENGER"
    OTHER = "OTHER"


@dataclass(frozen=True)
class Player:
    """A tennis player identity. NO invented stats/rating fields — those are future
    feature-registry (S6) concerns, never domain-contract fields.
    """

    player_id: str
    name: str | None = None

    def __post_init__(self) -> None:
        if not self.player_id or not self.player_id.strip():
            raise ValueError("player_id must be non-empty")


@dataclass(frozen=True)
class Tournament:
    """A tennis tournament. ``best_of_default`` is the tournament's default match
    format policy (e.g. best-of-5 for men's Grand Slam main draw); an individual
    :class:`Match` still declares its own authoritative ``best_of``.
    """

    tournament_id: str
    name: str
    surface: Surface
    best_of_default: BestOf
    level: TournamentLevel

    def __post_init__(self) -> None:
        if not self.tournament_id or not self.tournament_id.strip():
            raise ValueError("tournament_id must be non-empty")
        if not self.name or not self.name.strip():
            raise ValueError("name must be non-empty")


@dataclass(frozen=True)
class Match:
    """One tennis match: the decision unit for this sport (ADR 0017 correction 0003;
    ``sport_tennis``'s :class:`~sport_tennis.adapter.TENNIS_ADAPTER` declares
    ``decision_unit="match"``).

    ``scheduled_start_utc`` carries the dual-clock discipline (CLAUDE.md "Types"):
    every timestamped record carries UTC wall clock alongside a monotonic reading
    of when that schedule fact was captured, because wall clock can jump under NTP
    adjustment (SPEC-004's principle, applied here to a domain record rather than a
    raw capture record). Only the SCHEDULED start is representable — actual start is
    not knowable live and is out of scope for this contract (SPEC-022 principle).

    ``retirement_status`` / ``walkover_status`` are mutually exclusive: a match
    cannot be simultaneously a walkover (never started) and a mid-match retirement.
    ``completed`` means completed in the ordinary sense — the same sense as
    SPEC-084's COMPLETED outcome, which is mutually exclusive with retirement and
    walkover — so ``completed=True`` with a non-NONE retirement or walkover status
    is a contradiction and is refused at construction.
    """

    match_id: str
    tournament: Tournament
    round: Round
    best_of: BestOf
    player_a: Player
    player_b: Player
    scheduled_start_utc: datetime
    scheduled_start_captured_monotonic_ns: int
    qualification_status_a: QualificationStatus
    qualification_status_b: QualificationStatus
    retirement_status: RetirementStatus = RetirementStatus.NONE
    walkover_status: WalkoverStatus = WalkoverStatus.NONE
    completed: bool = False

    def __post_init__(self) -> None:
        if not self.match_id or not self.match_id.strip():
            raise ValueError("match_id must be non-empty")
        if self.player_a.player_id == self.player_b.player_id:
            raise ValueError(
                f"player_a and player_b must be distinct, both got "
                f"{self.player_a.player_id!r}: a match is exactly one mutually "
                "exclusive two-outcome choice set"
            )
        if self.scheduled_start_utc.tzinfo is None:
            raise ValueError("scheduled_start_utc must be timezone-aware")
        if self.scheduled_start_utc.utcoffset() != timezone.utc.utcoffset(None):
            raise ValueError("scheduled_start_utc must be in UTC")
        if self.walkover_status is WalkoverStatus.WALKOVER and (
            self.retirement_status is not RetirementStatus.NONE
        ):
            raise ValueError(
                "a match cannot be both a walkover (never started) and a "
                "retirement (started then ended early)"
            )
        if self.completed and (
            self.retirement_status is not RetirementStatus.NONE
            or self.walkover_status is not WalkoverStatus.NONE
        ):
            raise ValueError(
                "completed=True contradicts a retirement or walkover status: completed "
                "means completed in the ordinary sense (SPEC-084's COMPLETED outcome), "
                "which is mutually exclusive with retirement and walkover"
            )


@dataclass(frozen=True)
class MarketSelection:
    """Maps a Betfair Match Odds selection to a tennis player. Thin reference only —
    no price/size data (that is ``l1_reduce``/``price_contracts``, never duplicated here).
    """

    selection_id: int
    player: Player

    def __post_init__(self) -> None:
        if self.selection_id <= 0:
            raise ValueError(f"selection_id must be positive, got {self.selection_id}")


@dataclass(frozen=True)
class MarketSnapshot:
    """Thin reference tying a :class:`Match` to its Betfair Match Odds market and the
    two selection<->player mappings. Carries NO market data (no prices, no sizes,
    no order book) — that already exists in ``l1_reduce``/``price_contracts`` and is
    never duplicated here.
    """

    match: Match
    market_id: str
    selection_a: MarketSelection
    selection_b: MarketSelection

    def __post_init__(self) -> None:
        if not self.market_id or not self.market_id.strip():
            raise ValueError("market_id must be non-empty")
        if self.selection_a.selection_id == self.selection_b.selection_id:
            raise ValueError("selection_a and selection_b must have distinct selection_id")
        match_players = {self.match.player_a.player_id, self.match.player_b.player_id}
        selection_players = {
            self.selection_a.player.player_id,
            self.selection_b.player.player_id,
        }
        if match_players != selection_players:
            raise ValueError(
                "selection_a/selection_b must map exactly onto match.player_a/player_b "
                f"(match players {sorted(match_players)}, selection players "
                f"{sorted(selection_players)})"
            )


@dataclass(frozen=True)
class SettlementOutcome:
    """Thin reference from a :class:`Match` to the existing sport-agnostic settlement
    outcome contract (:class:`l7_settle.outcomes.MarketOutcome`). This type invents NO
    new settlement semantics: tennis settlement POLICY (retirement/walkover/void
    handling) is SPEC-084 (``l7_settle``, ``planned``) and lands in ADR 0017 S7, not
    here. This contract only lets an evidence/analytics consumer associate a Match
    with an (eventually SPEC-084-produced) outcome without duplicating the outcome
    schema.
    """

    match: Match
    outcome: MarketOutcome


@dataclass(frozen=True)
class ExecutionOutcome:
    """Thin reference from a :class:`Match` to the existing sport-agnostic executed
    position contract (:class:`l7_settle.outcomes.MatchedPosition`). No stake/odds
    fields are re-declared here — they exist exactly once, in ``l7_settle.outcomes``.
    """

    match: Match
    position: MatchedPosition
