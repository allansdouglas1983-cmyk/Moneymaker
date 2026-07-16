"""SPEC-093: experiment-record loader — exact numbers only, floats refused."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from l8_evidence.gates.experiment import ExperimentError, load_experiment

pytestmark = pytest.mark.spec("SPEC-093")

_RECORD = """\
experiment_id: exp-2026-041
gate: GATE-1
hypothesis: combined model beats the market price on the race-level log score
decision_unit: race
primary_endpoint: paired race-level log-score difference
minimum_economic_effect: "0.005"
harm_threshold: "-0.010"
alpha_budget: "0.05"
confidence_level: "0.99"
max_n: 4000
number_of_prior_trials: 3
stopping_rule: anytime-valid confidence sequence at the declared level
evidence:
  lower_bound: "0.007"
  upper_bound: "0.020"
  n: 2100
  loss_budget_breached: false
attestations:
  lockbox_uncontaminated: true
  endpoint_preregistered: true
computed_inputs:
  payback_v1:
    n_eligible_per_year: 2500
    r_select: "0.10"
    r_fill: "0.80"
    mean_stake: "2.00"
    roi_lower: "0.02"
    c_recurring_per_year: "120.00"
    c_fixed: "499.00"
    max_payback_years: "2"
"""


def _load(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "exp-2026-041.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_a_full_record_with_exact_numbers(tmp_path: Path) -> None:
    record = load_experiment(_load(tmp_path, _RECORD))
    assert record.experiment_id == "exp-2026-041"
    assert record.gate_id == "GATE-1"
    prereg = record.preregistration
    assert prereg is not None
    assert prereg.minimum_economic_effect == Decimal("0.005")
    assert prereg.harm_threshold == Decimal("-0.010")
    assert prereg.alpha_budget == Decimal("0.05")
    assert prereg.confidence_level == Decimal("0.99")
    assert prereg.max_n == 4000
    assert prereg.number_of_prior_trials == 3
    evidence = record.evidence
    assert evidence is not None
    assert evidence.lower_bound == Decimal("0.007")
    assert evidence.upper_bound == Decimal("0.020")
    assert evidence.n == 2100
    assert evidence.loss_budget_breached is False
    assert record.attestations == {"lockbox_uncontaminated": True, "endpoint_preregistered": True}
    assert record.computed_inputs["payback_v1"]["mean_stake"] == Decimal("2.00")


@pytest.mark.parametrize(
    "needle",
    [
        'minimum_economic_effect: "0.005"',
        'harm_threshold: "-0.010"',
        'alpha_budget: "0.05"',
        'confidence_level: "0.99"',
        'lower_bound: "0.007"',
        'upper_bound: "0.020"',
    ],
)
def test_float_leaves_are_refused(tmp_path: Path, needle: str) -> None:
    key, quoted = needle.split(": ")
    broken = _RECORD.replace(needle, f"{key}: {quoted.strip(chr(34))}")
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


def test_float_computed_input_is_refused(tmp_path: Path) -> None:
    broken = _RECORD.replace('r_select: "0.10"', "r_select: 0.10")
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


def test_missing_experiment_id_is_refused(tmp_path: Path) -> None:
    broken = _RECORD.replace("experiment_id: exp-2026-041\n", "")
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


def test_missing_gate_is_refused(tmp_path: Path) -> None:
    broken = _RECORD.replace("gate: GATE-1\n", "")
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


def test_negative_prior_trials_is_refused(tmp_path: Path) -> None:
    broken = _RECORD.replace("number_of_prior_trials: 3", "number_of_prior_trials: -1")
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


@pytest.mark.parametrize("level", ['"0"', '"1"', '"1.5"', '"-0.1"'])
def test_confidence_level_outside_open_unit_interval_is_refused(tmp_path: Path, level: str) -> None:
    broken = _RECORD.replace('confidence_level: "0.99"', f"confidence_level: {level}")
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


def test_nonpositive_alpha_budget_is_refused(tmp_path: Path) -> None:
    broken = _RECORD.replace('alpha_budget: "0.05"', 'alpha_budget: "0"')
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


def test_max_n_below_one_is_refused(tmp_path: Path) -> None:
    broken = _RECORD.replace("max_n: 4000", "max_n: 0")
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


def test_negative_evidence_n_is_refused(tmp_path: Path) -> None:
    broken = _RECORD.replace("n: 2100", "n: -5")
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


def test_bounds_out_of_order_are_refused(tmp_path: Path) -> None:
    broken = _RECORD.replace('upper_bound: "0.020"', 'upper_bound: "0.001"')
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


def test_non_boolean_attestation_is_refused(tmp_path: Path) -> None:
    broken = _RECORD.replace("lockbox_uncontaminated: true", "lockbox_uncontaminated: probably")
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


def test_non_boolean_loss_budget_flag_is_refused(tmp_path: Path) -> None:
    broken = _RECORD.replace("loss_budget_breached: false", "loss_budget_breached: unknown")
    with pytest.raises(ExperimentError):
        load_experiment(_load(tmp_path, broken))


def test_record_without_evidence_or_preregistration_still_loads(tmp_path: Path) -> None:
    minimal = "experiment_id: exp-c\ngate: GATE-0A\nattestations:\n  raw_messages_retained: true\n"
    record = load_experiment(_load(tmp_path, minimal))
    assert record.preregistration is None
    assert record.evidence is None
    assert record.attestations == {"raw_messages_retained": True}
