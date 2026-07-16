"""SPEC-037: immutable prediction snapshots with forecast vintage lineage.

Append-only snapshots recording what the platform believed at a specific time. A later
prediction is always a NEW ``prediction_id``; earlier snapshots are never updated in place —
there is no update/delete API in this module at all, by construction, not by convention.

Post-outcome data can never enter a snapshot: :class:`PredictionSnapshot` simply declares no
result/BSP/settlement fields (enforced by a dataclass-field-name test in the test suite, not
by a runtime guard invented on top of the spec). Results, BSP, settlement and future prices
join only at grading time in :mod:`l8_evidence`'s outcome-joined ledgers (SPEC-038), never
here.

This module MUST NOT import anything from ``l5_decision``, ``l5b_risk``, ``l6_broker`` or
``l7_settle`` — :class:`UncertaintySummary`'s ``central`` value is a diagnostic midpoint,
distinct from the trading conservative lower bound (``l5_decision.ev.WinProbabilityLowerBound``,
SPEC-050/SPEC-034), and must never be convertible to or usable as that type. Keeping the import
graph clean is the enforcement point a static architecture check can verify; this module's own
docstring says so explicitly so the check has a stated invariant to hold it to.

No LLM creates, alters, smooths or repairs any probability, fair-odds value or uncertainty
figure in this module — every value here is a direct passthrough of SPEC-036 probability
objects, SPEC-044 licensing eligibility results, and deterministic arithmetic performed in this
file (fair-odds inversion, hashing, digesting).

Ambiguity resolutions taken while drafting this slice (see the task's final report for the
full list):

* Fair odds are derived from ``p_combined`` when present in the race's
  :class:`~l4_pricing.probability_outputs.RaceProbabilityOutputs`, falling back to
  ``p_market_info`` and then ``p_fundamental`` only when the more market-aware kind is
  race-wide absent — SPEC-037 does not name which of the three probabilities backs "fair
  odds", and consuming whichever kind is actually present (in that priority order) keeps the
  function total over the SPEC-036 missingness contract instead of failing races that
  legitimately price only p_fundamental.
* ``vintage_type`` <-> ``update_reason`` is a closed mapping this module owns (see
  ``_ALLOWED_REASONS_FOR_VINTAGE`` below), since the spec names both vocabularies but not
  their pairing.
* "Chains must be linear" is read as: at most one snapshot may ever declare a given
  ``prediction_id`` as its ``supersedes_prediction_id`` — a fork is refused outright in v1.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from enum import Enum
from typing import Any, Mapping, Sequence

from governance.output_rights import EligibilityResult, EligibilityVocabulary
from l4_pricing.probability_outputs import MissingProbabilityError, RaceProbabilityOutputs

__all__ = [
    "VintageType",
    "UpdateReason",
    "DualClockTimestamp",
    "MarketStateSnapshot",
    "UncertaintySummary",
    "PredictionSnapshot",
    "SnapshotStore",
    "SnapshotValidationError",
    "SnapshotChainError",
    "DuplicatePredictionError",
    "build_active_runner_set_hash",
    "build_fair_odds",
]

_SCHEMA_VERSION_PATTERN_HINT = "prediction-snapshot-v1"
_FAIR_ODDS_QUANTUM = Decimal("0.0001")


class SnapshotValidationError(ValueError):
    """A snapshot's own fields are internally inconsistent (SPEC-037)."""


class SnapshotChainError(ValueError):
    """A snapshot is inconsistent with the revision chain already held by a store."""


class DuplicatePredictionError(ValueError):
    """A snapshot with this ``prediction_id`` already exists in the store."""


class VintageType(Enum):
    """SPEC-037's closed forecast-vintage vocabulary."""

    INITIAL = "INITIAL"
    UPDATED = "UPDATED"
    FINAL_APPROVED_HORIZON = "FINAL_APPROVED_HORIZON"
    CORRECTION = "CORRECTION"


