"""SPEC-091: the trial ledger — an immutable, append-only record per experiment.

SPECIFICATION.md §9.7 requires every experiment to get an immutable record carrying (in
its exact vocabulary): ``experiment_id, hypothesis, decision_unit, primary_endpoint,
secondary_endpoints, minimum_economic_effect, training_window, validation_window,
lockbox_window, exclusions, feature_set_hash, model_hash, execution_policy_hash,
number_of_prior_trials, stopping_rule, alpha_budget, result, confidence_interval,
decision, reviewer``. "The first several versions will fail" is realistic and creates a
multiple-testing problem: changing features, windows, tracks, exclusions and
hyperparameters until a gate passes will eventually manufacture a false positive. The
ledger is what makes ``number_of_prior_trials`` (and therefore the evaluator's exact
multiplicity arithmetic in ``l8_evidence.gates.evaluator.evaluate``) honest rather than
caller-asserted.

Two immutable record types, not one, because §9.4's pre-registration discipline is a
structural fact, not a formatting choice: an experiment is registered BEFORE observation
(hypothesis, endpoints, windows, hashes, stopping rule, alpha budget — everything a
multiple-testing accounting needs) and only LATER completed with what was actually
observed (result, confidence interval, decision, reviewer). Modelling this as one mutable
record would require editing "hypothesis" after the fact to attach a result — exactly the
kind of edit an append-only evidence ledger must refuse by construction, not by policy.

* :class:`TrialRegistration` — the pre-registration block. Immutable once built; the
  fields that would let a post-hoc rationalisation quietly change a boundary (hypothesis,
  endpoints, windows, hashes, stopping rule, alpha budget) live ONLY here and are never
  touched again.
* :class:`TrialCompletion` — the completion block. References its registration by
  ``registration_digest`` (a content hash — see :meth:`TrialRegistration.content_digest`)
  so :meth:`TrialLedger.complete` can refuse a completion that does not point at the
  EXACT pre-registration content already stored (the tamper guard: a completion can never
  silently ride in against a boundary that was quietly edited between registration and
  completion, because there is no path to edit it — the digest simply would not match).

ADR 0011 forward dependency (recorded against this module's slice in ``docs/PROGRESS.md``
and in the SPEC-093 gate evaluator's own docstring): §9.7's flat ``reviewer`` field is
promoted here to :class:`Attestation` (``reviewer`` identity plus ``attested_at_utc``) —
attestation PROVENANCE, not just a name string, so a completed trial's sign-off carries
the same "who and when" discipline as every other dual-clock record in this codebase.

Ambiguity resolutions taken while drafting this slice (see the task's final report for
the full list):

* ``decision_unit`` is validated against the governed closed set
  ``PERMITTED_DECISION_UNITS`` (originally exactly ``"race"`` per §9.7's template;
  widened to ``{"race", "match"}`` by founder-approved correction 0003, ADR 0017).
  The market choice set is the unit of analysis, never the individual selection — a
  selection-level trial ledger entry would misrepresent the very thing the
  multiplicity/clustering discipline depends on.
* ``ABANDONED`` has no ``l8_evidence.gates.outcomes.GateOutcome`` counterpart. It is a
  FIFTH :class:`TrialDecision` member (the other four share GateOutcome's exact string
  values, checked by a dedicated test, without literally reusing that sealed four-member
  enum) for an experiment stopped WITHOUT ever running the deterministic evaluator —
  deprioritised, superseded, or operationally abandoned. Because no evaluation ever ran,
  an ``ABANDONED`` completion carries no ``result``/``confidence_interval``; every other
  decision requires both (an evidence-backed CONTINUE still has an interim bound).
* ``number_of_prior_trials`` is supplied by the CALLER on the registration object (as
  §9.7 names it a field of the record itself) but is enforced, not caller-asserted:
  :meth:`TrialLedger.register` recomputes the true prior count from the ledger's own
  append-only history and refuses any mismatch. A caller who wants to register honestly
  calls :meth:`TrialLedger.prior_trial_count` first to learn the number to declare.
* ``lockbox_window`` overlap is checked against ``training_window`` and
  ``validation_window`` only (exactly what the task names) — not between
  ``training_window`` and ``validation_window`` themselves, which is a modelling/
  cross-fitting concern that belongs to ``l4_pricing`` (SPEC-031), not to this ledger's
  own record-shape validation.
* This module does not itself call ``l8_evidence.gates.evaluator.evaluate`` — it only
  exposes ``prior_trials_for_evaluation``/``alpha_budget_for_evaluation`` so a caller can
  build a ``PreRegistration`` for that evaluator. Wiring a specific completion's
  ``decision`` to a specific ``GateResult.outcome`` is a research-pipeline concern outside
  this module's scope; the round-trip test in this slice proves the values the ledger
  hands back actually drive the evaluator's exact multiplicity arithmetic.

No LLM computes, adjusts or approves any field in this module. Every value here is either
supplied directly by the caller (a human-run research pipeline) or deterministic
arithmetic performed in this file (content digests, prior-trial counting).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from l8_evidence.prediction_snapshots import DualClockTimestamp

__all__ = [
    "TrialLedgerError",
    "TrialValidationError",
    "DuplicateExperimentError",
    "UnknownExperimentError",
    "DoubleCompletionError",
    "PriorTrialCountError",
    "RegistrationDigestMismatchError",
    "TrialDecision",
    "DateWindow",
    "Exclusion",
    "Attestation",
    "TrialRegistration",
    "TrialCompletion",
    "TrialLedger",
    "prior_trials_for_evaluation",
    "alpha_budget_for_evaluation",
]

_ZERO = Decimal(0)
_ONE = Decimal(1)
_SHA256_PREFIX = "sha256:"
_SHA256_HEX_LEN = 64
#: Governed correction 0003 (founder approved, 2026-07-17): the decision unit is the
#: sport's mutually exclusive market choice set — a CLOSED, adapter-declared vocabulary,
#: not a free string and not racing-only. "race" (horse racing) and "match" (tennis) are
#: the two approved units; a future sport adds its unit HERE via a further governed
#: change, never at runtime. The unit of analysis is always the choice-set/event, never
#: the individual selection ("runner" is refused deliberately).
PERMITTED_DECISION_UNITS: frozenset[str] = frozenset({"race", "match"})


class TrialLedgerError(ValueError):
    """Base for every SPEC-091 trial-ledger error."""


class TrialValidationError(TrialLedgerError):
    """A record's own fields are internally inconsistent (§9.7 shape)."""


