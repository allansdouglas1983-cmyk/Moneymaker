"""SPEC-023: the versioned, sport-agnostic feature-declaration registry (ADR 0017 S6).

This module holds feature DECLARATIONS only — names, definitions, provenance, licensing
and evidence status. It never holds feature VALUES, market data, or model inputs, and it
declares no actual features: every concrete declaration is future, data-dependent work
that arrives with its sport adapter and its licensed source. Nothing in this module knows
which sport a feature belongs to — the same contract must fit an exchange market for any
event type, including football Match Odds and binary prediction-market contracts.

Design commitments, each enforced by construction rather than convention:

* **Provenance is explicit (SPEC-023).** The closed provenance vocabulary is REUSED from
  :mod:`l3_features.knowledge_time` (``LIVE_CAPTURED`` / ``BACKFILLED``), never forked. A
  ``BACKFILLED`` declaration MUST declare a ``true_publication_time_rule`` — the rule by
  which the source's TRUE publication time is established — because a backfill
  ``first_seen_ts`` never confers historical knowability. Construction is refused without
  it. A ``LIVE_CAPTURED`` declaration carrying such a rule is refused as contradictory.
* **Licensing fails closed (SPEC-044 vocabulary at declaration level).** ``source_id`` is
  a REFERENCE into the governance source-rights registry by id; this module neither
  imports nor evaluates rights logic. The declaration-level ``licensing_status`` is a
  closed enum whose only research-usable member is ``LICENSED_FOR_RESEARCH``:
  ``UNLICENSED``, ``PENDING_REVIEW`` and any future member are unusable by default —
  anything not explicitly licensed is unusable, and staleness/permission detail belongs
  to the governance registry the ``source_id`` points at.
* **Missing data is an explicit exclusion, never a disappearance.** The universe is
  frozen before outcomes are known, so ``MissingDataBehaviour`` has exactly ONE member in
  this version: ``EXPLICIT_EXCLUSION`` (a missing feature produces an exclusion carrying
  a knowledge-time). Imputation members (fill-forward, mean-fill, zero-fill) do not exist
  DELIBERATELY: silent imputation would let a feature vanish into a fabricated value and
  quietly bias every conclusion drawn downstream; adding any such member is a governed
  specification change, not a convenience edit.
* **Evidence status cannot be asserted.** Everything is ``DECLARED`` in this version.
  ``VALIDATED`` requires a ``validation_gate_reference`` naming the gate evidence that
  validated the feature; construction is refused without one, and a merely-``DECLARED``
  feature carrying a gate reference is refused as a misdeclaration.
* **The registry is append-only.** ``register`` refuses a duplicate ``(name, version)``;
  a changed definition is a NEW version and a NEW entry. No update, delete or mutation
  API exists anywhere on the type.

This module contains no numeric literal of any kind. Every numeric quantity on this
platform is declared per-experiment or per-feature by a human under SPEC-094's
pre-registration discipline, never baked into a contract module. No LLM creates, alters
or approves any field here; every value is supplied by the caller and validated by
deterministic refusals.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique

from l3_features.knowledge_time import ProvenanceMode

__all__ = [
    "FeatureRegistryError",
    "FeatureDeclarationError",
    "DuplicateFeatureVersionError",
    "UnknownFeatureError",
    "LicensingStatus",
    "MissingDataBehaviour",
    "EvidenceStatus",
    "ProvenanceMode",
    "FeatureDeclaration",
    "FeatureRegistry",
]


class FeatureRegistryError(ValueError):
    """Base for every SPEC-023 feature-registry error."""


class FeatureDeclarationError(FeatureRegistryError):
    """A declaration's own fields are invalid or internally contradictory."""


class DuplicateFeatureVersionError(FeatureRegistryError):
    """``register`` was called twice for the same ``(name, version)`` pair."""


class UnknownFeatureError(FeatureRegistryError):
    """A lookup named a feature or version that was never registered."""


