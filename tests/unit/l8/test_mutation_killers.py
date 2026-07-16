"""SPEC-093 mutation killers: tests aimed at otherwise-silent mutants (§12.4).

Each test names the mutant class it kills. Additions only — no existing test changed.
"""
from __future__ import annotations

import dataclasses
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import get_type_hints

import pytest

from l8_evidence.gates import cli as cli_mod
from l8_evidence.gates import evaluator as evaluator_mod
from l8_evidence.gates import experiment as experiment_mod
from l8_evidence.gates import facts as facts_mod
from l8_evidence.gates import outcomes as outcomes_mod
from l8_evidence.gates import spec as spec_mod
from l8_evidence.gates.experiment import (
    Evidence,
    ExperimentError,
    ExperimentRecord,
    PreRegistration,
    load_experiment,
)
from l8_evidence.gates.facts import Fact, FactsAssessment, FactsRegistry, FactsRegistryError, load_facts_registry
from l8_evidence.gates.spec import GateDefinition, GateItem, GateSpec

pytestmark = pytest.mark.spec("SPEC-093")

_MODULES: tuple[ModuleType, ...] = (
    cli_mod,
    evaluator_mod,
    experiment_mod,
    facts_mod,
    outcomes_mod,
    spec_mod,
)


def test_every_annotation_in_the_package_resolves() -> None:
    # Under `from __future__ import annotations` a mutated annotation (e.g. `X | None` ->
    # `X << None`) is never evaluated at runtime and survives silently. Resolving the hints
    # of every class, method and function evaluates every annotation expression, so any
    # such mutant raises here.
    for module in _MODULES:
        for obj in vars(module).values():
            if inspect.isfunction(obj) and obj.__module__ == module.__name__:
                assert isinstance(get_type_hints(obj), dict)
            elif inspect.isclass(obj) and obj.__module__ == module.__name__:
                assert isinstance(get_type_hints(obj), dict)
                for _, method in inspect.getmembers(obj, inspect.isfunction):
                    if method.__qualname__.startswith(obj.__name__):
                        assert isinstance(get_type_hints(method), dict)


@pytest.mark.parametrize(
    "instance",
    [
        PreRegistration(
            minimum_economic_effect=Decimal("0.005"),
            harm_threshold=Decimal("-0.010"),
            alpha_budget=Decimal("0.05"),
            confidence_level=Decimal("0.99"),
            max_n=4000,
            number_of_prior_trials=0,
            primary_endpoint="endpoint",
            stopping_rule="rule",
        ),
        Evidence(
            lower_bound=Decimal("0"),
            upper_bound=Decimal("0"),
            n=0,
            loss_budget_breached=False,
        ),
        ExperimentRecord(experiment_id="exp-f", gate_id="GATE-F"),
        Fact(fact_id="F", populated=False, recheck_by=None),
        FactsRegistry(facts=(), digest="sha256:" + "0" * 64),
        FactsAssessment(stale_or_misconfigured=(), required_unpopulated=()),
        GateItem(item_id="i", on_false=outcomes_mod.GateOutcome.CONTINUE),
        GateDefinition(gate_id="G", kind=spec_mod.GateKind.CHECKLIST, items=()),
        GateSpec(version="gates-v1", digest="sha256:" + "0" * 64, gates=()),
    ],
    ids=lambda instance: type(instance).__name__,
)
def test_contract_dataclasses_are_frozen(instance: object) -> None:
    # Kills ReplaceTrueWithFalse on @dataclass(frozen=True): a mutable record would let
    # a verdict or a pre-registered boundary be edited after the fact.
    field_name = dataclasses.fields(instance)[0].name  # type: ignore[arg-type]
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, field_name, getattr(instance, field_name))


_RECORD_TEMPLATE = """\
experiment_id: exp-k
gate: GATE-1
minimum_economic_effect: {mee}
harm_threshold: "-0.010"
alpha_budget: {alpha}
confidence_level: "0.99"
max_n: {max_n}
number_of_prior_trials: {trials}
primary_endpoint: endpoint
stopping_rule: rule
evidence:
  lower_bound: {lower}
  upper_bound: {upper}
  n: {n}
  loss_budget_breached: false
"""


def _write_record(
    tmp_path: Path,
    *,
    mee: str = '"0.005"',
    alpha: str = '"0.05"',
    max_n: str = "4000",
    trials: str = "3",
    lower: str = '"0.001"',
    upper: str = '"0.002"',
    n: str = "10",
) -> Path:
    path = tmp_path / "exp-k.yaml"
    path.write_text(
        _RECORD_TEMPLATE.format(
            mee=mee, alpha=alpha, max_n=max_n, trials=trials, lower=lower, upper=upper, n=n
        ),
        encoding="utf-8",
    )
    return path


