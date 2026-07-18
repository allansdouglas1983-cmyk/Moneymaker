"""Founder directive 2026-07-18 §5 — governed identity bridge:
Tennis-Data record → provider source identity → namespaced CompetitorId → Betfair alias.

Requirements under test: ATP/WTA namespaces distinct; display names never canonical
identity; deterministic versioned normalization; ambiguous matches refuse; homonyms
explicitly detected; aliases separate from identity; merges/corrections append-only with
provenance; unresolved ledger returned rather than dropped; no hand-coded silent aliases.
Names only — no sporting result (June or otherwise) enters identity resolution.
"""
from __future__ import annotations

import pytest

from sport_core.competitors import CompetitorId
from sport_tennis.identity_bridge import (
    NORMALIZATION_VERSION,
    BridgeResult,
    IdentityCorrection,
    UnresolvedReason,
    apply_corrections,
    build_bridge,
    normalize_name,
)

pytestmark = [pytest.mark.spec("SPEC-023")]


class TestNormalization:
    def test_deterministic_and_versioned(self) -> None:
        assert NORMALIZATION_VERSION == "td-norm-v1"
        assert normalize_name("  Alcaraz   C. ") == normalize_name("Alcaraz C.")
        assert normalize_name("Müller A.") == normalize_name("Muller A.")  # diacritics stripped

    def test_case_and_space_insensitive(self) -> None:
        assert normalize_name("DE MINAUR A.") == normalize_name("de minaur a.")


def _bridge(td_atp: list[str], td_wta: list[str], betfair: list[str]) -> BridgeResult:
    return build_bridge(
        td_names_by_tour={"ATP": td_atp, "WTA": td_wta},
        betfair_full_names=betfair,
        source_vintage="vintage-2026-07-18",
    )


class TestHappyPath:
    def test_simple_surname_initial_resolves(self) -> None:
        r = _bridge(["Alcaraz C."], [], ["Carlos Alcaraz"])
        assert len(r.mappings) == 1
        m = r.mappings[0]
        assert m.competitor_id == CompetitorId("td-atp:alcaraz|c")
        assert m.competitor_id.namespace == "td-atp"
        assert m.betfair_alias.display_name == "Carlos Alcaraz"
        assert "Carlos Alcaraz" in m.betfair_alias.aliases
        assert m.provenance.normalization_version == NORMALIZATION_VERSION
        assert m.provenance.source_vintage == "vintage-2026-07-18"

    def test_multiword_surname_resolves(self) -> None:
        r = _bridge(["De Minaur A."], [], ["Alex De Minaur"])
        assert len(r.mappings) == 1
        assert r.mappings[0].competitor_id == CompetitorId("td-atp:de minaur|a")

    def test_hyphenated_and_multi_initial(self) -> None:
        r = _bridge(["Auger-Aliassime F.", "Del Potro J.M."], [], ["Felix Auger-Aliassime", "Juan Martin Del Potro"])
        got = {m.competitor_id.value for m in r.mappings}
        assert got == {"td-atp:auger-aliassime|f", "td-atp:del potro|jm"}

    def test_namespaces_distinct_same_name_both_tours(self) -> None:
        # Same surname+initial in ATP and WTA stays TWO identities; a Betfair name that
        # could be either is ambiguous and must refuse, never guess a tour.
        r = _bridge(["Trevisan M."], ["Trevisan M."], ["Martina Trevisan"])
        assert len(r.mappings) == 0
        reasons = {u.reason for u in r.unresolved}
        assert UnresolvedReason.CROSS_NAMESPACE_AMBIGUOUS in reasons


class TestRefusals:
    def test_td_homonym_two_raw_names_same_key_refused(self) -> None:
        r = _bridge(["Zhang Z.", "Zhang  Z."], [], ["Zhizhen Zhang"])
        assert len(r.mappings) == 1  # whitespace variants are the SAME source identity
        r2 = _bridge(["Cerundolo F."], [], ["Francisco Cerundolo", "Fernando Cerundolo"])
        # one TD identity, two Betfair candidates: homonym — refused, both surfaced
        assert len(r2.mappings) == 0
        assert any(u.reason is UnresolvedReason.HOMONYM_MULTIPLE_BETFAIR for u in r2.unresolved)

    def test_unmatched_players_land_in_unresolved_not_dropped(self) -> None:
        r = _bridge(["Alcaraz C."], [], ["Carlos Alcaraz", "Totally Unknown"])
        assert len(r.mappings) == 1
        assert any(
            u.reason is UnresolvedReason.NO_SOURCE_MATCH and u.name == "Totally Unknown"
            for u in r.unresolved
        )

    def test_td_identity_without_betfair_match_is_not_an_error(self) -> None:
        # Historical players never seen on Betfair June simply have no alias — fine.
        r = _bridge(["Federer R."], [], [])
        assert r.mappings == ()


class TestDeterminism:
    def test_order_independent(self) -> None:
        a = _bridge(["Alcaraz C.", "Sinner J."], [], ["Jannik Sinner", "Carlos Alcaraz"])
        b = _bridge(["Sinner J.", "Alcaraz C."], [], ["Carlos Alcaraz", "Jannik Sinner"])
        assert a.mappings == b.mappings
        assert a.unresolved == b.unresolved


class TestCorrections:
    def test_corrections_are_append_only_and_provenanced(self) -> None:
        r = _bridge(["Alcaraz C."], [], ["Carlos Alcaraz"])
        c = IdentityCorrection(
            subject=CompetitorId("td-atp:alcaraz|c"),
            action="ADD_ALIAS",
            detail="C. Alcaraz Garfia",
            authorised_by="founder",
            rationale="Betfair alternate listing",
        )
        r2 = apply_corrections(r, [c])
        assert r2 is not r
        assert r.mappings[0].betfair_alias.aliases == frozenset({"Carlos Alcaraz"})  # original untouched
        assert "C. Alcaraz Garfia" in r2.mappings[0].betfair_alias.aliases
        assert r2.corrections == (c,)

    def test_correction_for_unknown_identity_refused(self) -> None:
        r = _bridge(["Alcaraz C."], [], ["Carlos Alcaraz"])
        c = IdentityCorrection(
            subject=CompetitorId("td-atp:nobody|x"),
            action="ADD_ALIAS",
            detail="X",
            authorised_by="founder",
            rationale="typo",
        )
        with pytest.raises(ValueError):
            apply_corrections(r, [c])