class UpdateReason(Enum):
    """Deterministic update reasons a superseding snapshot must cite.

    Not named by SPEC-037 verbatim; this is the closed enum this module owns so that
    ``update_reason`` is always one of a fixed, auditable set rather than free text.
    """

    NON_RUNNER = "NON_RUNNER"
    MARKET_STATE_REFRESH = "MARKET_STATE_REFRESH"
    MODEL_REVISION = "MODEL_REVISION"
    HORIZON_FINALISED = "HORIZON_FINALISED"
    DATA_CORRECTION = "DATA_CORRECTION"


_ALLOWED_REASONS_FOR_VINTAGE: Mapping[VintageType, frozenset[UpdateReason]] = {
    VintageType.UPDATED: frozenset(
        {UpdateReason.NON_RUNNER, UpdateReason.MARKET_STATE_REFRESH, UpdateReason.MODEL_REVISION}
    ),
    VintageType.FINAL_APPROVED_HORIZON: frozenset({UpdateReason.HORIZON_FINALISED}),
    VintageType.CORRECTION: frozenset({UpdateReason.DATA_CORRECTION}),
}


@dataclass(frozen=True)
class DualClockTimestamp:
    """A single instant on both clocks (SPEC-004 style): UTC wall clock + monotonic ns.

    Wall clock can jump backwards under NTP; nothing in this module compares monotonic values
    across snapshots from different processes — the monotonic value is carried purely as an
    evidentiary generation-order signal alongside the wall clock, never used alone for
    cross-process latency arithmetic (that is SPEC-004's ``latency_ns``, not this module's job).
    """

    wall_utc: datetime
    monotonic_ns: int

    def __post_init__(self) -> None:
        if self.wall_utc.tzinfo is None:
            raise SnapshotValidationError("wall_utc must be timezone-aware (UTC)")
        if self.wall_utc.utcoffset() != timezone.utc.utcoffset(None):
            raise SnapshotValidationError("wall_utc must be in UTC")


@dataclass(frozen=True)
class MarketStateSnapshot:
    """Market state fields as-of the moment this prediction was generated."""

    market_status: str
    in_play: bool
    number_of_active_runners: int
    total_matched: Decimal

    def __post_init__(self) -> None:
        if not self.market_status or not self.market_status.strip():
            raise SnapshotValidationError("market_status must be non-empty")
        if self.in_play:
            raise SnapshotValidationError("no in-play market state may back a pre-off snapshot")
        if self.number_of_active_runners <= 0:
            raise SnapshotValidationError("number_of_active_runners must be positive")
        if self.total_matched < Decimal(0):
            raise SnapshotValidationError("total_matched must be non-negative")


@dataclass(frozen=True)
class UncertaintySummary:
    """A diagnostic uncertainty summary: method + optional lower/central/upper Decimals.

    ``central`` is a diagnostic midpoint, DISTINCT from the trading conservative lower bound
    consumed by ``l5_decision`` (SPEC-050/SPEC-034/SPEC-037). This type deliberately shares no
    field, base class or conversion path with ``l5_decision.ev.WinProbabilityLowerBound`` —
    there is no ``__float__``-style coercion and no import of that module here at all.
    """

    method: str
    lower: Decimal | None
    central: Decimal | None
    upper: Decimal | None

    def __post_init__(self) -> None:
        if not self.method or not self.method.strip():
            raise SnapshotValidationError("uncertainty method must be non-empty")
        if self.lower is not None and self.central is not None and self.lower > self.central:
            raise SnapshotValidationError("lower must not exceed central")
        if self.central is not None and self.upper is not None and self.central > self.upper:
            raise SnapshotValidationError("central must not exceed upper")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise SnapshotValidationError("lower must not exceed upper")


