"""SPEC-044: commercial-output licensing lineage (ADR 0013).

A prediction or derived model output may cite one or more upstream licensed sources via
``source_lineage_ids``. Two questions are ALWAYS answered separately and MUST NEVER be
conflated:

* ``internal_research_eligibility`` — may this lineage be used inside the research/trading
  pipeline (offline research, model training, private automated betting, internal
  retention)?
* ``publication_eligibility`` — may an output built from this lineage be shown, published,
  or handed to a third party (derived probability/odds publication, display of source
  facts, commercial customer output, API redistribution, bulk export, customer-facing
  explanations)?

Public availability of a source does NOT imply publication rights, and internal-use
approval does NOT imply publication approval — each ``permitted_uses`` key is checked
independently and explicitly; nothing is inferred from ``data_classification`` or any other
descriptive field.

Both functions FAIL CLOSED:

* an unknown ``source_id`` in the lineage,
* a missing/``None`` permission entry for the use in question,
* a source whose ``status`` is not ``"permitted"``,
* a ``rights_review_by`` date at or before ``as_of`` (stale rights),

each independently make the WHOLE lineage ineligible for that eligibility check. Lineage is
never recomputed away: callers pass the full ``source_lineage_ids`` list every time, and
copying/transforming an output must carry the same list forward (this module never mutates
or shrinks it).

Transitive rule: when a lineage cites multiple sources, the output inherits the MOST
RESTRICTIVE applicable condition — i.e. it is eligible for a given use only if EVERY cited
source is eligible for that use. One unapproved source makes the whole output publication
INELIGIBLE without touching internal research eligibility, and vice versa: the two results
are independent and must be computed and reported separately by the caller.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Mapping

# --- Per-use permission vocabulary -----------------------------------------------------

INTERNAL_USES: frozenset[str] = frozenset(
    {
        "offline_research",
        "model_training",
        "private_automated_betting",
        "cloud_processing",
        "third_party_ci_processing",
        "retention",
        "derived_model_retention",
    }
)

PUBLICATION_USES: frozenset[str] = frozenset(
    {
        "derived_probability_publication",
        "derived_fair_odds_publication",
        "display_of_source_facts",
        "commercial_customer_output",
        "api_redistribution",
        "bulk_export",
        "customer_facing_explanations",
    }
)

ALL_USES: frozenset[str] = INTERNAL_USES | PUBLICATION_USES


class OutputRightsError(Exception):
    """Raised on a malformed registry entry or an invalid ``use`` argument."""


class EligibilityStatus(Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE_LICENSING = "ineligible_licensing"
    INELIGIBLE_STALE_RIGHTS = "ineligible_stale_rights"


@dataclass(frozen=True)
class SourceRights:
    """One registry entry's rights lineage-relevant fields.

    ``permitted_uses`` MUST cover every key in :data:`ALL_USES`; a use key that is absent or
    ``None`` is treated as *not granted* (fail closed), never as "not applicable".
    """

    source_id: str
    status: str
    permitted_uses: Mapping[str, bool | None]
    rights_review_by: date | None = None

    def is_permitted_for(self, use: str) -> bool:
        if self.status != "permitted":
            return False
        return self.permitted_uses.get(use) is True

    def is_stale(self, *, as_of: date) -> bool:
        return self.rights_review_by is not None and self.rights_review_by <= as_of


@dataclass(frozen=True)
class EligibilityResult:
    """The outcome of one eligibility check for one ``use`` over one lineage.

    ``eligible`` is a convenience derived from ``status`` — callers MUST branch on
    ``status``, not merely on a boolean, since ``INELIGIBLE_LICENSING`` and
    ``INELIGIBLE_STALE_RIGHTS`` require different remediation (get rights vs. re-review).
    """

    status: EligibilityStatus
    reasons: tuple[str, ...]
    rights_registry_version: str

    @property
    def eligible(self) -> bool:
        return self.status is EligibilityStatus.ELIGIBLE


def _registry_version(registry: Mapping[str, SourceRights]) -> str:
    """Deterministic version tag for the registry snapshot actually consulted.

    Built from the exact set of entries visible to the caller (not a file hash) so that two
    calls with the same in-memory registry are provably reproducible, and so that a caller
    can tell whether the registry used for a decision has since changed.
    """
    parts = []
    for source_id in sorted(registry):
        rights = registry[source_id]
        uses = ",".join(f"{k}={rights.permitted_uses.get(k)!r}" for k in sorted(ALL_USES))
        review = rights.rights_review_by.isoformat() if rights.rights_review_by else "none"
        parts.append(f"{source_id}:{rights.status}:{uses}:{review}")
    return "sha256:" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _check_lineage(
    source_lineage_ids: tuple[str, ...],
    registry: Mapping[str, SourceRights],
    *,
    use: str,
    as_of: date,
    allowed_uses: frozenset[str],
) -> EligibilityResult:
    if use not in allowed_uses:
        raise OutputRightsError(f"{use!r} is not a valid use for this eligibility check")

    version = _registry_version(registry)
    reasons: list[str] = []
    stale = False

    if not source_lineage_ids:
        # Fail closed: an output with no declared lineage has no basis for eligibility.
        return EligibilityResult(
            status=EligibilityStatus.INELIGIBLE_LICENSING,
            reasons=("source_lineage_ids is empty: no lineage to evaluate",),
            rights_registry_version=version,
        )

    for source_id in source_lineage_ids:
        rights = registry.get(source_id)
        if rights is None:
            reasons.append(f"{source_id}: unknown source id")
            continue
        if rights.is_stale(as_of=as_of):
            stale = True
            reasons.append(
                f"{source_id}: rights review date {rights.rights_review_by} has passed as of {as_of}"
            )
            continue
        if not rights.is_permitted_for(use):
            reasons.append(f"{source_id}: {use} not granted (status={rights.status!r})")

    if not reasons:
        return EligibilityResult(
            status=EligibilityStatus.ELIGIBLE,
            reasons=(),
            rights_registry_version=version,
        )

    # Most-restrictive-wins: any failure at all makes the whole lineage ineligible. Staleness
    # is reported distinctly from a plain licensing gap whenever it is present, since it
    # requires re-review rather than a fresh grant.
    status = EligibilityStatus.INELIGIBLE_STALE_RIGHTS if stale else EligibilityStatus.INELIGIBLE_LICENSING
    return EligibilityResult(status=status, reasons=tuple(reasons), rights_registry_version=version)


def publication_eligibility(
    source_lineage_ids: tuple[str, ...],
    registry: Mapping[str, SourceRights],
    *,
    use: str,
    as_of: date,
) -> EligibilityResult:
    """Whether an output citing ``source_lineage_ids`` may be published for ``use``.

    Fails closed on any unknown source, missing/false permission, non-``"permitted"``
    status, or stale ``rights_review_by``. Public availability of a source is irrelevant:
    only an explicit ``True`` under the matching key in ``permitted_uses`` grants rights.
    """
    return _check_lineage(
        source_lineage_ids, registry, use=use, as_of=as_of, allowed_uses=PUBLICATION_USES
    )


def internal_research_eligibility(
    source_lineage_ids: tuple[str, ...],
    registry: Mapping[str, SourceRights],
    *,
    use: str,
    as_of: date,
) -> EligibilityResult:
    """Whether ``source_lineage_ids`` may be used internally (research/training/betting/etc).

    Computed completely independently of :func:`publication_eligibility` over a disjoint
    use vocabulary: an output may be internal-research-eligible while publication-ineligible
    (or the reverse), and the two results are never merged into one another.
    """
    return _check_lineage(
        source_lineage_ids, registry, use=use, as_of=as_of, allowed_uses=INTERNAL_USES
    )
