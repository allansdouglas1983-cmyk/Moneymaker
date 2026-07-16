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


# --- second mutation pass (665 mutants): killers for the remaining survivor classes ----


def test_multiplicity_reason_reports_the_trial_multiplier(tmp_path: Path) -> None:
    # Kills arithmetic mutants inside the multiplicity reason text: the reported
    # multiplier must be number_of_prior_trials + 1 exactly (5 prior trials -> x 6).
    from l8_evidence.gates.evaluator import evaluate
    from l8_evidence.gates.facts import FactsRegistry as _FR
    from l8_evidence.gates.spec import GateKind as _GK

    spec = GateSpec(
        version="gates-v1",
        digest="sha256:" + "0" * 64,
        gates=(
            GateDefinition(
                gate_id="GATE-M",
                kind=_GK.EVIDENCE,
                decision="anytime_valid_bounds_v1",
                items=(GateItem(item_id="p", on_false=outcomes_mod.GateOutcome.CONTINUE),),
            ),
        ),
    )
    record = load_experiment(_write_record(tmp_path, trials="5", lower='"0.007"', upper='"0.020"'))
    record = dataclasses.replace(record, gate_id="GATE-M", attestations={"p": True})
    result = evaluate(
        spec=spec,
        experiment=record,
        facts=_FR(facts=(), digest="sha256:" + "0" * 64),
        data_manifest="sha256:" + "1" * 64,
        model_manifest="sha256:" + "2" * 64,
        as_of=date(2026, 7, 16),
    )
    assert result.outcome is outcomes_mod.GateOutcome.CONTINUE
    assert " x 6 = " in " ".join(result.reasons)


def _evaluate_single_evidence_gate(record: ExperimentRecord) -> object:
    from l8_evidence.gates.evaluator import evaluate
    from l8_evidence.gates.spec import GateKind as _GK

    spec = GateSpec(
        version="gates-v1",
        digest="sha256:" + "0" * 64,
        gates=(
            GateDefinition(
                gate_id="GATE-M",
                kind=_GK.EVIDENCE,
                decision="anytime_valid_bounds_v1",
                items=(GateItem(item_id="p", on_false=outcomes_mod.GateOutcome.CONTINUE),),
            ),
        ),
    )
    return evaluate(
        spec=spec,
        experiment=dataclasses.replace(record, gate_id="GATE-M", attestations={"p": True}),
        facts=FactsRegistry(facts=(), digest="sha256:" + "0" * 64),
        data_manifest="sha256:" + "1" * 64,
        model_manifest="sha256:" + "2" * 64,
        as_of=date(2026, 7, 16),
    ).outcome


def test_multiplicity_subtraction_is_a_true_subtraction(tmp_path: Path) -> None:
    # Kills Sub -> Mod on (1 - confidence_level): for 0.99 the two coincide (1 % 0.99 =
    # 0.01), so this uses 0.4 where 1 - 0.4 = 0.6 but 1 % 0.4 = 0.2. With alpha 0.5 the
    # true spent alpha (0.6) exceeds the budget and must block PASS.
    path = _write_record(tmp_path, trials="0", alpha='"0.5"', lower='"0.007"', upper='"0.020"')
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace('confidence_level: "0.99"', 'confidence_level: "0.4"'), encoding="utf-8"
    )
    record = load_experiment(path)
    assert _evaluate_single_evidence_gate(record) is outcomes_mod.GateOutcome.CONTINUE


def test_beyond_max_n_without_efficacy_is_still_futility(tmp_path: Path) -> None:
    # Kills >= -> == (and int-interning `is`) on the max_n check: n strictly past max_n
    # must still be FAIL_FUTILITY, not CONTINUE.
    record = load_experiment(_write_record(tmp_path, max_n="4000", n="4001"))
    assert _evaluate_single_evidence_gate(record) is outcomes_mod.GateOutcome.FAIL_FUTILITY


def test_negative_evidence_n_of_minus_one_is_refused(tmp_path: Path) -> None:
    # Kills 0 -> -1 on the evidence n floor: -1 is the first illegal value.
    with pytest.raises(ExperimentError):
        load_experiment(_write_record(tmp_path, n="-1"))


def test_fact_without_a_used_by_key_loads_as_unused(tmp_path: Path) -> None:
    # Kills or -> and on the used_by default: a fact with no used_by key is simply
    # required by no gate, never a crash.
    path = tmp_path / "facts.yaml"
    path.write_text("- fact_id: LONE\n  value: null\n  recheck_by: null\n", encoding="utf-8")
    registry = load_facts_registry(path)
    assert registry.facts[0].used_by == ()


# --- payback boundary killers ---------------------------------------------------------


