"""Experiment-record loader (SPEC-093; the §9.7 pre-registration record plus gate,
evidence and attestation blocks — the schema SPEC-091's ledger later formalises).

Money types: every quantity is an exact ``Decimal`` built from a string or an int.
A YAML float leaf is refused outright — binary floats must never carry a boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

import yaml

from l8_evidence.gates.outcomes import GateEvaluationError

_ONE = Decimal(1)
_ZERO = Decimal(0)

_PREREG_KEYS = (
    "minimum_economic_effect",
    "harm_threshold",
    "alpha_budget",
    "confidence_level",
    "max_n",
    "number_of_prior_trials",
    "primary_endpoint",
    "stopping_rule",
)


class ExperimentError(GateEvaluationError):
    """The experiment record is malformed; evaluation refuses to start."""


@dataclass(frozen=True)
class PreRegistration:
    """The declared-before-observation boundaries (§9.7, §10.1)."""

    minimum_economic_effect: Decimal
    harm_threshold: Decimal
    alpha_budget: Decimal
    confidence_level: Decimal
    max_n: int
    number_of_prior_trials: int
    primary_endpoint: str
    stopping_rule: str


@dataclass(frozen=True)
class Evidence:
    """Anytime-valid bounds on the primary endpoint (§9.8) plus budget state."""

    lower_bound: Decimal
    upper_bound: Decimal
    n: int
    loss_budget_breached: bool


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    gate_id: str
    preregistration: PreRegistration | None = None
    evidence: Evidence | None = None
    attestations: Mapping[str, bool] = field(default_factory=dict)
    computed_inputs: Mapping[str, Mapping[str, Decimal | int]] = field(default_factory=dict)


def _decimal(raw: Any, where: str) -> Decimal:
    if isinstance(raw, bool) or isinstance(raw, float):
        raise ExperimentError(f"{where}: {raw!r} must be a quoted decimal string or an int, not {type(raw).__name__}")
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, str):
        try:
            return Decimal(raw.strip())
        except InvalidOperation as exc:
            raise ExperimentError(f"{where}: not a decimal: {raw!r}") from exc
    raise ExperimentError(f"{where}: expected a number, got {raw!r}")


def _int(raw: Any, where: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ExperimentError(f"{where}: expected an integer, got {raw!r}")
    return raw


def _bool(raw: Any, where: str) -> bool:
    if not isinstance(raw, bool):
        raise ExperimentError(f"{where}: expected a boolean, got {raw!r}")
    return raw


def _string(raw: Any, where: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise ExperimentError(f"{where}: expected a non-empty string, got {raw!r}")
    return raw


def _parse_preregistration(document: Mapping[str, Any], where: str) -> PreRegistration | None:
    present = [key for key in _PREREG_KEYS if key in document]
    if not present:
        return None
    missing = [key for key in _PREREG_KEYS if key not in document]
    if missing:
        raise ExperimentError(f"{where}: partial pre-registration; missing {missing}")
    confidence_level = _decimal(document["confidence_level"], f"{where}.confidence_level")
    if not _ZERO < confidence_level < _ONE:
        raise ExperimentError(f"{where}: confidence_level must lie strictly inside (0, 1)")
    alpha_budget = _decimal(document["alpha_budget"], f"{where}.alpha_budget")
    if alpha_budget <= _ZERO:
        raise ExperimentError(f"{where}: alpha_budget must be positive")
    max_n = _int(document["max_n"], f"{where}.max_n")
    if max_n < 1:
        raise ExperimentError(f"{where}: max_n must be at least 1")
    number_of_prior_trials = _int(document["number_of_prior_trials"], f"{where}.number_of_prior_trials")
    if number_of_prior_trials < 0:
        raise ExperimentError(f"{where}: number_of_prior_trials must be non-negative")
    return PreRegistration(
        minimum_economic_effect=_decimal(
            document["minimum_economic_effect"], f"{where}.minimum_economic_effect"
        ),
        harm_threshold=_decimal(document["harm_threshold"], f"{where}.harm_threshold"),
        alpha_budget=alpha_budget,
        confidence_level=confidence_level,
        max_n=max_n,
        number_of_prior_trials=number_of_prior_trials,
        primary_endpoint=_string(document["primary_endpoint"], f"{where}.primary_endpoint"),
        stopping_rule=_string(document["stopping_rule"], f"{where}.stopping_rule"),
    )


def _parse_evidence(raw: Any, where: str) -> Evidence | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ExperimentError(f"{where}: evidence must be a mapping, got {raw!r}")
    lower_bound = _decimal(raw.get("lower_bound"), f"{where}.lower_bound")
    upper_bound = _decimal(raw.get("upper_bound"), f"{where}.upper_bound")
    if upper_bound < lower_bound:
        raise ExperimentError(f"{where}: upper_bound below lower_bound is incoherent evidence")
    n = _int(raw.get("n"), f"{where}.n")
    if n < 0:
        raise ExperimentError(f"{where}: n must be non-negative")
    return Evidence(
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        n=n,
        loss_budget_breached=_bool(raw.get("loss_budget_breached"), f"{where}.loss_budget_breached"),
    )


def _parse_attestations(raw: Any, where: str) -> dict[str, bool]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ExperimentError(f"{where}: attestations must be a mapping, got {raw!r}")
    return {
        _string(key, f"{where} key"): _bool(value, f"{where}.{key}") for key, value in raw.items()
    }


def _parse_computed_inputs(raw: Any, where: str) -> dict[str, dict[str, Decimal]]:
    # Narrower than the record field (Decimal, not Decimal | int): _decimal always returns
    # an exact Decimal, and Mapping is covariant in its value type.
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ExperimentError(f"{where}: computed_inputs must be a mapping, got {raw!r}")
    parsed: dict[str, dict[str, Decimal]] = {}
    for procedure, inputs in raw.items():
        proc_name = _string(procedure, f"{where} key")
        if not isinstance(inputs, dict):
            raise ExperimentError(f"{where}.{proc_name}: inputs must be a mapping, got {inputs!r}")
        parsed[proc_name] = {
            _string(key, f"{where}.{proc_name} key"): _decimal(value, f"{where}.{proc_name}.{key}")
            for key, value in inputs.items()
        }
    return parsed


def load_experiment(path: Path) -> ExperimentRecord:
    """Parse and validate one experiment record file."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ExperimentError(f"{path}: unparseable YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise ExperimentError(f"{path}: experiment record is not a mapping")
    experiment_id = _string(document.get("experiment_id"), f"{path}.experiment_id")
    gate_id = _string(document.get("gate"), f"{path}.gate")
    return ExperimentRecord(
        experiment_id=experiment_id,
        gate_id=gate_id,
        preregistration=_parse_preregistration(document, str(path)),
        evidence=_parse_evidence(document.get("evidence"), f"{path}.evidence"),
        attestations=_parse_attestations(document.get("attestations"), f"{path}.attestations"),
        computed_inputs=_parse_computed_inputs(document.get("computed_inputs"), f"{path}.computed_inputs"),
    )
