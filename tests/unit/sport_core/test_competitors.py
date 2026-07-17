"""A5 (audit F-07, founder order): stable namespaced opaque competitor identity.

``CompetitorId`` is an opaque STRING identity in mandatory ``namespace:identifier`` form
(e.g. ``atp:104925``) — never a Betfair selection integer (selection ids are per-market
wire facts; competitor identity is cross-market and cross-source). Display names and
aliases are a SEPARATE type: identity never carries presentation, and no alias is ever
an identity.
"""
from __future__ import annotations

import dataclasses

import pytest

from sport_core.competitors import CompetitorDisplay, CompetitorId

pytestmark = pytest.mark.spec("SPEC-034")


class TestCompetitorId:
    def test_namespaced_form_required(self) -> None:
        cid = CompetitorId("atp:104925")
        assert cid.namespace == "atp"
        assert cid.identifier == "104925"
        for bad in ("", "104925", "atp:", ":104925", "  ", "atp: "):
            with pytest.raises(ValueError):
                CompetitorId(bad)

    def test_hashable_frozen_value_equality(self) -> None:
        a, b = CompetitorId("wta:230234"), CompetitorId("wta:230234")
        assert a == b and hash(a) == hash(b)
        assert a != CompetitorId("atp:230234")  # namespace is identity-bearing
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.value = "x:y"  # type: ignore[misc]

    def test_not_an_integer_and_not_selection_shaped(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            CompetitorId(104925)  # type: ignore[arg-type]


class TestCompetitorDisplay:
    def test_display_and_aliases_are_separate_from_identity(self) -> None:
        cid = CompetitorId("atp:104925")
        display = CompetitorDisplay(
            competitor_id=cid,
            display_name="Example Player",
            aliases=frozenset({"E. Player", "Player, Example"}),
        )
        assert display.competitor_id is cid
        assert "E. Player" in display.aliases
        with pytest.raises(ValueError):
            CompetitorDisplay(competitor_id=cid, display_name="", aliases=frozenset())

    def test_an_alias_is_never_an_identity(self) -> None:
        display = CompetitorDisplay(
            competitor_id=CompetitorId("atp:104925"),
            display_name="Example Player",
            aliases=frozenset({"E. Player"}),
        )
        assert not isinstance(display, CompetitorId)
        assert not hasattr(display, "namespace")
