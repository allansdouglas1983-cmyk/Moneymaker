"""SPEC-039: deterministic explanation inputs.

Structured reason codes and contribution data from approved numerical attribution methods
only — signed/grouped coefficient contributions for the linear v1 model (SPEC-030/SPEC-032's
conditional-logit / stage-two combiner), identified by a VERSIONED method id. This module never
computes model internals itself: the caller (the deterministic pricing code, never an LLM)
passes in ``coefficient * feature_value`` contribution magnitudes already multiplied out; this
module only validates, structures, canonically orders and digests them, and derives a CLOSED
vocabulary of reason codes from their sign/rank.

No LLM creates, alters, smooths, infers or repairs any contribution, reason code or
probability in this module. There is no probability field anywhere on
:class:`ExplanationInputs` other than a linkage digest to the originating
:class:`~l8_evidence.prediction_snapshots.PredictionSnapshot` — explanations never alter, and
cannot be mistaken for, a probability (SPEC-039, SPEC-036).

This module MUST NOT import ``l5_decision``, ``l5b_risk``, ``l6_broker`` or ``l7_settle`` — it
is a read-only analytics consumer (ADR 0013, ``.claude/rules/analytics.md``), enforced by
``tests/unit/governance/test_analytics_import_boundary.py``.

Ambiguity resolutions taken while drafting this slice:

* "Approved attribution methods" is read as a closed registry of ``(method_id, version)``
  pairs rather than an open string — v1 approves exactly one entry,
  ``("linear-coefficient-contributions", 1)``, for the linear conditional-logit/stage-two
  models. An unknown ``(method_id, version)`` pair is refused at construction, never silently
  accepted or coerced to the nearest known version.
* "Contribution naming an unapproved feature is refused" is read as: the caller supplies the
  race/prediction's approved feature-name allowlist (typically the pricing model's
  ``FeatureSchema.names``) explicitly at construction time; this module has no notion of
  "the schema" of its own and never invents one.
* Reason codes are derived ONLY by rank/sign over the supplied contributions — never by
  magnitude thresholds this module would have to invent, and never by any text the caller
  supplies. The mapping is: the single highest-signed contribution -> ``STRONGEST_POSITIVE_
  FACTOR`` (only if positive) or no positive-factor code if the top contribution is <= 0; the
  single lowest-signed contribution -> ``STRONGEST_NEGATIVE_FACTOR`` (only if negative); a
  contribution whose magnitude is exactly zero never earns a "strongest" code (it carries no
  directional information) even if it happens to be first/last after sorting. This keeps the
  mapping deterministic under any input ordering (see ``_canonical_order``) and free of any
  caller-suppliable magnitude threshold.
* "No causal language" is enforced with a fixed blocklist of substrings
  (``_CAUSAL_VOCABULARY_BLOCKLIST``) checked against every generated reason-code display
  string at construction time; a display string is generated entirely by this module's own
  fixed templates (never caller-supplied free text), so the check is a self-consistency
  guard against future template edits, not a filter over untrusted input.
* Reproducibility digest covers ``method_id``, ``method_version``, the prediction linkage
  (``prediction_id`` + the snapshot's own ``content_digest()``), the contributions in
  CANONICAL order (sorted by feature_name, never input order) and the derived reason codes —
  so two constructions from the same logical inputs (any contribution ordering) are
  byte-identical, and reordering never changes the digest (tested).
* :class:`AttributionUnavailable` is a distinct type from :class:`ExplanationInputs` (not an
  optional/nullable field on it) so a caller can never accidentally treat "unavailable" as a
  degraded populated explanation — the type system forces a branch.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Mapping, Sequence

from l8_evidence.prediction_snapshots import PredictionSnapshot

__all__ = [
    "ExplanationInputsError",
    "UnapprovedAttributionMethodError",
    "UnapprovedFeatureError",
    "EmptyLineageError",
    "ReasonCode",
    "AttributionMethod",
    "FeatureContribution",
    "ExplanationInputs",
    "AttributionUnavailable",
    "APPROVED_ATTRIBUTION_METHODS",
    "build_explanation_inputs",
]

_HASH_PREFIX = "sha256:"


class ExplanationInputsError(ValueError):
    """Base error for this module."""


class UnapprovedAttributionMethodError(ExplanationInputsError):
    """The requested ``(method_id, method_version)`` is not in the approved registry."""


class UnapprovedFeatureError(ExplanationInputsError):
    """A contribution names a feature outside the caller-supplied approved-features list."""


class EmptyLineageError(ExplanationInputsError):
    """``source_lineage_ids`` was empty — an explanation cannot carry no lineage at all."""


class ReasonCode(Enum):
    """SPEC-039's closed reason-code vocabulary, derived only from contribution sign/rank.

    Never free text; never LLM-assigned; never carries a causal claim.
    """

    STRONGEST_POSITIVE_FACTOR = "STRONGEST_POSITIVE_FACTOR"
    STRONGEST_NEGATIVE_FACTOR = "STRONGEST_NEGATIVE_FACTOR"


@dataclass(frozen=True)
class AttributionMethod:
    """One VERSIONED approved-method registry entry (SPEC-039)."""

    method_id: str
    method_version: int

    def __post_init__(self) -> None:
        if not self.method_id or not self.method_id.strip():
            raise ExplanationInputsError("method_id must be non-empty")
        if self.method_version < 1:
            raise ExplanationInputsError("method_version must be >= 1")


#: v1 approves exactly one attribution method: signed/grouped coefficient contributions for
#: the linear conditional-logit / stage-two combiner models (SPEC-030/SPEC-032). Extending
#: this registry (a new method or a new version) is a specification change, not a runtime
#: parameter — no caller-supplied method is ever accepted without appearing here first.
APPROVED_ATTRIBUTION_METHODS: frozenset[AttributionMethod] = frozenset(
    {AttributionMethod(method_id="linear-coefficient-contributions", method_version=1)}
)

_CAUSAL_VOCABULARY_BLOCKLIST: tuple[str, ...] = (
    "because",
    "caused",
    "causes",
    "causing",
    "due to",
    "leads to",
    "results in",
    "reason for",
)


@dataclass(frozen=True)
class FeatureContribution:
    """One feature's signed contribution magnitude (``coefficient * feature_value``).

    Computed entirely by deterministic pricing code BEFORE it reaches this module — this
    module never derives ``magnitude`` itself, only validates and structures it.
    """

    feature_name: str
    magnitude: float
    group_label: str | None = None

    def __post_init__(self) -> None:
        if not self.feature_name or not self.feature_name.strip():
            raise ExplanationInputsError("feature_name must be non-empty")
        if self.group_label is not None and not self.group_label.strip():
            raise ExplanationInputsError("group_label, if given, must be non-empty")


def _canonical_order(contributions: Sequence[FeatureContribution]) -> tuple[FeatureContribution, ...]:
    """Sort by ``feature_name`` — the single canonical order this module ever serialises or
    derives reason codes from, so caller input order never affects any output."""
    return tuple(sorted(contributions, key=lambda c: c.feature_name))


def _derive_reason_codes(
    contributions: Sequence[FeatureContribution],
) -> tuple[tuple[ReasonCode, str], ...]:
    """Derive reason codes purely from contribution sign/rank (SPEC-039).

    Ties are broken by ``feature_name`` ascending so the result never depends on input order
    (the same guarantee ``_canonical_order`` gives the digest).
    """
    ordered = _canonical_order(contributions)
    codes: list[tuple[ReasonCode, str]] = []
    positive = [c for c in ordered if c.magnitude > 0.0]
    negative = [c for c in ordered if c.magnitude < 0.0]
    if positive:
        top = max(positive, key=lambda c: (c.magnitude, c.feature_name))
        codes.append(
            (
                ReasonCode.STRONGEST_POSITIVE_FACTOR,
                f"{ReasonCode.STRONGEST_POSITIVE_FACTOR.value}: {top.feature_name}",
            )
        )
    if negative:
        bottom = min(negative, key=lambda c: (c.magnitude, c.feature_name))
        codes.append(
            (
                ReasonCode.STRONGEST_NEGATIVE_FACTOR,
                f"{ReasonCode.STRONGEST_NEGATIVE_FACTOR.value}: {bottom.feature_name}",
            )
        )
    for _, display in codes:
        lowered = display.lower()
        for blocked in _CAUSAL_VOCABULARY_BLOCKLIST:
            if blocked in lowered:
                raise ExplanationInputsError(
                    f"generated reason string {display!r} contains causal vocabulary {blocked!r}"
                )
    return tuple(codes)


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    return value


@dataclass(frozen=True)
class AttributionUnavailable:
    """Attribution is not supported for this model/method — an explicit marker, never an
    approximation and never a partially-filled :class:`ExplanationInputs`."""

    prediction_id: str
    reason: str

    def __post_init__(self) -> None:
        if not self.prediction_id or not self.prediction_id.strip():
            raise ExplanationInputsError("prediction_id must be non-empty")
        if not self.reason or not self.reason.strip():
            raise ExplanationInputsError("reason must be non-empty")


def _reproducibility_payload_digest(
    *,
    prediction_id: str,
    prediction_content_digest: str,
    method_id: str,
    method_version: int,
    contributions: Sequence[FeatureContribution],
    reason_codes: Sequence[ReasonCode],
    source_lineage_ids: Sequence[str],
) -> str:
    """The single canonical reproducibility digest, shared by the builder and the type's own
    self-verification so a well-formed-but-wrong digest cannot survive construction."""
    payload = {
        "prediction_id": prediction_id,
        "prediction_content_digest": prediction_content_digest,
        "method_id": method_id,
        "method_version": method_version,
        "contributions": [_jsonable(c) for c in _canonical_order(contributions)],
        "reason_codes": [c.value for c in reason_codes],
        "source_lineage_ids": sorted(source_lineage_ids),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return _HASH_PREFIX + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExplanationInputs:
    """One SPEC-039 explanation: structured reason codes + contribution data for a single
    valid prediction. Carries NO probability/odds field — only a linkage digest to the
    originating snapshot, so an explanation can never alter or masquerade as a probability.
    """

    prediction_id: str
    prediction_content_digest: str
    method_id: str
    method_version: int
    contributions: tuple[FeatureContribution, ...]
    reason_codes: tuple[ReasonCode, ...]
    source_lineage_ids: tuple[str, ...]
    reproducibility_digest: str

    def __post_init__(self) -> None:
        if not self.prediction_id or not self.prediction_id.strip():
            raise ExplanationInputsError("prediction_id must be non-empty")
        if not self.prediction_content_digest.startswith(_HASH_PREFIX) or len(
            self.prediction_content_digest
        ) != len(_HASH_PREFIX) + 64:
            raise ExplanationInputsError("prediction_content_digest must be a sha256:<hex> digest")
        if not self.source_lineage_ids:
            raise EmptyLineageError("source_lineage_ids must not be empty")
        if not self.reproducibility_digest.startswith(_HASH_PREFIX) or len(
            self.reproducibility_digest
        ) != len(_HASH_PREFIX) + 64:
            raise ExplanationInputsError("reproducibility_digest must be a sha256:<hex> digest")
        # Self-verification: the digest is recomputed from this object's own fields, so even a
        # well-formed-but-wrong digest (or reason codes inconsistent with the contributions'
        # digest-covered values) is refused at construction — the type cannot lie about its
        # own reproducibility. (prediction_content_digest stays shape-checked only: verifying
        # it requires the snapshot, which is the builder's job.)
        expected = _reproducibility_payload_digest(
            prediction_id=self.prediction_id,
            prediction_content_digest=self.prediction_content_digest,
            method_id=self.method_id,
            method_version=self.method_version,
            contributions=self.contributions,
            reason_codes=self.reason_codes,
            source_lineage_ids=self.source_lineage_ids,
        )
        if self.reproducibility_digest != expected:
            raise ExplanationInputsError(
                "reproducibility_digest does not match this explanation's own canonical "
                f"content: expected {expected!r}"
            )


def build_explanation_inputs(
    snapshot: PredictionSnapshot,
    *,
    method_id: str,
    method_version: int,
    contributions: Sequence[FeatureContribution],
    approved_feature_names: Sequence[str],
    source_lineage_ids: Sequence[str],
) -> ExplanationInputs:
    """Build a SPEC-039 :class:`ExplanationInputs` from a valid ``snapshot``.

    Refuses: an unapproved ``(method_id, method_version)``; a contribution naming a feature
    outside ``approved_feature_names``; empty ``source_lineage_ids``. Never computes model
    internals — every ``magnitude`` in ``contributions`` must already be the deterministic
    ``coefficient * feature_value`` product computed by the pricing code that produced
    ``snapshot``.
    """
    method = AttributionMethod(method_id=method_id, method_version=method_version)
    if method not in APPROVED_ATTRIBUTION_METHODS:
        raise UnapprovedAttributionMethodError(
            f"attribution method {method_id!r} v{method_version} is not approved "
            f"(approved: {sorted((m.method_id, m.method_version) for m in APPROVED_ATTRIBUTION_METHODS)})"
        )

    approved_set = set(approved_feature_names)
    for contribution in contributions:
        if contribution.feature_name not in approved_set:
            raise UnapprovedFeatureError(
                f"feature {contribution.feature_name!r} is not in the approved-features list "
                f"for prediction {snapshot.prediction_id!r}"
            )

    # Canonical lineage: sorted and deduplicated, so the stored field is byte-identical to
    # what the digest covers and never depends on caller input order.
    lineage = tuple(sorted(set(source_lineage_ids)))
    if not lineage:
        raise EmptyLineageError("source_lineage_ids must not be empty")

    ordered_contributions = _canonical_order(contributions)
    reason_pairs = _derive_reason_codes(contributions)
    reason_codes = tuple(code for code, _display in reason_pairs)

    prediction_content_digest = snapshot.content_digest()
    reproducibility_digest = _reproducibility_payload_digest(
        prediction_id=snapshot.prediction_id,
        prediction_content_digest=prediction_content_digest,
        method_id=method.method_id,
        method_version=method.method_version,
        contributions=ordered_contributions,
        reason_codes=reason_codes,
        source_lineage_ids=lineage,
    )

    return ExplanationInputs(
        prediction_id=snapshot.prediction_id,
        prediction_content_digest=prediction_content_digest,
        method_id=method.method_id,
        method_version=method.method_version,
        contributions=ordered_contributions,
        reason_codes=reason_codes,
        source_lineage_ids=lineage,
        reproducibility_digest=reproducibility_digest,
    )