class DuplicateExperimentError(TrialLedgerError):
    """``register`` was called twice for the same ``experiment_id``."""


class UnknownExperimentError(TrialLedgerError):
    """An operation named an ``experiment_id`` that was never registered."""


class DoubleCompletionError(TrialLedgerError):
    """``complete`` was called twice for the same ``experiment_id``."""


class PriorTrialCountError(TrialLedgerError):
    """The claimed ``number_of_prior_trials`` does not match the ledger's own count.

    This is the enforcement point that keeps multiplicity accounting honest: the caller
    never gets to assert how many prior trials exist, only the ledger's own append-only
    history does.
    """


class RegistrationDigestMismatchError(TrialLedgerError):
    """A completion's ``registration_digest`` does not match the stored registration.

    The tamper guard: a completion can only be accepted against the EXACT pre-registered
    content, never a silently-edited variant of it.
    """


class TrialDecision(Enum):
    """The trial's final recorded decision (§9.7 ``decision``).

    A fresh five-member enum rather than an alias of
    ``l8_evidence.gates.outcomes.GateOutcome``: ``GateOutcome`` is sealed at four members
    (once an ``Enum`` declares members it cannot be subclassed to add a fifth) and refuses
    ``bool()`` outright, but a completed trial has a possibility ``GateOutcome`` cannot
    represent — ``ABANDONED``, an experiment stopped WITHOUT ever running the
    deterministic evaluator. The four shared members carry IDENTICAL string values to
    ``GateOutcome``'s (checked by a dedicated test in this slice) purely so a completed
    trial's decision can be logged and compared alongside a ``GateResult.outcome.value``
    without translation — this enum does not import or depend on ``GateOutcome`` at all.
    """

    PASS = "PASS"
    CONTINUE = "CONTINUE"
    FAIL_HARM = "FAIL_HARM"
    FAIL_FUTILITY = "FAIL_FUTILITY"
    ABANDONED = "ABANDONED"