@unique
class LicensingStatus(Enum):
    """Declaration-level licensing status. FAIL-CLOSED: unlicensed means unusable.

    ``source_id`` on the declaration references the governance source-rights registry,
    which owns per-use permissions and staleness (SPEC-044); this enum is only the
    declaration's own summary state. The single research-usable member is
    ``LICENSED_FOR_RESEARCH`` — see :meth:`permits_research_use`.
    """

    LICENSED_FOR_RESEARCH = "licensed_for_research"
    UNLICENSED = "unlicensed"
    PENDING_REVIEW = "pending_review"

    def permits_research_use(self) -> bool:
        """Whether this status permits research use. Anything not explicit is refused.

        Fail-closed by construction: the check is an identity comparison against the one
        licensed member, so ``UNLICENSED``, ``PENDING_REVIEW`` and any member a future
        governed change adds are all unusable unless that change ALSO amends this method
        — an omission can only deny use, never grant it.
        """
        return self is LicensingStatus.LICENSED_FOR_RESEARCH


@unique
class MissingDataBehaviour(Enum):
    """What a missing value for the feature produces. One member, deliberately.

    The universe is frozen before outcomes are known: a missing feature MUST produce an
    explicit exclusion carrying a knowledge-time, never a disappearance and never a
    fabricated value. Imputation members do not exist because silent imputation is
    exactly the "silently degraded" behaviour the project's first rule forbids — it
    would bias every conclusion downstream while leaving no trace in the exclusion
    funnel. Adding an imputation member is a governed specification change with its own
    evidence, never a convenience edit here.
    """

    EXPLICIT_EXCLUSION = "explicit_exclusion"


@unique
class EvidenceStatus(Enum):
    """Whether the feature's predictive usefulness has gate evidence behind it.

    Everything is ``DECLARED`` in this version. ``VALIDATED`` is constructible only with
    a ``validation_gate_reference`` naming the gate evidence — a status can never be
    asserted by prose alone.
    """

    DECLARED = "declared"
    VALIDATED = "validated"