def test_boolean_where_a_decimal_is_expected_is_refused(tmp_path: Path) -> None:
    # Kills or->and in _decimal's bool/float guard: bool is an int subtype, so a mutated
    # guard would silently coerce `true` to Decimal(1).
    with pytest.raises(ExperimentError):
        load_experiment(_write_record(tmp_path, mee="true"))


def test_boolean_where_an_integer_is_expected_is_refused(tmp_path: Path) -> None:
    # Kills or->and in _int's guard for the same bool-is-int reason.
    with pytest.raises(ExperimentError):
        load_experiment(_write_record(tmp_path, max_n="true"))


def test_empty_experiment_id_is_refused(tmp_path: Path) -> None:
    # Kills or->and in _string: an empty id would satisfy isinstance alone.
    path = tmp_path / "exp-k.yaml"
    path.write_text('experiment_id: ""\ngate: GATE-1\n', encoding="utf-8")
    with pytest.raises(ExperimentError):
        load_experiment(path)


def test_undecodable_decimal_string_is_an_experiment_error(tmp_path: Path) -> None:
    # Kills ExceptionReplacer on InvalidOperation: the domain error must surface as
    # ExperimentError (CLI exit 4), never as a raw decimal exception.
    with pytest.raises(ExperimentError):
        load_experiment(_write_record(tmp_path, alpha='"not-a-number"'))


def test_unparseable_experiment_yaml_is_an_experiment_error(tmp_path: Path) -> None:
    # Kills ExceptionReplacer on yaml.YAMLError in load_experiment.
    path = tmp_path / "exp-k.yaml"
    path.write_text("experiment_id: exp-k\ngate: [broken", encoding="utf-8")
    with pytest.raises(ExperimentError):
        load_experiment(path)


def test_unparseable_facts_yaml_is_a_facts_registry_error(tmp_path: Path) -> None:
    # Kills ExceptionReplacer on yaml.YAMLError in load_facts_registry.
    path = tmp_path / "facts.yaml"
    path.write_text("- fact_id: [broken", encoding="utf-8")
    with pytest.raises(FactsRegistryError):
        load_facts_registry(path)


def test_negative_alpha_budget_is_refused(tmp_path: Path) -> None:
    # Kills <= -> == on the alpha_budget positivity guard.
    with pytest.raises(ExperimentError):
        load_experiment(_write_record(tmp_path, alpha='"-0.05"'))


def test_max_n_of_exactly_one_is_valid(tmp_path: Path) -> None:
    # Kills < -> <= (and 1 -> 2) on the max_n floor: 1 is the smallest legal max_n.
    record = load_experiment(_write_record(tmp_path, max_n="1", n="0"))
    assert record.preregistration is not None
    assert record.preregistration.max_n == 1


def test_zero_prior_trials_is_valid(tmp_path: Path) -> None:
    # Kills < -> <= (and 0 -> 1) on the number_of_prior_trials floor.
    record = load_experiment(_write_record(tmp_path, trials="0"))
    assert record.preregistration is not None
    assert record.preregistration.number_of_prior_trials == 0


def test_equal_bounds_are_coherent_evidence(tmp_path: Path) -> None:
    # Kills < -> <= on the bounds-order guard: a fully collapsed interval is legal.
    record = load_experiment(_write_record(tmp_path, lower='"0.001"', upper='"0.001"'))
    assert record.evidence is not None
    assert record.evidence.lower_bound == record.evidence.upper_bound


def test_zero_evidence_n_is_valid(tmp_path: Path) -> None:
    # Kills < -> <= (and 0 -> 1) on the evidence n floor.
    record = load_experiment(_write_record(tmp_path, n="0"))
    assert record.evidence is not None
    assert record.evidence.n == 0


def test_incoherent_fact_construction_is_inert() -> None:
    # Pins the directly-constructed corner (populated, no recheck_by, not misconfigured):
    # assess_facts must neither crash nor flag it — the loader can never produce it, and
    # a mutant that dereferences the None date would raise here.
    registry = FactsRegistry(
        facts=(Fact(fact_id="ODD", populated=True, recheck_by=None, misconfigured=False),),
        digest="sha256:" + "0" * 64,
    )
    assessment = facts_mod.assess_facts(registry, gate_ids=frozenset({"GATE-1"}), as_of=date(2026, 7, 16))
    assert assessment.required_unpopulated == ()
    assert assessment.stale_or_misconfigured == ()