def _require_sha256(value: str, where: str) -> None:
    if not value.startswith(_SHA256_PREFIX):
        raise TrialValidationError(f"{where}: must start with {_SHA256_PREFIX!r}, got {value!r}")
    hex_part = value[len(_SHA256_PREFIX) :]
    if len(hex_part) != _SHA256_HEX_LEN or any(c not in "0123456789abcdef" for c in hex_part):
        raise TrialValidationError(
            f"{where}: must be {_SHA256_PREFIX}<{_SHA256_HEX_LEN} lowercase hex chars>, got {value!r}"
        )


def _require_nonempty(value: str, where: str) -> None:
    if not value or not value.strip():
        raise TrialValidationError(f"{where} must be a non-empty string")


def _require_utc(value: datetime, where: str) -> None:
    if value.tzinfo is None:
        raise TrialValidationError(f"{where} must be timezone-aware (UTC)")
    if value.utcoffset() != timezone.utc.utcoffset(None):
        raise TrialValidationError(f"{where} must be in UTC")


@dataclass(frozen=True)
class DateWindow:
    """A closed ``[start_date, end_date]`` calendar-day window."""

    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise TrialValidationError(
                f"window start_date {self.start_date} is after end_date {self.end_date}"
            )

    def overlaps(self, other: "DateWindow") -> bool:
        """Whether this window shares at least one calendar day with ``other``."""
        return self.start_date <= other.end_date and other.start_date <= self.end_date


@dataclass(frozen=True)
class Exclusion:
    """One excluded item, always carrying its knowledge-time reason (evidence.md).

    "Missing data produces an explicit exclusion with a knowledge-time, never a
    disappearance" — every exclusion here MUST carry a rationale; there is no bare
    "rule" field that can silently drop a race without explaining, as of when, it was
    known to be ineligible.
    """

    rule: str
    knowledge_time_rationale: str

    def __post_init__(self) -> None:
        _require_nonempty(self.rule, "Exclusion.rule")
        _require_nonempty(self.knowledge_time_rationale, "Exclusion.knowledge_time_rationale")


@dataclass(frozen=True)
class Attestation:
    """Attestation provenance for a completed trial (ADR 0011 forward dependency).

    Replaces §9.7's flat ``reviewer`` string with WHO reviewed and WHEN, matching this
    codebase's dual-clock/attestation conventions elsewhere (SPEC-004, SPEC-037's
    ``generated_at``).
    """

    reviewer: str
    attested_at_utc: datetime

    def __post_init__(self) -> None:
        _require_nonempty(self.reviewer, "Attestation.reviewer")
        _require_utc(self.attested_at_utc, "Attestation.attested_at_utc")


