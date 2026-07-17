"""Adapter-owned cluster identity + explicit chronology (A4; audit F-05).

Two SEPARATE semantics, never conflated (founder directive, 2026-07-17):

* :class:`ClusterId` — opaque, hashable dependence-group identity: which decision units
  share conditions and must be resampled together (SPEC-090's block unit). Deliberately
  UNORDERABLE — comparing or sorting ClusterIds raises ``TypeError``, so lexicographic
  ordering of opaque ids can never silently stand in for chronology. Where deterministic
  ITERATION over clusters is needed (resampling reproducibility), consumers sort by the
  explicit ``.value`` string and must document that as a determinism device, never as
  time order.
* :class:`ChronologyKey` — the explicit ordered value time-respecting folds compare
  (SPEC-031's strictly-before discipline): an integer ordinal with a total order. The
  adapter derives it deterministically (racing meeting day / tennis UTC calendar day:
  ``date.toordinal()``); a sport whose chronology is not calendar-shaped supplies its
  own ordinal derivation.

:class:`ClusterAssignment` carries both. Generic fold code consumes ``chronology`` for
ordering and ``cluster_id`` for grouping; resampling consumes ``cluster_id`` ONLY.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

__all__ = [
    "ClusterId",
    "ChronologyKey",
    "ClusterAssignment",
    "calendar_day_assignment",
]


@dataclass(frozen=True)
class ClusterId:
    """Opaque dependence-group identity. Hashable, equal by value, NOT ordered."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("ClusterId must be non-empty")


@dataclass(frozen=True, order=True)
class ChronologyKey:
    """Explicit total order for time-respecting folds. An integer ordinal."""

    ordinal: int

    @classmethod
    def from_date(cls, day: date) -> ChronologyKey:
        """Exact, monotone mapping from a calendar day (racing meeting day, tennis UTC
        calendar day) to the ordinal chronology."""
        return cls(ordinal=day.toordinal())


@dataclass(frozen=True)
class ClusterAssignment:
    """One decision unit's dependence-group identity plus its chronology."""

    cluster_id: ClusterId
    chronology: ChronologyKey


def calendar_day_assignment(sport_id: str, day: date) -> ClusterAssignment:
    """The calendar-day instantiation both current sports use (racing: meeting day;
    tennis: UTC calendar day). Namespaced by sport so the same day in two sports is two
    DIFFERENT dependence groups sharing one chronology — which is legitimate."""
    if not sport_id or not sport_id.strip():
        raise ValueError("sport_id must be non-empty")
    return ClusterAssignment(
        cluster_id=ClusterId(f"{sport_id}:day:{day.isoformat()}"),
        chronology=ChronologyKey.from_date(day),
    )
