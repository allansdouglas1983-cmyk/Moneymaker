"""Tests for linking exchange markets to pyramid identities and Betfair's own grading.

The reason this path exists at all is that TE-0001 closed the Challenger/ITF thesis as
untestable — the tiers where an edge is claimed had no transactable prices in any free
source. The June ADVANCED corpus turns out to be mostly those tiers, and a Betfair market
carries its own settlement, so prices and outcomes both come from the exchange and no
results feed is needed.

What must not go wrong is identity. At ITF level there are thousands of players, surnames
repeat, and Betfair truncates first names, so a (surname, initial) key collides far more
often than it does on the main tour. Every test below is about refusing an uncertain
identity rather than resolving it optimistically: a wrong player is a wrong rating, a wrong
prediction and a wrong settlement all at once, and none of it is visible in the output.
"""
from __future__ import annotations


from tennis_edge.pyramid_link import (
    PyramidLinkOutcome,
    betfair_player_key,
    resolve_tour,
)


class TestBetfairNameKeys:
    def test_an_initial_and_surname_resolves(self) -> None:
        """Hyphens survive normalisation — and must, since both sides of the join use it."""
        assert betfair_player_key("F Auger-Aliassime") == ("auger-aliassime", "f")

    def test_a_full_first_name_resolves_to_its_initial(self) -> None:
        assert betfair_player_key("Caterina Odorizzi") == ("odorizzi", "c")

    def test_a_truncated_first_name_keeps_only_its_first_letter(self) -> None:
        """Betfair abbreviates: 'Ma van der Merwe' is one player, keyed on 'm'."""
        assert betfair_player_key("Ma van der Merwe") == ("van der merwe", "m")

    def test_a_bare_surname_is_refused(self) -> None:
        """'Carboni' could be any Carboni. No initial, no key."""
        assert betfair_player_key("Carboni") is None

    def test_a_doubles_pairing_is_refused(self) -> None:
        """Doubles markets are a different sport for our purposes and must not link."""
        assert betfair_player_key("Perez/Schuurs") is None

    def test_an_empty_name_is_refused(self) -> None:
        assert betfair_player_key("") is None
        assert betfair_player_key("   ") is None


class TestTourResolution:
    def test_a_key_known_to_one_tour_only_resolves_to_it(self) -> None:
        known = {"ATP": {("odorizzi", "c")}, "WTA": set()}
        assert resolve_tour(("odorizzi", "c"), ("odorizzi", "c"), known) == "ATP"

    def test_a_key_known_to_both_tours_is_ambiguous(self) -> None:
        """Nothing in a Betfair market definition says which tour it is."""
        both = {"ATP": {("smith", "a")}, "WTA": {("smith", "a")}}
        assert resolve_tour(("smith", "a"), ("smith", "a"), both) is None

    def test_players_from_different_tours_do_not_resolve(self) -> None:
        """A man cannot play a woman; if that is what the keys say, the keys are wrong."""
        split = {"ATP": {("a", "a")}, "WTA": {("b", "b")}}
        assert resolve_tour(("a", "a"), ("b", "b"), split) is None

    def test_an_unknown_player_does_not_resolve(self) -> None:
        known = {"ATP": {("a", "a")}, "WTA": set()}
        assert resolve_tour(("a", "a"), ("unknown", "z"), known) is None


class TestOutcomeVocabulary:
    def test_every_refusal_reason_is_distinct(self) -> None:
        """Counts only add up if each exclusion has exactly one name."""
        values = [outcome.value for outcome in PyramidLinkOutcome]
        assert len(values) == len(set(values))

    def test_the_vocabulary_covers_each_way_a_link_can_fail(self) -> None:
        expected = {
            "NOT_MATCH_ODDS", "NOT_TWO_RUNNERS", "UNRESOLVED_NAME",
            "AMBIGUOUS_TOUR", "NO_SETTLEMENT", "AMBIGUOUS_SETTLEMENT",
            "NO_PRICE_AT_HORIZON", "THIN_RATING_HISTORY",
        }
        assert {outcome.name for outcome in PyramidLinkOutcome} == expected