def _jsonable(value: Any) -> Any:
    """Recursively convert a value into a JSON-serialisable, canonically-ordered form.

    Mirrors ``l8_evidence.prediction_snapshots._jsonable`` (house style): Decimals render
    via ``str`` (never float ``repr``), enums via their ``.value``, dates/datetimes via
    ISO 8601, mappings with sorted keys at every nesting level, so the digest is stable
    across processes and Python versions.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    return value


def _content_digest(record: Any) -> str:
    payload = _jsonable(asdict(record))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return _SHA256_PREFIX + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TrialRegistration:
    """The §9.7 pre-registration block: everything declared BEFORE observation.

    Never edited after :meth:`TrialLedger.register` accepts it — there is no setter, no
    update method anywhere in this module, and :class:`TrialCompletion` can only be
    accepted against this object's exact ``content_digest()``.
    """

    experiment_id: str
    hypothesis: str
    decision_unit: str
    primary_endpoint: str
    secondary_endpoints: tuple[str, ...]
    minimum_economic_effect: Decimal
    training_window: DateWindow
    validation_window: DateWindow
    lockbox_window: DateWindow
    exclusions: tuple[Exclusion, ...]
    feature_set_hash: str
    model_hash: str
    execution_policy_hash: str
    number_of_prior_trials: int
    stopping_rule: str
    alpha_budget: Decimal
    recorded_at: DualClockTimestamp

    def __post_init__(self) -> None:
        _require_nonempty(self.experiment_id, "experiment_id")
        _require_nonempty(self.hypothesis, "hypothesis")
        if self.decision_unit not in PERMITTED_DECISION_UNITS:
            raise TrialValidationError(
                f"decision_unit must be one of {sorted(PERMITTED_DECISION_UNITS)} (the "
                "market choice-set is the unit of analysis, never the individual "
                f"selection); got {self.decision_unit!r}"
            )
        _require_nonempty(self.primary_endpoint, "primary_endpoint")
        for i, endpoint in enumerate(self.secondary_endpoints):
            _require_nonempty(endpoint, f"secondary_endpoints[{i}]")
        if self.minimum_economic_effect <= _ZERO:
            raise TrialValidationError(
                f"minimum_economic_effect must be positive, got {self.minimum_economic_effect}"
            )
        if self.lockbox_window.overlaps(self.training_window):
            raise TrialValidationError(
                "lockbox_window overlaps training_window — inspecting the lockbox during "
                "development burns it (evidence.md); a ledger record must not even describe "
                "a design that would do so"
            )
        if self.lockbox_window.overlaps(self.validation_window):
            raise TrialValidationError(
                "lockbox_window overlaps validation_window — inspecting the lockbox during "
                "development burns it (evidence.md); a ledger record must not even describe "
                "a design that would do so"
            )
        for name, value in (
            ("feature_set_hash", self.feature_set_hash),
            ("model_hash", self.model_hash),
            ("execution_policy_hash", self.execution_policy_hash),
        ):
            _require_sha256(value, name)
        if self.number_of_prior_trials < 0:
            raise TrialValidationError(
                f"number_of_prior_trials must be non-negative, got {self.number_of_prior_trials}"
            )
        _require_nonempty(self.stopping_rule, "stopping_rule")
        if not (_ZERO < self.alpha_budget < _ONE):
            raise TrialValidationError(
                f"alpha_budget must lie strictly inside (0, 1), got {self.alpha_budget}"
            )

    def content_digest(self) -> str:
        """Deterministic ``sha256:<hex>`` over every field, canonically serialised.

        The tamper-guard anchor: :class:`TrialCompletion.registration_digest` must equal
        this exact value for :meth:`TrialLedger.complete` to accept a completion.
        """
        return _content_digest(self)


@dataclass(frozen=True)
class TrialCompletion:
    """The §9.7 completion block: what was actually observed, decided and signed off.

    ``result``/``confidence_interval`` are required for every decision EXCEPT
    ``ABANDONED`` (an abandoned trial never ran the evaluator, so it has nothing to
    report — fabricating a result for it would be exactly the "silent degradation" the
    project's rules forbid).
    """

    experiment_id: str
    registration_digest: str
    result: Decimal | None
    confidence_interval: tuple[Decimal, Decimal] | None
    decision: TrialDecision
    attestation: Attestation
    completed_at: DualClockTimestamp

    def __post_init__(self) -> None:
        _require_nonempty(self.experiment_id, "experiment_id")
        _require_sha256(self.registration_digest, "registration_digest")
        if not isinstance(self.decision, TrialDecision):
            raise TrialValidationError(
                f"decision must be a TrialDecision member, got {self.decision!r}"
            )
        if self.decision is TrialDecision.ABANDONED:
            if self.result is not None:
                raise TrialValidationError("an ABANDONED completion must not carry a result")
            if self.confidence_interval is not None:
                raise TrialValidationError(
                    "an ABANDONED completion must not carry a confidence_interval"
                )
        else:
            if self.result is None:
                raise TrialValidationError(
                    f"a {self.decision.value} completion must carry a result"
                )
            if self.confidence_interval is None:
                raise TrialValidationError(
                    f"a {self.decision.value} completion must carry a confidence_interval"
                )
            lower, upper = self.confidence_interval
            if lower > upper:
                raise TrialValidationError(
                    f"confidence_interval lower {lower} exceeds upper {upper}"
                )

    def content_digest(self) -> str:
        """Deterministic ``sha256:<hex>`` over every field, canonically serialised."""
        return _content_digest(self)


class TrialLedger:
    """The append-only SPEC-091 ledger. No update/delete API exists anywhere on this type.

    Only two mutating operations exist: :meth:`register` (mint a new, immutable
    pre-registration) and :meth:`complete` (attach exactly one completion to an existing
    registration). Neither can alter a previously stored record — ``register`` refuses a
    duplicate ``experiment_id`` outright, and ``complete`` refuses a second completion for
    the same ``experiment_id`` and refuses a completion whose ``registration_digest``
    does not match the stored registration's own digest.
    """

    def __init__(self) -> None:
        self._registrations: dict[str, TrialRegistration] = {}
        self._registration_order: list[str] = []
        self._completions: dict[str, TrialCompletion] = {}

    def prior_trial_count(self) -> int:
        """How many experiments this ledger has registered so far.

        Call this BEFORE building the next :class:`TrialRegistration` to learn the
        ``number_of_prior_trials`` value :meth:`register` will actually accept.
        """
        return len(self._registration_order)

    def register(self, registration: TrialRegistration) -> None:
        """Append a new pre-registration. Refuses a duplicate id or a wrong prior count."""
        if registration.experiment_id in self._registrations:
            raise DuplicateExperimentError(
                f"experiment_id {registration.experiment_id!r} is already registered"
            )
        actual_prior_trials = self.prior_trial_count()
        if registration.number_of_prior_trials != actual_prior_trials:
            raise PriorTrialCountError(
                f"experiment {registration.experiment_id!r} claims "
                f"number_of_prior_trials={registration.number_of_prior_trials}, but the "
                f"ledger has registered {actual_prior_trials} experiment(s) so far; call "
                "prior_trial_count() before building the registration"
            )
        self._registrations[registration.experiment_id] = registration
        self._registration_order.append(registration.experiment_id)

    def complete(self, completion: TrialCompletion) -> None:
        """Attach a completion to its registration. Refuses unknown/duplicate/tampered."""
        registration = self._registrations.get(completion.experiment_id)
        if registration is None:
            raise UnknownExperimentError(
                f"experiment_id {completion.experiment_id!r} was never registered"
            )
        if completion.experiment_id in self._completions:
            raise DoubleCompletionError(
                f"experiment_id {completion.experiment_id!r} is already completed"
            )
        expected_digest = registration.content_digest()
        if completion.registration_digest != expected_digest:
            raise RegistrationDigestMismatchError(
                f"experiment_id {completion.experiment_id!r}: completion's "
                f"registration_digest {completion.registration_digest!r} does not match the "
                f"stored registration's digest {expected_digest!r}"
            )
        # Same discipline as SPEC-037's chain guard: an evidence record formed later can
        # never be backdated to precede what it completes.
        if completion.completed_at.wall_utc < registration.recorded_at.wall_utc:
            raise TrialValidationError(
                f"experiment_id {completion.experiment_id!r}: completion is wall-clock "
                "backdated before its registration; a completion cannot precede what it completes"
            )
        self._completions[completion.experiment_id] = completion

    def registration_for(self, experiment_id: str) -> TrialRegistration:
        """The stored registration for ``experiment_id``. Raises if never registered."""
        registration = self._registrations.get(experiment_id)
        if registration is None:
            raise UnknownExperimentError(f"experiment_id {experiment_id!r} was never registered")
        return registration

    def completion_for(self, experiment_id: str) -> TrialCompletion | None:
        """The stored completion for ``experiment_id``, or ``None`` if not yet completed.

        Raises :class:`UnknownExperimentError` if ``experiment_id`` was never registered at
        all — distinct from "registered but not yet completed".
        """
        if experiment_id not in self._registrations:
            raise UnknownExperimentError(f"experiment_id {experiment_id!r} was never registered")
        return self._completions.get(experiment_id)

    def experiment_ids(self) -> tuple[str, ...]:
        """Every registered ``experiment_id``, in registration order."""
        return tuple(self._registration_order)


def prior_trials_for_evaluation(ledger: TrialLedger, experiment_id: str) -> int:
    """``number_of_prior_trials`` for ``experiment_id``, for building a gate ``PreRegistration``.

    This is the ledger-side half of "gate evaluation MUST read it" (SPEC-091): a research
    pipeline calls this (and :func:`alpha_budget_for_evaluation`) to populate
    ``l8_evidence.gates.experiment.PreRegistration`` before calling
    ``l8_evidence.gates.evaluator.evaluate``, so the evaluator's exact multiplicity
    arithmetic is driven by the ledger's own append-only count, never by a value the
    caller invents at evaluation time.
    """
    return ledger.registration_for(experiment_id).number_of_prior_trials


def alpha_budget_for_evaluation(ledger: TrialLedger, experiment_id: str) -> Decimal:
    """``alpha_budget`` for ``experiment_id``, for building a gate ``PreRegistration``.

    See :func:`prior_trials_for_evaluation` — the same ledger-to-evaluator wiring, for the
    other multiplicity-accounting input.
    """
    return ledger.registration_for(experiment_id).alpha_budget