def build_active_runner_set_hash(runner_ids: Sequence[int]) -> str:
    """Deterministic ``sha256:<hex>`` over the SORTED set of active runner ids."""
    if not runner_ids:
        raise SnapshotValidationError("active runner set must not be empty")
    if len(set(runner_ids)) != len(runner_ids):
        raise SnapshotValidationError("active runner set must not contain duplicate runner ids")
    canonical = ",".join(str(rid) for rid in sorted(runner_ids))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_fair_odds(race: RaceProbabilityOutputs) -> dict[int, Decimal]:
    """Deterministic fair odds (Decimal ``1/p``) for every runner in ``race``.

    Priority order p_combined -> p_market_info -> p_fundamental (see module docstring for the
    ambiguity resolution): the first kind that is race-wide present (SPEC-036 guarantees a kind
    is either fully present or fully absent across the race) backs the fair-odds figure.
    Quantized to ``_FAIR_ODDS_QUANTUM`` (4 dp) with ROUND_HALF_EVEN — banker's rounding, chosen
    for its lack of systematic bias, applied identically every time the same probability is
    inverted (this is the "document the rounding" requirement).
    """
    for accessor in ("combined", "market_info", "fundamental"):
        try:
            probs = {r.runner_id: getattr(r, accessor)().probability for r in race.runners}
        except MissingProbabilityError:
            continue  # this kind is absent for the race; probe the next in priority order
        return {
            runner_id: (Decimal(1) / p).quantize(_FAIR_ODDS_QUANTUM, rounding=ROUND_HALF_EVEN)
            for runner_id, p in probs.items()
        }
    raise SnapshotValidationError(
        f"race {race.race_id!r}: no probability kind is race-wide present; cannot derive fair odds"
    )


def _jsonable(value: Any) -> Any:
    """Recursively convert a value into a JSON-serialisable, canonically-ordered form."""
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
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="python"))
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    return value