def _payback_outcome(
    c_recurring: str, c_fixed: str, extra: dict[str, str] | None = None
) -> object:
    from l8_evidence.gates.evaluator import evaluate
    from l8_evidence.gates.spec import GateKind as _GK

    inputs: dict[str, Decimal | int] = {
        "n_eligible_per_year": 2500,
        "r_select": Decimal("0.10"),
        "r_fill": Decimal("0.80"),
        "mean_stake": Decimal("2.00"),
        "roi_lower": Decimal("0.02"),
        "c_recurring_per_year": Decimal(c_recurring),
        "c_fixed": Decimal(c_fixed),
        "max_payback_years": Decimal("2"),
    }
    for key, value in (extra or {}).items():
        inputs[key] = Decimal(value)
    spec = GateSpec(
        version="gates-v1",
        digest="sha256:" + "0" * 64,
        gates=(
            GateDefinition(
                gate_id="GATE-P",
                kind=_GK.CHECKLIST,
                items=(
                    GateItem(
                        item_id="payback_within_precommitted_horizon",
                        on_false=outcomes_mod.GateOutcome.FAIL_FUTILITY,
                        computed="payback_v1",
                    ),
                ),
            ),
        ),
    )
    record = ExperimentRecord(
        experiment_id="exp-p", gate_id="GATE-P", computed_inputs={"payback_v1": inputs}
    )
    return evaluate(
        spec=spec,
        experiment=record,
        facts=FactsRegistry(facts=(), digest="sha256:" + "0" * 64),
        data_manifest="sha256:" + "1" * 64,
        model_manifest="sha256:" + "2" * 64,
        as_of=date(2026, 7, 16),
    ).outcome


def test_fractional_annual_contribution_is_still_viable() -> None:
    # annual = 8.00 - 7.50 = 0.50 and c_fixed 1.00 <= 2 x 0.50: kills 0 -> 1 on _ZERO,
    # which would misread every sub-unit annual contribution as never-amortising.
    assert _payback_outcome("7.50", "1.00") is outcomes_mod.GateOutcome.PASS


def test_zero_annual_with_zero_fixed_cost_never_amortises() -> None:
    # annual = 0 with c_fixed = 0: <= at the guard must classify it never-amortising
    # (kills <= -> < and <= -> is, and 0 -> -1 on _ZERO, all of which would PASS it).
    assert _payback_outcome("8.00", "0") is outcomes_mod.GateOutcome.FAIL_FUTILITY


def test_negative_annual_never_amortises_even_with_a_negative_fixed_cost() -> None:
    # Garbage-tolerance pin: a (nonsensical) negative c_fixed must not resurrect a
    # negative annual contribution via the comparison path (kills <= -> == at the guard,
    # which is otherwise observable only on this input class).
    assert _payback_outcome("14.00", "-100") is outcomes_mod.GateOutcome.FAIL_FUTILITY


# --- spec-loader guard killers --------------------------------------------------------


_SPEC_TEMPLATE = """\
version: {version}
evaluator: gate-evaluator-v1
outcomes: {outcomes}
gates:
  - gate_id: {gate_id}
    title: t
    kind: checklist
    items: {items}
"""


def _write_spec(
    tmp_path: Path,
    *,
    version: str = "gates-v1",
    outcomes: str = "[PASS, CONTINUE, FAIL_HARM, FAIL_FUTILITY]",
    gate_id: str = "GATE-X",
    items: str = "[{item_id: alpha, requirement: r, on_false: CONTINUE}]",
) -> Path:
    path = tmp_path / "gates.yaml"
    path.write_text(
        _SPEC_TEMPLATE.format(version=version, outcomes=outcomes, gate_id=gate_id, items=items),
        encoding="utf-8",
    )
    return path


def test_empty_version_is_refused(tmp_path: Path) -> None:
    # Kills or->and on the version guard.
    with pytest.raises(spec_mod.GateSpecError):
        spec_mod.load_gate_spec(_write_spec(tmp_path, version='""'))


def test_empty_gate_id_is_refused(tmp_path: Path) -> None:
    # Kills or->and on the gate_id guard.
    with pytest.raises(spec_mod.GateSpecError):
        spec_mod.load_gate_spec(_write_spec(tmp_path, gate_id='""'))


def test_empty_item_id_is_refused(tmp_path: Path) -> None:
    # Kills or->and on the item_id guard.
    with pytest.raises(spec_mod.GateSpecError):
        spec_mod.load_gate_spec(
            _write_spec(tmp_path, items='[{item_id: "", requirement: r, on_false: CONTINUE}]')
        )


def test_empty_items_list_is_refused(tmp_path: Path) -> None:
    # Kills or->and on the non-empty items guard.
    with pytest.raises(spec_mod.GateSpecError):
        spec_mod.load_gate_spec(_write_spec(tmp_path, items="[]"))


