"""A4 (audit F-05, founder order): adapter-owned cluster identity + explicit chronology.

Two SEPARATE semantics, never conflated (founder directive):

* ``ClusterId`` — opaque, hashable dependence-group identity (which decision units share
  conditions and must resample together). Deliberately UNORDERABLE: sorting ClusterIds
  raises, so lexicographic ordering of opaque ids can never silently become chronology.
* ``ChronologyKey`` — the explicit ordered value time-respecting folds compare (which
  cluster is strictly earlier). Total order over an explicit integer ordinal.

The adapter supplies both via ``ClusterAssignment``; generic fold code consumes
``chronology`` for strictly-before discipline and ``cluster_id`` for grouping;
resampling (SPEC-090) consumes identity only. The divergence tests pin a corpus where
identity's lexicographic order CONTRADICTS chronology — folds must follow chronology.
"""
from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from sport_core.clustering import (
    ChronologyKey,
    ClusterAssignment,
    ClusterId,
    calendar_day_assignment,
)

pytestmark = pytest.mark.spec("SPEC-031")


class TestClusterIdIsOpaqueIdentity:
    def test_hashable_and_frozen(self) -> None:
        a, b = ClusterId("x:1"), ClusterId("x:1")
        assert a == b and hash(a) == hash(b)
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.value = "y"  # type: ignore[misc]

    def test_non_empty(self) -> None:
        with pytest.raises(ValueError):
            ClusterId("")
        with pytest.raises(ValueError):
            ClusterId("   ")

    def test_deliberately_unorderable(self) -> None:
        # Lexicographic ordering of opaque cluster ids must never stand in for
        # chronology — sorting them is refused by the type itself.
        with pytest.raises(TypeError):
            _ = ClusterId("a") < ClusterId("b")  # type: ignore[operator]
        with pytest.raises(TypeError):
            sorted([ClusterId("b"), ClusterId("a")])  # type: ignore[type-var]


class TestChronologyKeyIsExplicitOrder:
    def test_total_order_on_ordinal(self) -> None:
        early, late = ChronologyKey(ordinal=100), ChronologyKey(ordinal=200)
        assert early < late and late > early and early == ChronologyKey(ordinal=100)

    def test_from_date_is_exact_and_monotone(self) -> None:
        d1, d2 = date(2026, 1, 31), date(2026, 2, 1)
        assert ChronologyKey.from_date(d1) < ChronologyKey.from_date(d2)
        assert ChronologyKey.from_date(d1).ordinal == d1.toordinal()


class TestClusterAssignment:
    def test_carries_both_semantics(self) -> None:
        assignment = ClusterAssignment(
            cluster_id=ClusterId("tennis:day:2026-07-17"),
            chronology=ChronologyKey.from_date(date(2026, 7, 17)),
        )
        assert assignment.cluster_id.value == "tennis:day:2026-07-17"
        assert assignment.chronology.ordinal == date(2026, 7, 17).toordinal()

    def test_calendar_day_assignment_is_namespaced_and_deterministic(self) -> None:
        racing = calendar_day_assignment("horse_racing", date(2026, 1, 5))
        tennis = calendar_day_assignment("tennis", date(2026, 1, 5))
        assert racing.cluster_id != tennis.cluster_id  # same day, different sports
        assert racing.chronology == tennis.chronology  # same chronology is legitimate
        assert racing == calendar_day_assignment("horse_racing", date(2026, 1, 5))
        with pytest.raises(ValueError):
            calendar_day_assignment("", date(2026, 1, 5))


class TestIdentityAndChronologyCanDiverge:
    def test_lexicographic_id_order_contradicting_chronology_is_representable(self) -> None:
        # Founder-required divergence pin: id "b-january" sorts lexicographically AFTER
        # "a-february", but is chronologically EARLIER. Both must be representable, and
        # any consumer ordering by id-string would get this wrong — which is why
        # ClusterId is unorderable and folds consume ChronologyKey.
        january = ClusterAssignment(
            cluster_id=ClusterId("b-january"),
            chronology=ChronologyKey.from_date(date(2026, 1, 10)),
        )
        february = ClusterAssignment(
            cluster_id=ClusterId("a-february"),
            chronology=ChronologyKey.from_date(date(2026, 2, 10)),
        )
        assert january.cluster_id.value > february.cluster_id.value  # lexicographic lies
        assert january.chronology < february.chronology  # chronology tells the truth
