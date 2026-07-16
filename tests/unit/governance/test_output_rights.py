"""SPEC-044: commercial-output licensing lineage (ADR 0013).

Behavioral tests for ``governance.output_rights`` — publication eligibility and internal
research eligibility over a source lineage. The module does not yet exist in the repo (it
is drafted in scratch pending review); these tests are expected to be RED with an
ImportError until it lands.
"""
from __future__ import annotations

from datetime import date

import pytest

from governance.output_rights import (
    EligibilityStatus,
    OutputRightsError,
    SourceRights,
    internal_research_eligibility,
    publication_eligibility,
)

pytestmark = pytest.mark.spec("SPEC-044")

_TODAY = date(2026, 7, 16)
_FAR_FUTURE = date(2030, 1, 1)
_PAST = date(2020, 1, 1)


def _all_uses_granted() -> dict[str, bool | None]:
    return {
        "offline_research": True,
        "model_training": True,
        "private_automated_betting": True,
        "derived_probability_publication": True,
        "derived_fair_odds_publication": True,
        "display_of_source_facts": True,
        "commercial_customer_output": True,
        "api_redistribution": True,
        "bulk_export": True,
        "customer_facing_explanations": True,
        "cloud_processing": True,
        "third_party_ci_processing": True,
        "retention": True,
        "derived_model_retention": True,
    }


def _all_uses_denied() -> dict[str, bool | None]:
    return {k: None for k in _all_uses_granted()}


def _fully_permitted(source_id: str, *, review_by: date | None = _FAR_FUTURE) -> SourceRights:
    return SourceRights(
        source_id=source_id,
        status="permitted",
        permitted_uses=_all_uses_granted(),
        rights_review_by=review_by,
    )


def _candidate(source_id: str) -> SourceRights:
    return SourceRights(
        source_id=source_id,
        status="candidate",
        permitted_uses=_all_uses_denied(),
        rights_review_by=None,
    )


# --- publication eligibility: baseline grant/deny ---------------------------------------


def test_fully_permitted_single_source_is_publication_eligible() -> None:
    registry = {"a": _fully_permitted("a")}
    result = publication_eligibility(
        ("a",), registry, use="derived_probability_publication", as_of=_TODAY
    )
    assert result.status is EligibilityStatus.ELIGIBLE
    assert result.eligible is True
    assert result.reasons == ()


def test_candidate_status_is_publication_ineligible_even_with_true_flags() -> None:
    # status must itself be "permitted"; a candidate entry never grants rights regardless of
    # what permitted_uses says.
    rights = SourceRights(
        source_id="a", status="candidate", permitted_uses=_all_uses_granted(), rights_review_by=_FAR_FUTURE
    )
    registry = {"a": rights}
    result = publication_eligibility(
        ("a",), registry, use="derived_probability_publication", as_of=_TODAY
    )
    assert result.status is EligibilityStatus.INELIGIBLE_LICENSING


def test_missing_permission_key_fails_closed() -> None:
    uses = _all_uses_granted()
    del uses["derived_probability_publication"]
    registry = {"a": SourceRights(source_id="a", status="permitted", permitted_uses=uses, rights_review_by=_FAR_FUTURE)}
    result = publication_eligibility(
        ("a",), registry, use="derived_probability_publication", as_of=_TODAY
    )
    assert result.status is EligibilityStatus.INELIGIBLE_LICENSING


def test_none_valued_permission_fails_closed() -> None:
    registry = {"a": _candidate("a")}
    registry["a"] = SourceRights(
        source_id="a", status="permitted", permitted_uses=_all_uses_denied(), rights_review_by=_FAR_FUTURE
    )
    result = publication_eligibility(
        ("a",), registry, use="derived_probability_publication", as_of=_TODAY
    )
    assert result.status is EligibilityStatus.INELIGIBLE_LICENSING


# --- public availability does not imply publication rights ------------------------------


def test_public_dataset_without_explicit_grant_is_still_ineligible() -> None:
    # A source that is publicly available carries no special-cased permission: only an
    # explicit True under the matching key grants rights. Simulate "publicly available" by
    # granting only offline_research (freely readable) and nothing publication-facing.
    uses = _all_uses_denied()
    uses["offline_research"] = True
    registry = {
        "public-feed": SourceRights(
            source_id="public-feed", status="permitted", permitted_uses=uses, rights_review_by=_FAR_FUTURE
        )
    }
    result = publication_eligibility(
        ("public-feed",), registry, use="display_of_source_facts", as_of=_TODAY
    )
    assert result.status is EligibilityStatus.INELIGIBLE_LICENSING


# --- internal-use approval does not imply publication approval, and vice versa ----------


def test_internal_use_approved_source_can_still_be_publication_ineligible() -> None:
    uses = _all_uses_denied()
    uses["offline_research"] = True
    uses["model_training"] = True
    registry = {
        "a": SourceRights(source_id="a", status="permitted", permitted_uses=uses, rights_review_by=_FAR_FUTURE)
    }
    internal = internal_research_eligibility(("a",), registry, use="model_training", as_of=_TODAY)
    pub = publication_eligibility(("a",), registry, use="derived_probability_publication", as_of=_TODAY)
    assert internal.status is EligibilityStatus.ELIGIBLE
    assert pub.status is EligibilityStatus.INELIGIBLE_LICENSING


