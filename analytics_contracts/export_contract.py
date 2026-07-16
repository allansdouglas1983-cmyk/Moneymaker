"""SPEC-045: exportable prediction contract with independent status dimensions (ADR 0013,
Amendment A).

A versioned, transport-independent, PURE/DETERMINISTIC domain contract for analytics
consumers. Every value on :class:`ExportablePrediction` is a direct passthrough of an
existing SPEC-036/037/039/044 object — this module never creates, alters, smooths or repairs
a probability, and never invents a recommendation.

This module MUST NOT import ``l5_decision``, ``l5b_risk``, ``l6_broker`` or ``l7_settle`` — it
is a read-only analytics consumer (ADR 0013, ``.claude/rules/analytics.md``), enforced by
``tests/unit/governance/test_analytics_import_boundary.py`` (which already lists
``analytics_contracts`` among the checked modules).

Three INDEPENDENT status dimensions (Amendment A), each its own closed enum, computed by
entirely separate code paths so that one can never leak into another:

* :class:`ForecastAvailability` — whether a probability exists at all for this race/market.
  ``AVAILABLE`` is carried only by :class:`ExportablePrediction`; every ``UNAVAILABLE_*`` /
  ``WITHHELD_*`` variant is carried only by :class:`UnavailableForecast`. These are two
  DISTINCT types (a tagged union, not one type with optional fields) precisely so an
  unavailable export has nowhere to put a probability, fair-odds or uncertainty value — there
  is no field to fake-default.
* :class:`PublicationEligibility` — whether this output may ever be shown to a third party.
  Derived from :class:`~governance.output_rights.EligibilityResult` by
  :func:`map_eligibility_to_publication_status`, an explicit, documented, deterministic
  mapping (see its docstring) that ALSO fails closed on the separate Gate P1 (SPEC-046)
  product gate: a lineage that is licence-``ELIGIBLE`` still maps to ``INTERNAL_ONLY`` while
  Gate P1 has not been activated by a human, because SPEC-045/046 forbid predictor
  publication until that gate is active and passed regardless of licensing.
* :class:`RecommendationStatus` — hard-pinned to a SINGLE member, ``NOT_EVALUATED``. No
  TIP/BET/selection state exists anywhere in this module's vocabulary, and neither
  :func:`build_export` nor :func:`build_unavailable` accepts a recommendation argument at
  all — the field is always the sole enum member, never derived from rank, probability, fair
  odds or market disagreement, and never LLM-assigned.

MUST NOT contain: credentials, balances, order ids, stakes, risk budgets, execution
thresholds, or any live-trading state (enforced by a field-name substring scan test over this
module's whole type tree).

Ambiguity resolutions taken while drafting this slice (see the task's final report for the
full list):

* "Fair odds ... only where the probability is present and valid" is read as: this module
  never recomputes fair odds itself. It mirrors ``PredictionSnapshot.fair_odds`` verbatim,
  which SPEC-037's own invariant already guarantees covers exactly the race's runner ids (one
  priority-ordered probability kind, race-wide present) — there is structurally no "missing
  fair odds for one runner but not another" state to represent, so no missingness field is
  added here that SPEC-037 does not already close off.
* "Explanations ... reference by digest" is read as: the export never re-carries raw
  contribution magnitudes or reason-code display strings across the analytics-contract
  boundary. :class:`ExplanationReference` carries only the identifying digests
  (``prediction_id``, ``reproducibility_digest``, ``method_id``, ``method_version``) a
  consumer needs to look the full :class:`~l8_evidence.explanation_inputs.ExplanationInputs`
  up out-of-band; :func:`build_export` verifies the supplied ``ExplanationInputs`` actually
  belongs to the snapshot being exported (matching ``prediction_id`` and
  ``prediction_content_digest``) before building the reference, refusing a mismatched one.
* ``REVIEW_REQUIRED`` (named by SPEC-045 Amendment A) is a closed vocabulary member with no
  automatic derivation path in this v1 mapping — it is reserved for a future explicit human
  flag on the rights registry, exactly as ``PublicationEligibility``'s other members are
  reserved ahead of Gate P1's activation. An enum member existing without every mapping
  branch reaching it is the same pattern SPEC-037 already uses for its own vintage/reason
  vocabularies.
* Display rounding is offered as a single pure helper, :func:`display_decimal`, that returns a
  NEW ``Decimal`` and never mutates its argument or any stored contract field — it is not
  wired into any constructor, so a display step is always an explicit, separate, opt-in call
  by the consumer.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from enum import Enum
from typing import Mapping

from governance.output_rights import EligibilityResult, EligibilityStatus, EligibilityVocabulary
from l4_pricing.probability_outputs import RunnerProbabilities
from l8_evidence.explanation_inputs import AttributionUnavailable, ExplanationInputs
from l8_evidence.prediction_snapshots import PredictionSnapshot, UncertaintySummary

__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "ExportContractError",
    "ForecastAvailability",
    "PublicationEligibility",
    "RecommendationStatus",
    "RunnerProbabilityExport",
    "ExplanationReference",
    "AttributionUnavailable",
    "ExportablePrediction",
    "UnavailableForecast",
    "map_eligibility_to_publication_status",
    "build_export",
    "build_unavailable",
    "display_decimal",
]

CONTRACT_SCHEMA_VERSION = "export-contract-v1"
_HASH_PREFIX = "sha256:"


class ExportContractError(ValueError):
    """Base error for this module."""


class ForecastAvailability(Enum):
    """Whether a probability exists at all for this race/market (SPEC-045 Amendment A).

    ``AVAILABLE`` is carried only by :class:`ExportablePrediction`. Every other member is
    carried only by :class:`UnavailableForecast`, together with a mandatory ``reason`` —
    there is no path from any of these variants to a populated probability field.
    """

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE_NO_PREDICTION = "UNAVAILABLE_NO_PREDICTION"
    UNAVAILABLE_EXCLUDED = "UNAVAILABLE_EXCLUDED"
    WITHHELD_DATA_QUALITY = "WITHHELD_DATA_QUALITY"


_UNAVAILABLE_VARIANTS = frozenset(
    {
        ForecastAvailability.UNAVAILABLE_NO_PREDICTION,
        ForecastAvailability.UNAVAILABLE_EXCLUDED,
        ForecastAvailability.WITHHELD_DATA_QUALITY,
    }
)


class PublicationEligibility(Enum):
    """Whether an export may ever be shown to a third party (SPEC-045 Amendment A).

    Derived ONLY by :func:`map_eligibility_to_publication_status` from a
    :class:`~governance.output_rights.EligibilityResult` plus the separate Gate P1 activation
    flag — never assigned freehand by a caller or an LLM.
    """

    INTERNAL_ONLY = "INTERNAL_ONLY"
    PUBLICATION_ELIGIBLE = "PUBLICATION_ELIGIBLE"
    INELIGIBLE_RIGHTS = "INELIGIBLE_RIGHTS"
    INELIGIBLE_STALE_RIGHTS = "INELIGIBLE_STALE_RIGHTS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class RecommendationStatus(Enum):
    """Hard-pinned to a single member (SPEC-045 Amendment A): no TIP/BET/selection state is
    authorised anywhere in this module. Never inferred from rank, probability, fair odds or
    market disagreement; never LLM-assigned."""

    NOT_EVALUATED = "NOT_EVALUATED"


def map_eligibility_to_publication_status(
    eligibility: EligibilityResult, *, gate_p1_activated: bool
) -> PublicationEligibility:
    """The single explicit, deterministic mapping from a licensing eligibility check plus the
    Gate P1 (SPEC-046) product-gate activation flag to a :class:`PublicationEligibility`.

    Mapping (documented here since SPEC-045 names the target vocabulary but not the mapping):

    * ``EligibilityStatus.INELIGIBLE_STALE_RIGHTS`` -> ``INELIGIBLE_STALE_RIGHTS`` always,
      regardless of ``gate_p1_activated`` — stale rights block publication on their own and
      re-review, not gate activation, is the remediation.
    * ``EligibilityStatus.INELIGIBLE_LICENSING`` -> ``INELIGIBLE_RIGHTS`` always, for the same
      reason.
    * ``EligibilityStatus.ELIGIBLE`` and ``gate_p1_activated`` is ``False`` -> ``INTERNAL_ONLY``.
      Licence eligibility alone never implies publication eligibility while the separate
      product gate is not active (ADR 0013 / ``.claude/rules/analytics.md``: "Publication is
      forbidden until Gate P1 ... is activated by a human and passed").
    * ``EligibilityStatus.ELIGIBLE`` and ``gate_p1_activated`` is ``True`` ->
      ``PUBLICATION_ELIGIBLE``.

    ``REVIEW_REQUIRED`` has no automatic derivation path in this v1 mapping (see module
    docstring) — it is reserved for a future explicit human rights-review flag, exactly as
    SPEC-037 reserves enum members without every branch reaching them.
    """
    if eligibility.vocabulary is not EligibilityVocabulary.PUBLICATION:
        raise ExportContractError(
            "publication mapping requires an EligibilityResult computed over the PUBLICATION "
            "vocabulary; internal-research approval never implies publication (SPEC-044)"
        )
    if eligibility.status is EligibilityStatus.INELIGIBLE_STALE_RIGHTS:
        return PublicationEligibility.INELIGIBLE_STALE_RIGHTS
    if eligibility.status is EligibilityStatus.INELIGIBLE_LICENSING:
        return PublicationEligibility.INELIGIBLE_RIGHTS
    if eligibility.status is not EligibilityStatus.ELIGIBLE:
        # Fail closed: a future EligibilityStatus member must be mapped here explicitly,
        # never allowed to fall through toward publication.
        raise ExportContractError(
            f"unmapped EligibilityStatus {eligibility.status!r}; publication mapping refuses "
            "to guess"
        )
    if not gate_p1_activated:
        return PublicationEligibility.INTERNAL_ONLY
    return PublicationEligibility.PUBLICATION_ELIGIBLE


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    return value


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(None):
        raise ExportContractError(f"{field} must be timezone-aware UTC")


@dataclass(frozen=True)
class RunnerProbabilityExport:
    """One runner's three SPEC-036 probability kinds, mirrored verbatim (Decimal, never
    substituted from another kind) plus the fair odds this snapshot already computed for it.

    Missingness is carried per-kind exactly as SPEC-036 declares it: a kind is either present
    (a Decimal in ``(0, 1)``) or absent with a mandatory non-empty reason — never both, never
    neither.
    """

    runner_id: int
    p_fundamental: Decimal | None
    p_fundamental_missing_reason: str | None
    p_market_info: Decimal | None
    p_market_info_missing_reason: str | None
    p_combined: Decimal | None
    p_combined_missing_reason: str | None
    fair_odds: Decimal

    def __post_init__(self) -> None:
        if self.runner_id <= 0:
            raise ExportContractError(f"runner_id must be positive, got {self.runner_id}")
        for value, reason, kind in (
            (self.p_fundamental, self.p_fundamental_missing_reason, "p_fundamental"),
            (self.p_market_info, self.p_market_info_missing_reason, "p_market_info"),
            (self.p_combined, self.p_combined_missing_reason, "p_combined"),
        ):
            if value is None and (reason is None or not reason.strip()):
                raise ExportContractError(f"{kind} is absent but has no explicit non-empty reason")
            if value is not None and reason is not None:
                raise ExportContractError(f"{kind} is present; a missing_reason must not also be set")
            if value is not None and not (Decimal(0) < value < Decimal(1)):
                raise ExportContractError(f"{kind} must be in the open interval (0, 1), got {value!r}")
        if self.fair_odds <= Decimal(0):
            raise ExportContractError("fair_odds must be positive")


@dataclass(frozen=True)
class ExplanationReference:
    """A digest-only reference to an out-of-band :class:`~l8_evidence.explanation_inputs.
    ExplanationInputs` — never re-carries raw contribution magnitudes across the contract
    boundary (see module docstring)."""

    prediction_id: str
    reproducibility_digest: str
    method_id: str
    method_version: int

    def __post_init__(self) -> None:
        if not self.prediction_id or not self.prediction_id.strip():
            raise ExportContractError("prediction_id must be non-empty")
        if not self.reproducibility_digest.startswith(_HASH_PREFIX) or len(
            self.reproducibility_digest
        ) != len(_HASH_PREFIX) + 64:
            raise ExportContractError("reproducibility_digest must be a sha256:<hex> digest")
        if not self.method_id or not self.method_id.strip():
            raise ExportContractError("method_id must be non-empty")
        if self.method_version < 1:
            raise ExportContractError("method_version must be >= 1")


def _export_runner(runner: RunnerProbabilities, fair_odds: Mapping[int, Decimal]) -> RunnerProbabilityExport:
    return RunnerProbabilityExport(
        runner_id=runner.runner_id,
        p_fundamental=runner.p_fundamental.probability if runner.p_fundamental is not None else None,
        p_fundamental_missing_reason=runner.p_fundamental_missing_reason,
        p_market_info=runner.p_market_info.probability if runner.p_market_info is not None else None,
        p_market_info_missing_reason=runner.p_market_info_missing_reason,
        p_combined=runner.p_combined.probability if runner.p_combined is not None else None,
        p_combined_missing_reason=runner.p_combined_missing_reason,
        fair_odds=fair_odds[runner.runner_id],
    )


@dataclass(frozen=True)
class ExportablePrediction:
    """SPEC-045's AVAILABLE-case export contract: a versioned, transport-independent, pure
    domain object mirroring one :class:`~l8_evidence.prediction_snapshots.PredictionSnapshot`
    faithfully, plus the three independent status dimensions.

    Carries NO credential, balance, order id, stake, risk budget or execution-threshold field
    — enforced by a field-name substring scan in the test suite over this whole module.
    """

    contract_schema_version: str
    prediction_id: str
    race_id: str
    market_id: str
    generated_at_utc: datetime
    available_to_consumer_at_utc: datetime
    decision_horizon: str
    runner_probabilities: tuple[RunnerProbabilityExport, ...]
    fair_odds: Mapping[int, Decimal]
    uncertainty: UncertaintySummary
    model_lineage_digest: str
    feature_lineage_digest: str
    source_lineage_digest: str
    forecast_availability: ForecastAvailability
    publication_eligibility: PublicationEligibility
    rights_registry_version: str
    recommendation_status: RecommendationStatus
    explanations: ExplanationReference | AttributionUnavailable

    def __post_init__(self) -> None:
        if not self.contract_schema_version or not self.contract_schema_version.strip():
            raise ExportContractError("contract_schema_version must be non-empty")
        if not self.prediction_id or not self.prediction_id.strip():
            raise ExportContractError("prediction_id must be non-empty")
        if not self.race_id or not self.race_id.strip():
            raise ExportContractError("race_id must be non-empty")
        if not self.market_id or not self.market_id.strip():
            raise ExportContractError("market_id must be non-empty")
        _require_utc(self.generated_at_utc, "generated_at_utc")
        _require_utc(self.available_to_consumer_at_utc, "available_to_consumer_at_utc")
        if self.available_to_consumer_at_utc < self.generated_at_utc:
            raise ExportContractError(
                "available_to_consumer_at_utc must not precede generated_at_utc"
            )
        if not self.decision_horizon or not self.decision_horizon.strip():
            raise ExportContractError("decision_horizon must be non-empty")
        if not self.runner_probabilities:
            raise ExportContractError("runner_probabilities must not be empty")
        runner_ids = [r.runner_id for r in self.runner_probabilities]
        if len(set(runner_ids)) != len(runner_ids):
            raise ExportContractError("runner_probabilities must not contain duplicate runner ids")
        if set(self.fair_odds) != set(runner_ids):
            raise ExportContractError("fair_odds must cover exactly the exported runner ids")
        if self.forecast_availability is not ForecastAvailability.AVAILABLE:
            raise ExportContractError(
                "ExportablePrediction always carries ForecastAvailability.AVAILABLE; use "
                "UnavailableForecast for every other variant"
            )
        if self.recommendation_status is not RecommendationStatus.NOT_EVALUATED:
            raise ExportContractError(
                "recommendation_status is hard-pinned to NOT_EVALUATED"
            )
        if not self.rights_registry_version or not self.rights_registry_version.strip():
            raise ExportContractError("rights_registry_version must be non-empty")

    def content_digest(self) -> str:
        """Deterministic ``sha256:<hex>`` over every field, canonically serialised — same
        field values always produce the identical digest (SPEC-045: reproducible from
        approved manifests)."""
        payload = _jsonable(dataclasses.asdict(self))
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return _HASH_PREFIX + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class UnavailableForecast:
    """SPEC-045's UNAVAILABLE/WITHHELD-case export: structurally has NO probability, fair-odds
    or uncertainty field at all — there is nowhere on this type to put a fake default."""

    contract_schema_version: str
    race_id: str
    market_id: str
    generated_at_utc: datetime
    forecast_availability: ForecastAvailability
    reason: str
    recommendation_status: RecommendationStatus

    def __post_init__(self) -> None:
        if not self.contract_schema_version or not self.contract_schema_version.strip():
            raise ExportContractError("contract_schema_version must be non-empty")
        if not self.race_id or not self.race_id.strip():
            raise ExportContractError("race_id must be non-empty")
        if not self.market_id or not self.market_id.strip():
            raise ExportContractError("market_id must be non-empty")
        _require_utc(self.generated_at_utc, "generated_at_utc")
        if self.forecast_availability not in _UNAVAILABLE_VARIANTS:
            raise ExportContractError(
                "UnavailableForecast must carry an UNAVAILABLE_*/WITHHELD_* availability, "
                "never AVAILABLE — use ExportablePrediction for the available case"
            )
        if not self.reason or not self.reason.strip():
            raise ExportContractError("reason must be non-empty for an unavailable export")
        if self.recommendation_status is not RecommendationStatus.NOT_EVALUATED:
            raise ExportContractError("recommendation_status is hard-pinned to NOT_EVALUATED")

    def content_digest(self) -> str:
        payload = _jsonable(dataclasses.asdict(self))
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return _HASH_PREFIX + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def display_decimal(value: Decimal, *, places: int) -> Decimal:
    """Pure display-only rounding helper (SPEC-045: "display rounding never alters stored
    probabilities"). Returns a NEW ``Decimal``; never mutates ``value`` (Decimals are
    immutable in any case) and is never wired into any constructor above — a consumer must
    call this explicitly and separately from the stored contract value it read.
    """
    if places < 0:
        raise ExportContractError("places must be >= 0")
    quantum = Decimal(1).scaleb(-places)
    return value.quantize(quantum, rounding=ROUND_HALF_EVEN)


def _explanation_reference(
    snapshot: PredictionSnapshot, explanations: ExplanationInputs | AttributionUnavailable
) -> ExplanationReference | AttributionUnavailable:
    if isinstance(explanations, AttributionUnavailable):
        if explanations.prediction_id != snapshot.prediction_id:
            raise ExportContractError(
                f"AttributionUnavailable.prediction_id {explanations.prediction_id!r} does not "
                f"match snapshot.prediction_id {snapshot.prediction_id!r}"
            )
        return explanations
    if explanations.prediction_id != snapshot.prediction_id:
        raise ExportContractError(
            f"ExplanationInputs.prediction_id {explanations.prediction_id!r} does not match "
            f"snapshot.prediction_id {snapshot.prediction_id!r}"
        )
    if explanations.prediction_content_digest != snapshot.content_digest():
        raise ExportContractError(
            "ExplanationInputs.prediction_content_digest does not match this snapshot's own "
            "content_digest() — the supplied explanation belongs to a different prediction "
            "content and must not be exported alongside this snapshot"
        )
    return ExplanationReference(
        prediction_id=explanations.prediction_id,
        reproducibility_digest=explanations.reproducibility_digest,
        method_id=explanations.method_id,
        method_version=explanations.method_version,
    )


def build_export(
    snapshot: PredictionSnapshot,
    eligibility: EligibilityResult,
    *,
    gate_p1_activated: bool,
    explanations: ExplanationInputs | AttributionUnavailable,
) -> ExportablePrediction:
    """Build the AVAILABLE-case SPEC-045 export from a valid ``snapshot``.

    Mirrors ``snapshot``'s three probabilities, fair odds and uncertainty summary verbatim —
    never substitutes, smooths or recomputes any of them. ``eligibility`` and
    ``gate_p1_activated`` are mapped to :class:`PublicationEligibility` by
    :func:`map_eligibility_to_publication_status`; an ineligible lineage is still exported
    (ineligible predictions remain internally storable and evaluable — eligibility only marks
    status, it never blocks construction). There is no ``recommendation`` parameter: the
    result's ``recommendation_status`` is always ``RecommendationStatus.NOT_EVALUATED``.
    """
    runners = sorted(snapshot.probabilities.runners, key=lambda r: r.runner_id)
    runner_exports = tuple(_export_runner(r, snapshot.fair_odds) for r in runners)
    publication_status = map_eligibility_to_publication_status(
        eligibility, gate_p1_activated=gate_p1_activated
    )
    explanation_ref = _explanation_reference(snapshot, explanations)
    return ExportablePrediction(
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        prediction_id=snapshot.prediction_id,
        race_id=snapshot.race_id,
        market_id=snapshot.market_id,
        generated_at_utc=snapshot.generated_at.wall_utc,
        available_to_consumer_at_utc=snapshot.available_to_consumer_at_utc,
        decision_horizon=snapshot.decision_horizon,
        runner_probabilities=runner_exports,
        fair_odds=dict(snapshot.fair_odds),
        uncertainty=snapshot.uncertainty,
        model_lineage_digest=snapshot.model_lineage_digest,
        feature_lineage_digest=snapshot.feature_lineage_digest,
        source_lineage_digest=snapshot.source_lineage_digest,
        forecast_availability=ForecastAvailability.AVAILABLE,
        publication_eligibility=publication_status,
        rights_registry_version=eligibility.rights_registry_version,
        recommendation_status=RecommendationStatus.NOT_EVALUATED,
        explanations=explanation_ref,
    )


def build_unavailable(
    race_id: str,
    market_id: str,
    availability: ForecastAvailability,
    reason: str,
    *,
    generated_at_utc: datetime,
) -> UnavailableForecast:
    """Build the UNAVAILABLE/WITHHELD-case SPEC-045 export.

    ``availability`` MUST be one of the ``UNAVAILABLE_*``/``WITHHELD_*`` members — passing
    ``ForecastAvailability.AVAILABLE`` is refused (use :func:`build_export` instead). There is
    no ``recommendation`` parameter: the result's ``recommendation_status`` is always
    ``RecommendationStatus.NOT_EVALUATED``.
    """
    return UnavailableForecast(
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        race_id=race_id,
        market_id=market_id,
        generated_at_utc=generated_at_utc,
        forecast_availability=availability,
        reason=reason,
        recommendation_status=RecommendationStatus.NOT_EVALUATED,
    )
