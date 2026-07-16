"""SPEC-044 properties: monotone restriction, determinism, and fail-closed on unknown ids.

Publication eligibility over a lineage MUST behave as a monotone restriction (adding a
source to the lineage never widens rights), MUST be deterministic given the same inputs,
and MUST always fail closed for any lineage containing an unknown source id.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from governance.output_rights import (
    EligibilityStatus,
    SourceRights,
    internal_research_eligibility,
    publication_eligibility,
)

pytestmark = pytest.mark.spec("SPEC-044")

_AS_OF = date(2026, 7, 16)
_USE = "derived_probability_publication"
_INTERNAL_USE = "offline_research"


def _all_uses(granted: bool) -> dict[str, bool | None]:
    value: bool | None = True if granted else None
    return {
        "offline_research": value,
        "model_training": value,
        "private_automated_betting": value,
        "derived_probability_publication": value,
        "derived_fair_odds_publication": value,
        "display_of_source_facts": value,
        "commercial_customer_output": value,
        "api_redistribution": value,
        "bulk_export": value,
        "customer_facing_explanations": value,
        "cloud_processing": value,
        "third_party_ci_processing": value,
        "retention": value,
        "derived_model_retention": value,
    }


def _rights(source_id: str, *, granted: bool, review_by: date | None) -> SourceRights:
    return SourceRights(
        source_id=source_id,
        status="permitted",
        permitted_uses=_all_uses(granted),
        rights_review_by=review_by,
    )


_SOURCE_ID = st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd")), min_size=1, max_size=8)
_GRANTED = st.booleans()
_FUTURE_REVIEW = st.just(_AS_OF + timedelta(days=365))


@given(
    source_ids=st.lists(_SOURCE_ID, min_size=1, max_size=6, unique=True),
    grants=st.data(),
)
def test_adding_a_source_never_widens_publication_rights(
    source_ids: list[str], grants: st.DataObject
) -> None:
    # Build a registry where every existing source is fully granted, then add one more
    # source whose grant is drawn arbitrarily. Extending the lineage with that source must
    # never turn an ineligible-or-eligible result MORE eligible: eligibility can only stay
    # the same or move from eligible to ineligible, never the reverse.
    base_ids = source_ids[:-1] if len(source_ids) > 1 else []
    new_id = source_ids[-1]
    registry = {sid: _rights(sid, granted=True, review_by=_AS_OF + timedelta(days=365)) for sid in base_ids}
    new_granted = grants.draw(_GRANTED)
    registry[new_id] = _rights(new_id, granted=new_granted, review_by=_AS_OF + timedelta(days=365))

    before = publication_eligibility(tuple(base_ids), registry, use=_USE, as_of=_AS_OF) if base_ids else None
    after = publication_eligibility(tuple(source_ids), registry, use=_USE, as_of=_AS_OF)

    if before is None:
        # Single-source lineage: eligibility is exactly whether the grant was made.
        assert after.eligible == new_granted
        return

    if before.status is EligibilityStatus.INELIGIBLE_LICENSING:
        # Already ineligible: adding any source keeps it ineligible (monotone restriction;
        # it cannot recover eligibility by adding more lineage).
        assert after.status is EligibilityStatus.INELIGIBLE_LICENSING
    elif not new_granted:
        # Previously eligible, new source withholds the right: must become ineligible.
        assert after.status is EligibilityStatus.INELIGIBLE_LICENSING
    else:
        # Previously eligible, new source also grants: stays eligible.
        assert after.status is EligibilityStatus.ELIGIBLE


@given(source_ids=st.lists(_SOURCE_ID, min_size=1, max_size=5, unique=True))
def test_eligibility_is_deterministic(source_ids: list[str]) -> None:
    registry = {
        sid: _rights(sid, granted=True, review_by=_AS_OF + timedelta(days=365)) for sid in source_ids
    }
    first = publication_eligibility(tuple(source_ids), registry, use=_USE, as_of=_AS_OF)
    second = publication_eligibility(tuple(source_ids), registry, use=_USE, as_of=_AS_OF)
    assert first.status == second.status
    assert first.reasons == second.reasons
    assert first.rights_registry_version == second.rights_registry_version

    first_internal = internal_research_eligibility(tuple(source_ids), registry, use=_INTERNAL_USE, as_of=_AS_OF)
    second_internal = internal_research_eligibility(tuple(source_ids), registry, use=_INTERNAL_USE, as_of=_AS_OF)
    assert first_internal.status == second_internal.status
    assert first_internal.reasons == second_internal.reasons


@given(
    known_ids=st.lists(_SOURCE_ID, min_size=0, max_size=4, unique=True),
    unknown_id=_SOURCE_ID,
)
def test_unknown_source_id_always_fails_closed(known_ids: list[str], unknown_id: str) -> None:
    registry = {
        sid: _rights(sid, granted=True, review_by=_AS_OF + timedelta(days=365)) for sid in known_ids
    }
    # Force the unknown id to actually be unknown.
    if unknown_id in registry:
        return
    lineage = tuple(known_ids) + (unknown_id,)

    pub = publication_eligibility(lineage, registry, use=_USE, as_of=_AS_OF)
    internal = internal_research_eligibility(lineage, registry, use=_INTERNAL_USE, as_of=_AS_OF)

    assert pub.status is EligibilityStatus.INELIGIBLE_LICENSING
    assert internal.status is EligibilityStatus.INELIGIBLE_LICENSING
    assert any(unknown_id in r for r in pub.reasons)
    assert any(unknown_id in r for r in internal.reasons)