def test_publication_approved_source_without_internal_grant_is_internal_ineligible() -> None:
    uses = _all_uses_denied()
    uses["derived_probability_publication"] = True
    registry = {
        "a": SourceRights(source_id="a", status="permitted", permitted_uses=uses, rights_review_by=_FAR_FUTURE)
    }
    pub = publication_eligibility(("a",), registry, use="derived_probability_publication", as_of=_TODAY)
    internal = internal_research_eligibility(("a",), registry, use="model_training", as_of=_TODAY)
    assert pub.status is EligibilityStatus.ELIGIBLE
    assert internal.status is EligibilityStatus.INELIGIBLE_LICENSING


# --- transitive lineage: most-restrictive-wins ------------------------------------------


def test_one_unapproved_source_makes_whole_lineage_publication_ineligible() -> None:
    registry = {
        "a": _fully_permitted("a"),
        "b": _candidate("b"),
    }
    result = publication_eligibility(
        ("a", "b"), registry, use="derived_probability_publication", as_of=_TODAY
    )
    assert result.status is EligibilityStatus.INELIGIBLE_LICENSING
    assert any("b" in r for r in result.reasons)


def test_unapproved_source_does_not_touch_internal_research_eligibility_of_other_sources() -> None:
    # The two eligibilities are separate results: a publication-blocking source does not
    # retroactively revoke internal research eligibility for a lineage that IS internally
    # approved end to end.
    registry = {
        "a": _fully_permitted("a"),
        "b": SourceRights(
            source_id="b",
            status="permitted",
            permitted_uses={**_all_uses_granted(), "derived_probability_publication": None},
            rights_review_by=_FAR_FUTURE,
        ),
    }
    pub = publication_eligibility(("a", "b"), registry, use="derived_probability_publication", as_of=_TODAY)
    internal = internal_research_eligibility(("a", "b"), registry, use="model_training", as_of=_TODAY)
    assert pub.status is EligibilityStatus.INELIGIBLE_LICENSING
    assert internal.status is EligibilityStatus.ELIGIBLE


def test_all_sources_approved_lineage_is_eligible() -> None:
    registry = {"a": _fully_permitted("a"), "b": _fully_permitted("b"), "c": _fully_permitted("c")}
    result = publication_eligibility(
        ("a", "b", "c"), registry, use="derived_probability_publication", as_of=_TODAY
    )
    assert result.status is EligibilityStatus.ELIGIBLE


# --- copying/transforming does not erase lineage ----------------------------------------


def test_lineage_is_an_explicit_input_list_never_shrunk_by_the_module() -> None:
    # The module never recomputes or trims source_lineage_ids; passing the same lineage
    # twice (simulating a copy/transform that forwards the original list unchanged) gives
    # the identical result both times.
    registry = {"a": _fully_permitted("a"), "b": _candidate("b")}
    lineage = ("a", "b")
    first = publication_eligibility(lineage, registry, use="derived_probability_publication", as_of=_TODAY)
    second = publication_eligibility(tuple(lineage), registry, use="derived_probability_publication", as_of=_TODAY)
    assert first.status == second.status
    assert first.reasons == second.reasons


def test_empty_lineage_fails_closed() -> None:
    registry = {"a": _fully_permitted("a")}
    result = publication_eligibility((), registry, use="derived_probability_publication", as_of=_TODAY)
    assert result.status is EligibilityStatus.INELIGIBLE_LICENSING


# --- fail-closed on missing entries, missing keys, stale rights --------------------------


def test_unknown_source_id_fails_closed() -> None:
    registry = {"a": _fully_permitted("a")}
    result = publication_eligibility(
        ("a", "does-not-exist"), registry, use="derived_probability_publication", as_of=_TODAY
    )
    assert result.status is EligibilityStatus.INELIGIBLE_LICENSING
    assert any("does-not-exist" in r for r in result.reasons)


def test_stale_rights_review_date_fails_closed_and_is_distinguished() -> None:
    registry = {"a": _fully_permitted("a", review_by=_PAST)}
    result = publication_eligibility(
        ("a",), registry, use="derived_probability_publication", as_of=_TODAY
    )
    assert result.status is EligibilityStatus.INELIGIBLE_STALE_RIGHTS
    assert result.eligible is False


def test_rights_review_date_exactly_as_of_is_stale_not_just_before() -> None:
    registry = {"a": _fully_permitted("a", review_by=_TODAY)}
    result = publication_eligibility(("a",), registry, use="derived_probability_publication", as_of=_TODAY)
    assert result.status is EligibilityStatus.INELIGIBLE_STALE_RIGHTS


def test_no_review_date_never_counts_as_stale() -> None:
    registry = {"a": _fully_permitted("a", review_by=None)}
    result = publication_eligibility(("a",), registry, use="derived_probability_publication", as_of=_TODAY)
    assert result.status is EligibilityStatus.ELIGIBLE


# --- status enum shape, reasons, registry version ---------------------------------------


def test_result_reports_registry_version() -> None:
    registry = {"a": _fully_permitted("a")}
    result = publication_eligibility(("a",), registry, use="derived_probability_publication", as_of=_TODAY)
    assert isinstance(result.rights_registry_version, str)
    assert result.rights_registry_version


def test_invalid_use_for_publication_check_raises() -> None:
    registry = {"a": _fully_permitted("a")}
    with pytest.raises(OutputRightsError):
        publication_eligibility(("a",), registry, use="offline_research", as_of=_TODAY)


def test_invalid_use_for_internal_check_raises() -> None:
    registry = {"a": _fully_permitted("a")}
    with pytest.raises(OutputRightsError):
        internal_research_eligibility(("a",), registry, use="derived_probability_publication", as_of=_TODAY)