def test_empty_gates_list_is_refused(tmp_path: Path) -> None:
    # Kills or->and on the non-empty gates guard.
    path = tmp_path / "gates.yaml"
    path.write_text(
        "version: gates-v1\noutcomes: [PASS, CONTINUE, FAIL_HARM, FAIL_FUTILITY]\ngates: []\n",
        encoding="utf-8",
    )
    with pytest.raises(spec_mod.GateSpecError):
        spec_mod.load_gate_spec(path)


def test_lexicographically_smaller_outcome_list_is_refused(tmp_path: Path) -> None:
    # Kills != -> > on the outcomes pin: [CONTINUE] compares less than the required list,
    # so an ordering mutant would accept it.
    with pytest.raises(spec_mod.GateSpecError):
        spec_mod.load_gate_spec(_write_spec(tmp_path, outcomes="[CONTINUE]"))


# --- CLI contract killers -------------------------------------------------------------


_CLI_BASE = {
    "--spec": "gates.yaml",
    "--experiment": "exp-1",
    "--experiment-root": "experiments",  # optional (has a default) — never omitted below
    "--data-manifest": "sha256:" + "1" * 64,
    "--model-manifest": "sha256:" + "2" * 64,
    "--facts-registry": "facts.yaml",
}
_CLI_REQUIRED = tuple(sorted(set(_CLI_BASE) - {"--experiment-root"}))


def _cli_argv(tmp_path: Path, omit: str | None = None) -> list[str]:
    (tmp_path / "gates.yaml").write_text(
        _SPEC_TEMPLATE.format(
            version="gates-v1",
            outcomes="[PASS, CONTINUE, FAIL_HARM, FAIL_FUTILITY]",
            gate_id="GATE-X",
            items="[{item_id: alpha, requirement: r, on_false: CONTINUE}]",
        ),
        encoding="utf-8",
    )
    (tmp_path / "facts.yaml").write_text("[]", encoding="utf-8")
    root = tmp_path / "experiments"
    root.mkdir(exist_ok=True)
    (root / "exp-1.yaml").write_text(
        "experiment_id: exp-1\ngate: GATE-X\nattestations:\n  alpha: true\n", encoding="utf-8"
    )
    argv = ["evaluate"]
    for flag, value in _CLI_BASE.items():
        if flag == omit:
            continue
        argv.append(flag)
        argv.append(str(tmp_path / value) if value.endswith(".yaml") or flag == "--experiment-root" else value)
    argv += ["--as-of", "2026-07-16"]
    return argv


def test_cli_all_options_present_passes(tmp_path: Path) -> None:
    assert cli_mod.main(_cli_argv(tmp_path)) == 0


@pytest.mark.parametrize("omit", _CLI_REQUIRED)
def test_cli_refuses_a_missing_required_option(tmp_path: Path, omit: str) -> None:
    # Kills required=True -> False per flag: argparse must reject the invocation
    # (SystemExit 2), never proceed into evaluation with a missing binding.
    with pytest.raises(SystemExit) as excinfo:
        cli_mod.main(_cli_argv(tmp_path, omit=omit))
    assert excinfo.value.code == 2


def test_cli_refuses_a_missing_subcommand() -> None:
    # Kills required=True -> False on the subparser.
    with pytest.raises(SystemExit) as excinfo:
        cli_mod.main([])
    assert excinfo.value.code == 2


def test_cli_invalid_as_of_is_exit_four(tmp_path: Path) -> None:
    # Kills ExceptionReplacer on the --as-of ValueError mapping.
    argv = _cli_argv(tmp_path)
    argv[argv.index("2026-07-16")] = "not-a-date"
    assert cli_mod.main(argv) == 4


def test_cli_id_mismatch_smaller_file_id_is_exit_four(tmp_path: Path) -> None:
    # Kills != -> > on the experiment-id check: a file id that compares LESS than the
    # requested id ("exp-0" < "exp-1") must still be a mismatch.
    argv = _cli_argv(tmp_path)
    root = tmp_path / "experiments"
    (root / "exp-1.yaml").write_text(
        "experiment_id: exp-0\ngate: GATE-X\nattestations:\n  alpha: true\n", encoding="utf-8"
    )
    assert cli_mod.main(argv) == 4


def test_python_dash_m_entry_point_runs_the_cli(tmp_path: Path) -> None:
    # Pins the packaged __main__ entry (python -m l8_evidence.gates): the process must
    # produce the canonical verdict and the outcome exit code end-to-end.
    import json as _json
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "l8_evidence.gates", *_cli_argv(tmp_path)],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[3]),
        check=False,
    )
    assert result.returncode == 0
    assert _json.loads(result.stdout)["outcome"] == "PASS"