@dataclass(frozen=True)
class PredictionSnapshot:
    """One immutable SPEC-037 prediction snapshot.

    NO field on this dataclass names a race/settlement outcome, BSP or account result — this
    is the enforcement point for "post-outcome data can never enter a snapshot": there is
    simply nowhere on this type to put it. Grading joins happen downstream in SPEC-038's
    outcome-joined evidence ledger, never by mutating or extending this type.
    """

    prediction_id: str
    race_id: str
    market_id: str
    active_runner_set_hash: str
    generated_at: DualClockTimestamp
    decision_horizon: str
    market_state: MarketStateSnapshot
    probabilities: RaceProbabilityOutputs
    fair_odds: Mapping[int, Decimal]
    uncertainty: UncertaintySummary
    model_lineage_digest: str
    feature_lineage_digest: str
    source_lineage_digest: str
    publication_eligibility: EligibilityResult
    schema_version: str
    forecast_vintage_id: str
    vintage_type: VintageType
    supersedes_prediction_id: str | None
    update_reason: UpdateReason | None
    available_to_consumer_at_utc: datetime

    def __post_init__(self) -> None:
        if not self.prediction_id or not self.prediction_id.strip():
            raise SnapshotValidationError("prediction_id must be non-empty")
        if not self.race_id or not self.race_id.strip():
            raise SnapshotValidationError("race_id must be non-empty")
        if not self.market_id or not self.market_id.strip():
            raise SnapshotValidationError("market_id must be non-empty")
        if self.race_id != self.probabilities.race_id:
            raise SnapshotValidationError(
                f"race_id {self.race_id!r} does not match probabilities.race_id "
                f"{self.probabilities.race_id!r}"
            )
        expected_hash = build_active_runner_set_hash([r.runner_id for r in self.probabilities.runners])
        if self.active_runner_set_hash != expected_hash:
            raise SnapshotValidationError(
                "active_runner_set_hash does not match the sha256 of the sorted runner ids "
                f"actually present in probabilities: expected {expected_hash!r}, "
                f"got {self.active_runner_set_hash!r}"
            )
        if set(self.fair_odds) != {r.runner_id for r in self.probabilities.runners}:
            raise SnapshotValidationError("fair_odds must cover exactly the race's runner ids")
        for digest_name, digest_value in (
            ("model_lineage_digest", self.model_lineage_digest),
            ("feature_lineage_digest", self.feature_lineage_digest),
            ("source_lineage_digest", self.source_lineage_digest),
        ):
            if not digest_value.startswith("sha256:") or len(digest_value) != len("sha256:") + 64:
                raise SnapshotValidationError(f"{digest_name} must be a sha256:<hex> digest")
        if not self.decision_horizon or not self.decision_horizon.strip():
            raise SnapshotValidationError("decision_horizon must be non-empty")
        if not self.schema_version or not self.schema_version.strip():
            raise SnapshotValidationError("schema_version must be non-empty")
        if not self.forecast_vintage_id or not self.forecast_vintage_id.strip():
            raise SnapshotValidationError("forecast_vintage_id must be non-empty")
        if self.publication_eligibility.vocabulary is not EligibilityVocabulary.PUBLICATION:
            raise SnapshotValidationError(
                "publication_eligibility must be computed over the PUBLICATION vocabulary; "
                "an internal-research eligibility result never implies publication (SPEC-044)"
            )
        if self.available_to_consumer_at_utc.tzinfo is None:
            raise SnapshotValidationError("available_to_consumer_at_utc must be timezone-aware (UTC)")
        if self.available_to_consumer_at_utc.utcoffset() != timezone.utc.utcoffset(None):
            raise SnapshotValidationError("available_to_consumer_at_utc must be in UTC")
        # Knowledge-time ordering: a forecast cannot be available to any consumer before it
        # was generated. This is what makes "available_to_consumer_at_utc" an honest
        # knowledge-time and blocks backdated availability (hindsight rewriting).
        if self.available_to_consumer_at_utc < self.generated_at.wall_utc:
            raise SnapshotValidationError(
                "available_to_consumer_at_utc must not precede the generation wall-clock time"
            )

        if self.vintage_type is VintageType.INITIAL:
            if self.supersedes_prediction_id is not None:
                raise SnapshotValidationError("an INITIAL snapshot must not set supersedes_prediction_id")
            if self.update_reason is not None:
                raise SnapshotValidationError("an INITIAL snapshot must not set update_reason")
        else:
            if self.supersedes_prediction_id is None:
                raise SnapshotValidationError(
                    f"a {self.vintage_type.value} snapshot must set supersedes_prediction_id"
                )
            if self.supersedes_prediction_id == self.prediction_id:
                raise SnapshotValidationError("a snapshot must not supersede itself")
            if self.update_reason is None:
                raise SnapshotValidationError(f"a {self.vintage_type.value} snapshot must set update_reason")
            allowed = _ALLOWED_REASONS_FOR_VINTAGE[self.vintage_type]
            if self.update_reason not in allowed:
                raise SnapshotValidationError(
                    f"update_reason {self.update_reason.value} is not permitted for vintage_type "
                    f"{self.vintage_type.value} (allowed: {sorted(r.value for r in allowed)})"
                )

    def content_digest(self) -> str:
        """Deterministic ``sha256:<hex>`` over every field, canonically serialised.

        Same field values -> identical digest; any field change -> a different digest. Keys are
        sorted at every nesting level and Decimals are rendered via ``str`` (never ``repr`` of a
        float) so the digest is stable across processes and Python versions.
        """
        payload = _jsonable(asdict(self))
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SnapshotStore:
    """Append-only store of :class:`PredictionSnapshot`. No update/delete API exists here.

    ``latest_for`` and ``all_vintages`` are DERIVED by walking the supersession chain each
    call — there is no stored "latest" pointer to mutate, and no accessor here (or anywhere in
    this module) accepts a race/runner outcome, so no consumer can select the best-performing
    vintage after the fact through this store's API.
    """

    def __init__(self) -> None:
        # _by_id is the only authoritative state; _children_of and _root_of are convenience
        # indexes fully rebuildable from the snapshots themselves (re-appending the same
        # snapshots into a fresh store reproduces identical derived answers — tested).
        self._by_id: dict[str, PredictionSnapshot] = {}
        self._children_of: dict[str, str] = {}  # supersedes_prediction_id -> prediction_id
        self._root_of: dict[tuple[str, str], str] = {}  # (race_id, market_id) -> INITIAL id

    def append(self, snapshot: PredictionSnapshot) -> None:
        if snapshot.prediction_id in self._by_id:
            raise DuplicatePredictionError(
                f"prediction_id {snapshot.prediction_id!r} already exists in this store"
            )
        parent_id = snapshot.supersedes_prediction_id
        key = (snapshot.race_id, snapshot.market_id)
        if parent_id is None:
            # One INITIAL root per (race, market): an append-only store must never accept a
            # state its own reader would refuse — the refusal belongs here, not at read time.
            existing_root = self._root_of.get(key)
            if existing_root is not None:
                raise SnapshotChainError(
                    f"race {snapshot.race_id!r} market {snapshot.market_id!r} already has "
                    f"INITIAL snapshot {existing_root!r}; a later belief must supersede it, "
                    "not start a second chain"
                )
        else:
            parent = self._by_id.get(parent_id)
            if parent is None:
                raise SnapshotChainError(
                    f"snapshot {snapshot.prediction_id!r} supersedes unknown prediction_id {parent_id!r}"
                )
            if parent.race_id != snapshot.race_id or parent.market_id != snapshot.market_id:
                raise SnapshotChainError(
                    f"snapshot {snapshot.prediction_id!r} supersedes {parent_id!r} but their "
                    "race_id/market_id differ — a chain must stay within one race and market"
                )
            existing_child = self._children_of.get(parent_id)
            if existing_child is not None:
                raise SnapshotChainError(
                    f"prediction_id {parent_id!r} is already superseded by {existing_child!r}; "
                    "chains must be linear — a second supersession is refused in v1"
                )
            # Hindsight guard: a superseding snapshot (including CORRECTION) is a NEW belief
            # formed no earlier than its parent. A correction generated after the fact can
            # never be backdated to look like a forecast that was available pre-off.
            if snapshot.generated_at.wall_utc < parent.generated_at.wall_utc:
                raise SnapshotChainError(
                    f"snapshot {snapshot.prediction_id!r} is generated before its parent "
                    f"{parent_id!r}; a superseding vintage cannot be backdated"
                )
        self._by_id[snapshot.prediction_id] = snapshot
        if parent_id is not None:
            self._children_of[parent_id] = snapshot.prediction_id
        else:
            self._root_of[key] = snapshot.prediction_id

    def snapshot_by_id(self, prediction_id: str) -> PredictionSnapshot:
        snapshot = self._by_id.get(prediction_id)
        if snapshot is None:
            raise KeyError(f"no snapshot with prediction_id {prediction_id!r}")
        return snapshot

    def all_vintages(self, prediction_id: str) -> tuple[PredictionSnapshot, ...]:
        """Every snapshot in ``prediction_id``'s chain, in INITIAL-to-latest order."""
        current = self.snapshot_by_id(prediction_id)
        while current.supersedes_prediction_id is not None:
            current = self.snapshot_by_id(current.supersedes_prediction_id)
        chain = [current]
        while current.prediction_id in self._children_of:
            current = self.snapshot_by_id(self._children_of[current.prediction_id])
            chain.append(current)
        return tuple(chain)

    def latest_for(self, race_id: str, market_id: str) -> PredictionSnapshot | None:
        """The chain-derived latest snapshot for ``(race_id, market_id)``, or ``None``.

        Walks every root (INITIAL) snapshot matching ``(race_id, market_id)`` to the end of its
        chain. Never reads a stored mutable pointer — the answer is recomputed from the chain
        structure every call.
        """
        root_id = self._root_of.get((race_id, market_id))
        if root_id is None:
            return None
        return self.all_vintages(root_id)[-1]