def _require_nonempty(value: object, where: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FeatureDeclarationError(f"{where} must be a non-empty string, got {value!r}")


def _require_member(value: object, enum_type: type[Enum], where: str) -> None:
    if not isinstance(value, enum_type):
        raise FeatureDeclarationError(
            f"{where} must be a {enum_type.__name__} member, got {value!r}"
        )


@dataclass(frozen=True)
class FeatureDeclaration:
    """One immutable, versioned feature declaration. A changed definition is a new version.

    Attributes:
        name: Stable feature name, shared across versions.
        description: Human-readable purpose of the feature.
        knowledge_time_semantics: How the feature's first-usable-time is established —
            the SPEC-020 build-time enforcement consumes this discipline; a feature whose
            first-usable-time is not provably before the market off is rejected at build
            time with an error.
        source_id: Reference into the governance source-rights registry by id. This
            module never evaluates rights logic (SPEC-044 owns that); the id is lineage.
        licensing_status: Declaration-level licensing summary, fail-closed
            (:class:`LicensingStatus`).
        provenance_mode: ``LIVE_CAPTURED`` or ``BACKFILLED``
            (:class:`l3_features.knowledge_time.ProvenanceMode`, SPEC-023).
        true_publication_time_rule: MANDATORY for ``BACKFILLED`` (how the true
            publication time is established — never the backfill first-seen timestamp);
            MUST be ``None`` for ``LIVE_CAPTURED`` (a live capture has no backfill rule,
            and supplying one is a contradiction, refused rather than ignored).
        missing_data_behaviour: :class:`MissingDataBehaviour` — explicit exclusion only.
        deterministic_definition: Free-text description of the deterministic formula or
            procedure. Any constants a concrete definition needs are declared by the
            human authoring that future feature's version, never by this module.
        version: Version string; ``(name, version)`` is the registry key.
        evidence_status: :class:`EvidenceStatus`.
        validation_gate_reference: MANDATORY for ``VALIDATED`` (names the gate evidence);
            MUST be ``None`` for ``DECLARED``.
    """

    name: str
    description: str
    knowledge_time_semantics: str
    source_id: str
    licensing_status: LicensingStatus
    provenance_mode: ProvenanceMode
    true_publication_time_rule: str | None
    missing_data_behaviour: MissingDataBehaviour
    deterministic_definition: str
    version: str
    evidence_status: EvidenceStatus
    validation_gate_reference: str | None

    def __post_init__(self) -> None:
        _require_nonempty(self.name, "name")
        _require_nonempty(self.description, "description")
        _require_nonempty(self.knowledge_time_semantics, "knowledge_time_semantics")
        _require_nonempty(self.source_id, "source_id")
        _require_member(self.licensing_status, LicensingStatus, "licensing_status")
        _require_member(self.provenance_mode, ProvenanceMode, "provenance_mode")
        _require_member(
            self.missing_data_behaviour, MissingDataBehaviour, "missing_data_behaviour"
        )
        _require_nonempty(self.deterministic_definition, "deterministic_definition")
        _require_nonempty(self.version, "version")
        _require_member(self.evidence_status, EvidenceStatus, "evidence_status")

        if self.provenance_mode is ProvenanceMode.BACKFILLED:
            if self.true_publication_time_rule is None:
                raise FeatureDeclarationError(
                    f"feature {self.name!r} v{self.version}: a BACKFILLED declaration "
                    "must declare a true_publication_time_rule — backfill first-seen "
                    "timestamps never confer historical knowability (SPEC-023)"
                )
            _require_nonempty(self.true_publication_time_rule, "true_publication_time_rule")
        else:
            if self.true_publication_time_rule is not None:
                raise FeatureDeclarationError(
                    f"feature {self.name!r} v{self.version}: a LIVE_CAPTURED declaration "
                    "must not carry a true_publication_time_rule — a live capture has no "
                    "backfill rule, and a contradictory declaration is refused, not "
                    "ignored"
                )

        if self.evidence_status is EvidenceStatus.VALIDATED:
            if self.validation_gate_reference is None:
                raise FeatureDeclarationError(
                    f"feature {self.name!r} v{self.version}: VALIDATED requires a "
                    "validation_gate_reference naming the gate evidence; a status can "
                    "never be asserted by prose alone"
                )
            _require_nonempty(self.validation_gate_reference, "validation_gate_reference")
        else:
            if self.validation_gate_reference is not None:
                raise FeatureDeclarationError(
                    f"feature {self.name!r} v{self.version}: a DECLARED feature must not "
                    "carry a validation_gate_reference — a gate reference on an "
                    "unvalidated feature would imply evidence that never existed"
                )


class FeatureRegistry:
    """Append-only registry of :class:`FeatureDeclaration` entries.

    The only mutating operation is :meth:`register`, and it can only APPEND: a duplicate
    ``(name, version)`` is refused outright, and no update, delete or replacement API
    exists anywhere on this type. A changed definition is a new version and therefore a
    new entry; earlier versions remain readable forever so historical conclusions stay
    reproducible.
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], FeatureDeclaration] = {}
        self._order: list[FeatureDeclaration] = []

    def register(self, declaration: FeatureDeclaration) -> None:
        """Append a new declaration. Refuses a duplicate ``(name, version)``."""
        if not isinstance(declaration, FeatureDeclaration):
            raise FeatureDeclarationError(
                f"register requires a FeatureDeclaration, got {declaration!r}"
            )
        key = (declaration.name, declaration.version)
        if key in self._by_key:
            raise DuplicateFeatureVersionError(
                f"feature {declaration.name!r} v{declaration.version} is already "
                "registered; a changed definition is a NEW version, never an overwrite"
            )
        self._by_key[key] = declaration
        self._order.append(declaration)

    def declaration_for(self, name: str, version: str) -> FeatureDeclaration:
        """The stored declaration for ``(name, version)``. Raises if never registered."""
        declaration = self._by_key.get((name, version))
        if declaration is None:
            raise UnknownFeatureError(
                f"feature {name!r} v{version} was never registered; lookups are refused, "
                "never defaulted"
            )
        return declaration

    def versions_of(self, name: str) -> tuple[str, ...]:
        """Every registered version of ``name``, in registration order.

        Raises :class:`UnknownFeatureError` if ``name`` was never registered at all — an
        unknown feature is a refusal, never an empty answer that reads like "no
        versions yet".
        """
        versions = tuple(
            declaration.version for declaration in self._order if declaration.name == name
        )
        if not versions:
            raise UnknownFeatureError(f"feature {name!r} was never registered")
        return versions

    def declarations(self) -> tuple[FeatureDeclaration, ...]:
        """Every registered declaration, in registration order."""
        return tuple(self._order)
