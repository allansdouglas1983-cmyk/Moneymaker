"""SPEC-094: typed experiment pre-registration templates (ADR 0017 S6, phase seven).

Five FUTURE experiments — a market-only baseline, surface-elo, weighted-elo,
bradley-terry, and the stage2-combined model — are registered here as typed, versioned
TEMPLATES that plug into the EXISTING evidence machinery: the SPEC-091 trial ledger
(:mod:`l8_evidence.trial_ledger`) and the SPEC-094 sample-size discipline
(:mod:`l8_evidence.sample_size`). A template names WHAT would be compared (candidate
family, baseline comparator, decision unit, primary endpoint wording); it can never say
HOW MUCH or HOW LONG. Running any of these experiments stays blocked on purchased data
and founder approval — no dataset exists, no model exists, and this module changes
neither fact.

The SPEC-094 discipline, enforced structurally rather than by prose:

* **No numeric constant exists anywhere in this module.** Minimum economically
  meaningful effect, power assumptions and the stopping rule are declared PER EXPERIMENT
  by a human BEFORE observation. A number baked into a template would be exactly the
  borrowed threshold SPECIFICATION.md rejects; the template type's fields are all
  strings, so it cannot even hold one.
* **A template cannot become a trial registration on its own.**
  :meth:`ExperimentTemplate.to_trial_registration_fields` raises a typed
  :class:`PreRegistrationIncompleteError` unless the caller supplies a
  :class:`PreRegisteredEndpoints` — a frozen record whose fields are all mandatory with
  no defaults, carrying the human-declared minimum effect, the
  :class:`l8_evidence.sample_size.PowerAssumptions` behind the derived sample size, and
  the stopping rule.
* **The declared minimum effect and the power derivation must agree.** The minimum
  economically meaningful effect IS the ``delta`` in SPEC-094's sample-size formula; a
  :class:`PreRegisteredEndpoints` whose ``minimum_economic_effect`` differs from its
  ``power_assumptions.delta`` is refused — two different numbers for the same declared
  quantity is exactly the inconsistency pre-registration exists to prevent. Positivity
  and range validation are inherited from ``PowerAssumptions``' own refusals, so no
  bound constant is restated here.
* **The vocabulary is the ledger's, not a parallel one.** ``decision_unit`` is validated
  against :data:`l8_evidence.trial_ledger.PERMITTED_DECISION_UNITS` (the closed,
  governed choice-set vocabulary — the unit of analysis is the mutually exclusive
  choice set, never the individual selection), and the produced field names are exactly
  the :class:`l8_evidence.trial_ledger.TrialRegistration` field names they feed.

ADR 0013 boundary: this module imports nothing from live execution, risk, broker or
settlement code, directly or transitively. No LLM computes, adjusts or approves any
value here; the module contains no numbers to compute, and every field a human must
supply is refused when absent, never defaulted.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from l8_evidence.sample_size import PowerAssumptions
from l8_evidence.trial_ledger import PERMITTED_DECISION_UNITS

__all__ = [
    "ExperimentTemplateError",
    "TemplateValidationError",
    "PreRegistrationIncompleteError",
    "PreRegisteredEndpoints",
    "ExperimentTemplate",
    "MARKET_ONLY_BASELINE_TEMPLATE",
    "SURFACE_ELO_TEMPLATE",
    "WEIGHTED_ELO_TEMPLATE",
    "BRADLEY_TERRY_TEMPLATE",
    "STAGE2_COMBINED_TEMPLATE",
    "ALL_EXPERIMENT_TEMPLATES",
]

_TEMPLATE_VERSION = "adr-0017-s6"

_BLOCKED_NOTE = (
    "Running this experiment stays blocked on purchased data and founder approval; the "
    "template only fixes the comparison's vocabulary before any observation exists."
)


class ExperimentTemplateError(ValueError):
    """Base for every SPEC-094 experiment-template error."""


class TemplateValidationError(ExperimentTemplateError):
    """A template's or endpoints record's own fields are invalid or inconsistent."""


class PreRegistrationIncompleteError(ExperimentTemplateError):
    """No human-supplied :class:`PreRegisteredEndpoints` was provided.

    The structural half of SPEC-094: a template alone can never produce trial
    registration fields, because the numeric endpoints it lacks must be declared by a
    human before observation — there is no default to fall back on.
    """


def _require_nonempty(value: object, where: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise TemplateValidationError(f"{where} must be a non-empty string, got {value!r}")


@dataclass(frozen=True)
class PreRegisteredEndpoints:
    """The human-declared numeric endpoints of one experiment. No field has a default.

    Attributes:
        minimum_economic_effect: The minimum economically meaningful effect on the
            paired decision-unit-level log-score scale, declared before observation. It
            MUST equal ``power_assumptions.delta`` — the same declared quantity drives
            both the ledger record and the sample-size derivation, and two different
            numbers for it are refused.
        power_assumptions: The :class:`l8_evidence.sample_size.PowerAssumptions` behind
            the experiment's derived sample size. Its own validation enforces ranges and
            positivity, so no bound is restated in this module.
        stopping_rule: The pre-registered stopping rule text (anytime-valid monitoring
            vocabulary; quoting the derived sample-size plan's content digest here is
            the documented SPEC-094 flow).
    """

    minimum_economic_effect: Decimal
    power_assumptions: PowerAssumptions
    stopping_rule: str

    def __post_init__(self) -> None:
        if not isinstance(self.minimum_economic_effect, Decimal):
            raise TemplateValidationError(
                "minimum_economic_effect must be a Decimal, got "
                f"{type(self.minimum_economic_effect)!r}"
            )
        if not isinstance(self.power_assumptions, PowerAssumptions):
            raise TemplateValidationError(
                "power_assumptions must be a PowerAssumptions, got "
                f"{type(self.power_assumptions)!r}"
            )
        _require_nonempty(self.stopping_rule, "stopping_rule")
        if self.minimum_economic_effect != self.power_assumptions.delta:
            raise TemplateValidationError(
                f"minimum_economic_effect {self.minimum_economic_effect} does not equal "
                f"power_assumptions.delta {self.power_assumptions.delta}; the minimum "
                "economically meaningful effect IS the delta the sample size was derived "
                "from — declaring two different numbers for the same quantity is refused"
            )


@dataclass(frozen=True)
class ExperimentTemplate:
    """One typed, versioned pre-registration template. Every field is a string.

    Deliberately incapable of holding a number: endpoints are declared per experiment by
    a human (:class:`PreRegisteredEndpoints`), never baked into a template.

    Attributes:
        template_id: Stable identifier for this template.
        template_version: Version string of the template vocabulary.
        description: What the experiment would compare, including the standing note that
            running it stays blocked on purchased data and founder approval.
        decision_unit: The unit of analysis; validated against the trial ledger's
            closed, governed vocabulary.
        candidate_model_family: String id of the candidate model family.
        baseline_comparator: String id of the baseline the candidate is compared to.
        primary_endpoint_description: Wording of the primary endpoint, in the paired
            decision-unit-level vocabulary the evidence layer already uses.
    """

    template_id: str
    template_version: str
    description: str
    decision_unit: str
    candidate_model_family: str
    baseline_comparator: str
    primary_endpoint_description: str

    def __post_init__(self) -> None:
        _require_nonempty(self.template_id, "template_id")
        _require_nonempty(self.template_version, "template_version")
        _require_nonempty(self.description, "description")
        _require_nonempty(self.decision_unit, "decision_unit")
        if self.decision_unit not in PERMITTED_DECISION_UNITS:
            raise TemplateValidationError(
                f"decision_unit must be one of {sorted(PERMITTED_DECISION_UNITS)} (the "
                "mutually exclusive choice set is the unit of analysis, never the "
                f"individual selection); got {self.decision_unit!r}"
            )
        _require_nonempty(self.candidate_model_family, "candidate_model_family")
        _require_nonempty(self.baseline_comparator, "baseline_comparator")
        _require_nonempty(self.primary_endpoint_description, "primary_endpoint_description")

    def to_trial_registration_fields(
        self, endpoints: PreRegisteredEndpoints | None
    ) -> Mapping[str, object]:
        """The template-determined subset of SPEC-091 ``TrialRegistration`` fields.

        Raises a typed :class:`PreRegistrationIncompleteError` when ``endpoints`` is
        absent — a template can NEVER produce registration fields on its own, because
        the numeric endpoints must be human-declared before observation (SPEC-094).

        Returns a read-only mapping whose keys are exactly the
        :class:`l8_evidence.trial_ledger.TrialRegistration` field names the template and
        endpoints determine (``hypothesis``, ``decision_unit``, ``primary_endpoint``,
        ``minimum_economic_effect``, ``stopping_rule``). The caller supplies everything
        experiment-specific the template cannot know — windows, hashes, exclusions,
        identifiers, the ledger-enforced prior-trial count and timestamps — and the
        ledger's own validation remains the authority on all of it.
        """
        if endpoints is None:
            raise PreRegistrationIncompleteError(
                f"template {self.template_id!r}: no PreRegisteredEndpoints supplied — "
                "minimum effect, power assumptions and stopping rule are declared by a "
                "human before observation; a template alone cannot register a trial"
            )
        if not isinstance(endpoints, PreRegisteredEndpoints):
            raise TemplateValidationError(
                f"endpoints must be a PreRegisteredEndpoints, got {type(endpoints)!r}"
            )
        hypothesis = (
            f"candidate {self.candidate_model_family} improves the pre-registered "
            f"primary endpoint over baseline {self.baseline_comparator} at the "
            f"{self.decision_unit} level"
        )
        return MappingProxyType(
            {
                "hypothesis": hypothesis,
                "decision_unit": self.decision_unit,
                "primary_endpoint": self.primary_endpoint_description,
                "minimum_economic_effect": endpoints.minimum_economic_effect,
                "stopping_rule": endpoints.stopping_rule,
            }
        )


_PRIMARY_ENDPOINT = (
    "paired decision-unit-level log-score difference against the baseline comparator, "
    "clustered by the sport adapter's declared clustering unit"
)

#: The baseline-establishing experiment: the frozen market-information price evaluated
#: as a forecast in its own right. Its comparator is itself — this run establishes the
#: reference forecast whose paired differences every later candidate is measured
#: against; it is registered in the same ledger so its trial counts toward multiplicity.
MARKET_ONLY_BASELINE_TEMPLATE = ExperimentTemplate(
    template_id="exp-template-market-only-baseline",
    template_version=_TEMPLATE_VERSION,
    description=(
        "Establish the market-only baseline: the frozen market-information price "
        "evaluated as a forecast, the reference every candidate model family is later "
        f"compared against. {_BLOCKED_NOTE}"
    ),
    decision_unit="match",
    candidate_model_family="market-only-baseline",
    baseline_comparator="market-only-baseline",
    primary_endpoint_description=_PRIMARY_ENDPOINT,
)

SURFACE_ELO_TEMPLATE = ExperimentTemplate(
    template_id="exp-template-surface-elo",
    template_version=_TEMPLATE_VERSION,
    description=(
        "Compare a surface-conditioned Elo rating family against the market-only "
        f"baseline. No such model exists yet. {_BLOCKED_NOTE}"
    ),
    decision_unit="match",
    candidate_model_family="surface-elo",
    baseline_comparator="market-only-baseline",
    primary_endpoint_description=_PRIMARY_ENDPOINT,
)

WEIGHTED_ELO_TEMPLATE = ExperimentTemplate(
    template_id="exp-template-weighted-elo",
    template_version=_TEMPLATE_VERSION,
    description=(
        "Compare a recency/importance-weighted Elo rating family against the "
        f"market-only baseline. No such model exists yet. {_BLOCKED_NOTE}"
    ),
    decision_unit="match",
    candidate_model_family="weighted-elo",
    baseline_comparator="market-only-baseline",
    primary_endpoint_description=_PRIMARY_ENDPOINT,
)

BRADLEY_TERRY_TEMPLATE = ExperimentTemplate(
    template_id="exp-template-bradley-terry",
    template_version=_TEMPLATE_VERSION,
    description=(
        "Compare a Bradley-Terry paired-comparison family against the market-only "
        f"baseline. No such model exists yet. {_BLOCKED_NOTE}"
    ),
    decision_unit="match",
    candidate_model_family="bradley-terry",
    baseline_comparator="market-only-baseline",
    primary_endpoint_description=_PRIMARY_ENDPOINT,
)

STAGE2_COMBINED_TEMPLATE = ExperimentTemplate(
    template_id="exp-template-stage2-combined",
    template_version=_TEMPLATE_VERSION,
    description=(
        "Compare the stage-two market-aware combined model against the market-only "
        f"baseline. No such model exists yet. {_BLOCKED_NOTE}"
    ),
    decision_unit="match",
    candidate_model_family="stage2-combined",
    baseline_comparator="market-only-baseline",
    primary_endpoint_description=_PRIMARY_ENDPOINT,
)

#: The exact five ADR 0017 phase-seven experiment families, in program order.
ALL_EXPERIMENT_TEMPLATES: tuple[ExperimentTemplate, ...] = (
    MARKET_ONLY_BASELINE_TEMPLATE,
    SURFACE_ELO_TEMPLATE,
    WEIGHTED_ELO_TEMPLATE,
    BRADLEY_TERRY_TEMPLATE,
    STAGE2_COMBINED_TEMPLATE,
)
