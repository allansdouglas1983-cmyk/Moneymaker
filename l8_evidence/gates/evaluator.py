"""The pure, deterministic gate evaluation (SPEC-093, ADR 0011 decisions 4-9).

``evaluate`` maps (gate spec, experiment record, facts registry, manifests, as-of) to a
four-valued ``GateResult``. It reads no clock and no file: every input is explicit, so
identical inputs produce byte-identical canonical output.

Verdict precedence is safety-first: stale facts and any harm signal dominate futility,
futility dominates everything but harm, and PASS requires every precondition, the exact
multiplicity check and the efficacy boundary together. Constructed insufficient evidence
can therefore never reach PASS (§12.4).
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Mapping, Optional

from l8_evidence.gates.experiment import ExperimentRecord
from l8_evidence.gates.facts import FactsRegistry, assess_facts
from l8_evidence.gates.outcomes import (
    EVALUATOR_VERSION,
    GateEvaluationError,
    GateOutcome,
    GateResult,
)
from l8_evidence.gates.spec import GateDefinition, GateItem, GateSpec, GateSpecError

_MANIFEST_RE = re.compile(r"\Asha256:[0-9a-f]{64}\Z")

_ONE = Decimal(1)
_ZERO = Decimal(0)

_PAYBACK_INPUTS = (
    "n_eligible_per_year",
    "r_select",
    "r_fill",
    "mean_stake",
    "roi_lower",
    "c_recurring_per_year",
    "c_fixed",
    "max_payback_years",
)


class EvaluatorError(GateEvaluationError):
    """A malformed evaluation request. An error is never a verdict (CLI exit 4)."""


def _require_manifest(value: str, name: str) -> None:
    if _MANIFEST_RE.fullmatch(value) is None:
        raise EvaluatorError(f"{name} must match sha256:<64 lowercase hex>, got {value!r}")


def _payback_amortises(inputs: Mapping[str, Decimal | int] | None) -> bool | None:
    """§10.4 by exact arithmetic. ``None`` means the inputs are not all supplied yet.

    ``T = c_fixed / annual <= max_payback_years`` is evaluated as
    ``c_fixed <= max_payback_years * annual`` (equivalent for ``annual > 0``), so the
    comparison uses multiplication only and stays exact.
    """
    if inputs is None:
        return None
    if any(key not in inputs for key in _PAYBACK_INPUTS):
        return None
    annual = (
        inputs["n_eligible_per_year"]
        * inputs["r_select"]
        * inputs["r_fill"]
        * inputs["mean_stake"]
        * inputs["roi_lower"]
        - inputs["c_recurring_per_year"]
    )
    if annual <= _ZERO:
        return False
    return inputs["c_fixed"] <= inputs["max_payback_years"] * annual


def _item_state(item: GateItem, experiment: ExperimentRecord) -> bool | None:
    """True/False from attestation or computation; ``None`` when not yet supplied."""
    if item.computed is not None:
        return _payback_amortises(experiment.computed_inputs.get(item.computed))
    return experiment.attestations.get(item.item_id)


def _check_attestation_ids(gate: GateDefinition, experiment: ExperimentRecord) -> None:
    items_by_id = {item.item_id: item for item in gate.items}
    for attested_id in experiment.attestations:
        item = items_by_id.get(attested_id)
        if item is None:
            raise EvaluatorError(
                f"{gate.gate_id}: attestation {attested_id!r} names no item of this gate"
            )
        if item.computed is not None:
            raise EvaluatorError(
                f"{gate.gate_id}: {attested_id!r} is computed ({item.computed}) and"
                " cannot be hand-attested"
            )


def evaluate(
    *,
    spec: GateSpec,
    experiment: ExperimentRecord,
    facts: FactsRegistry,
    data_manifest: str,
    model_manifest: str,
    as_of: date,
) -> GateResult:
    """Evaluate one experiment against its declared gate. Deterministic and pure."""
    _require_manifest(data_manifest, "data-manifest")
    _require_manifest(model_manifest, "model-manifest")
    try:
        gate = spec.gate(experiment.gate_id)
    except GateSpecError as exc:
        raise EvaluatorError(str(exc)) from exc
    _check_attestation_ids(gate, experiment)

    harm: list[str] = []
    futility: list[str] = []
    keep_going: list[str] = []

    gate_ids = frozenset(name for name in (gate.gate_id, gate.alias) if name is not None)
    assessment = assess_facts(facts, gate_ids=gate_ids, as_of=as_of)
    harm.extend(assessment.stale_or_misconfigured)
    keep_going.extend(assessment.required_unpopulated)

    by_flavour: dict[GateOutcome, list[str]] = {
        GateOutcome.FAIL_HARM: harm,
        GateOutcome.FAIL_FUTILITY: futility,
        GateOutcome.CONTINUE: keep_going,
    }
    for item in gate.items:
        state = _item_state(item, experiment)
        if state is None:
            keep_going.append(f"{item.item_id}: not yet attested or computed")
        elif state is False:
            by_flavour[item.on_false].append(f"{item.item_id}: attested or computed false")

    # Optional[...] rather than `| None`: local annotations are never runtime-evaluated,
    # so a `|` here would be unobservable mutant surface (the get_type_hints killer test
    # only reaches signatures and class bodies).
    max_n_futility: Optional[str] = None
    if gate.decision is not None:
        prereg = experiment.preregistration
        if prereg is None:
            raise EvaluatorError(
                f"{gate.gate_id}: an evidence gate requires the pre-registration block (§9.7)"
            )
        evidence = experiment.evidence
        if evidence is None:
            keep_going.append("no evidence recorded yet")
        else:
            if evidence.loss_budget_breached:
                harm.append("experiment loss budget breached")
            if evidence.upper_bound < prereg.harm_threshold:
                harm.append(
                    f"upper bound {evidence.upper_bound} below harm threshold"
                    f" {prereg.harm_threshold}"
                )
            spent_alpha = (_ONE - prereg.confidence_level) * (
                prereg.number_of_prior_trials + 1
            )
            if spent_alpha > prereg.alpha_budget:
                keep_going.append(
                    f"alpha budget exceeded by multiplicity: (1 - {prereg.confidence_level})"
                    f" x {prereg.number_of_prior_trials + 1} = {spent_alpha}"
                    f" > {prereg.alpha_budget}"
                )
            efficacy_crossed = evidence.lower_bound > prereg.minimum_economic_effect
            if not efficacy_crossed:
                keep_going.append(
                    f"lower bound {evidence.lower_bound} has not crossed the minimum"
                    f" economic effect {prereg.minimum_economic_effect}"
                )
                if evidence.n >= prereg.max_n:
                    max_n_futility = (
                        f"max_n {prereg.max_n} reached (n={evidence.n}) without crossing"
                        " the efficacy boundary"
                    )

    if harm:
        outcome, reasons = GateOutcome.FAIL_HARM, harm
    elif futility:
        outcome, reasons = GateOutcome.FAIL_FUTILITY, futility
    elif not keep_going:
        outcome, reasons = GateOutcome.PASS, []
    elif max_n_futility is not None:
        outcome, reasons = GateOutcome.FAIL_FUTILITY, [max_n_futility]
    else:
        outcome, reasons = GateOutcome.CONTINUE, keep_going

    return GateResult(
        gate_id=gate.gate_id,
        experiment_id=experiment.experiment_id,
        outcome=outcome,
        reasons=tuple(reasons),
        data_manifest=data_manifest,
        model_manifest=model_manifest,
        spec_version=spec.version,
        spec_digest=spec.digest,
        facts_digest=facts.digest,
        evaluator_version=EVALUATOR_VERSION,
        as_of=as_of,
    )
