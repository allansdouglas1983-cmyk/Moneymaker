"""Tennis settlement contracts (SPEC-084, ADR 0017 S7).

SPEC-084 is `planned`, money-critical, and explicitly forbids any empirical settlement
policy until the Betfair Exchange tennis rules page has been fetched and reconciled with
pilot data (DR-TENNIS-SETTLEMENT-001, currently unresolved). These tests pin the CONTRACT
layer only: a closed outcome enum, a frozen case type with a winner-mandatory-iff-COMPLETED
invariant, a typed refusal for every outcome (including the completed/happy path — the whole
matrix activates at once, never a partial policy), and a policy matrix template whose every
cell is an explicit PENDING marker rather than a guessed rule.

Nothing here may assert a settlement AMOUNT, a void rule, or a retirement/walkover payout —
that would be exactly the guessed empirical policy this SPEC-ID forbids.
"""
from __future__ import annotations

import ast
import inspect
import re
from dataclasses import FrozenInstanceError

import pytest

from l7_settle.tennis_rules import (
    POLICY_MATRIX_TEMPLATE,
    SettlementPolicyPendingError,
    TennisMatchOutcome,
    TennisSettlementCase,
    settle_tennis_case,
)

pytestmark = pytest.mark.spec("SPEC-084")

_EXPECTED_OUTCOMES = {
    "COMPLETED",
    "WALKOVER_BEFORE_PLAY",
    "RETIRED_BEFORE_SET1_COMPLETE",
    "RETIRED_AFTER_SET1_COMPLETE",
    "DISQUALIFICATION",
    "CANCELLED",
    "POSTPONED",
    "SURFACE_CHANGED",
    "PRE_MATCH_WITHDRAWAL",
}

_POLICY_DIMENSIONS = (
    "betfair_settlement",
    "model_training_inclusion",
    "predictor_score_inclusion",
    "clv_grading",
    "pnl_grading",
)

# Same banned-token regex the Makefile greps l7_settle/** with (make verify's ESCAPE_HATCHES).
# Kept as a literal copy (not an import) so this test independently pins the module clean,
# rather than trusting the same constant the implementation might also import.
_ESCAPE_HATCHES = re.compile(
    r"(notimplementederror|\btodo\b|\bfixme\b|\bxxx\b|\bhack\b|\bplaceholder\b|\bstub\b|"
    r"raise\s+notimplemented|\bpass\b\s*(\#.*)?$)",
    re.IGNORECASE | re.MULTILINE,
)


def _valid_case(outcome: TennisMatchOutcome) -> TennisSettlementCase:
    if outcome is TennisMatchOutcome.COMPLETED:
        return TennisSettlementCase(match_ref_id="m-1", outcome=outcome, winner_selection_id=123)
    return TennisSettlementCase(match_ref_id="m-1", outcome=outcome)


class TestEnumClosure:
    def test_exactly_nine_members(self) -> None:
        assert len(TennisMatchOutcome) == 9

    def test_exact_member_set(self) -> None:
        assert {member.name for member in TennisMatchOutcome} == _EXPECTED_OUTCOMES


class TestWinnerMandatoryIffCompleted:
    def test_completed_without_winner_is_refused(self) -> None:
        with pytest.raises(ValueError):
            TennisSettlementCase(match_ref_id="m-1", outcome=TennisMatchOutcome.COMPLETED)

    def test_completed_with_winner_is_accepted(self) -> None:
        case = TennisSettlementCase(
            match_ref_id="m-1", outcome=TennisMatchOutcome.COMPLETED, winner_selection_id=42
        )
        assert case.winner_selection_id == 42

    @pytest.mark.parametrize(
        "outcome",
        sorted((o for o in TennisMatchOutcome if o is not TennisMatchOutcome.COMPLETED), key=lambda o: o.name),
    )
    def test_non_completed_with_winner_is_refused(self, outcome: TennisMatchOutcome) -> None:
        with pytest.raises(ValueError):
            TennisSettlementCase(match_ref_id="m-1", outcome=outcome, winner_selection_id=7)

    @pytest.mark.parametrize(
        "outcome",
        sorted((o for o in TennisMatchOutcome if o is not TennisMatchOutcome.COMPLETED), key=lambda o: o.name),
    )
    def test_non_completed_without_winner_is_accepted(self, outcome: TennisMatchOutcome) -> None:
        case = TennisSettlementCase(match_ref_id="m-1", outcome=outcome)
        assert case.winner_selection_id is None


class TestFrozen:
    def test_case_is_frozen(self) -> None:
        case = _valid_case(TennisMatchOutcome.CANCELLED)
        with pytest.raises(FrozenInstanceError):
            case.match_ref_id = "m-2"  # type: ignore[misc]


class TestSettlementIsPolicyPending:
    @pytest.mark.parametrize("outcome", sorted(TennisMatchOutcome, key=lambda o: o.name))
    def test_every_outcome_raises_naming_itself(self, outcome: TennisMatchOutcome) -> None:
        case = _valid_case(outcome)
        with pytest.raises(SettlementPolicyPendingError) as excinfo:
            settle_tennis_case(case)
        assert outcome.name in str(excinfo.value)

    def test_completed_happy_path_also_refused(self) -> None:
        # The whole matrix activates at once (ADR 0017 S7): COMPLETED is not special-cased
        # into a real settlement just because it looks unambiguous.
        case = _valid_case(TennisMatchOutcome.COMPLETED)
        with pytest.raises(SettlementPolicyPendingError):
            settle_tennis_case(case)

    def test_error_cites_spec_and_research_ticket(self) -> None:
        doc = SettlementPolicyPendingError.__doc__ or ""
        assert "SPEC-084" in doc
        assert "DR-TENNIS-SETTLEMENT-001" in doc


class TestPolicyMatrixTemplate:
    def test_covers_every_outcome(self) -> None:
        assert set(POLICY_MATRIX_TEMPLATE.keys()) == set(TennisMatchOutcome)

    def test_every_outcome_has_all_five_dimensions(self) -> None:
        for outcome, dims in POLICY_MATRIX_TEMPLATE.items():
            assert set(dims.keys()) == set(_POLICY_DIMENSIONS), outcome

    def test_every_cell_is_pending(self) -> None:
        for outcome, dims in POLICY_MATRIX_TEMPLATE.items():
            for dimension, value in dims.items():
                assert value == "PENDING_EXCHANGE_RULES_VERIFICATION", (outcome, dimension)


class TestNoRacingImport:
    def test_module_does_not_import_racing_settlement(self) -> None:
        import l7_settle.tennis_rules as module

        source = inspect.getsource(module)
        tree = ast.parse(source)
        forbidden_modules = {"l7_settle.outcomes", "l7_settle.pnl", "l7_settle.settlement"}
        forbidden_names = {"outcomes", "pnl", "settlement"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden_modules, alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    assert node.module not in forbidden_modules, node.module
                    # relative "from . import outcomes" style
                    assert node.module not in forbidden_names, node.module
                for alias in node.names:
                    assert alias.name not in forbidden_names, alias.name


class TestNoEscapeHatches:
    def test_module_source_has_no_banned_tokens(self) -> None:
        import l7_settle.tennis_rules as module

        source = inspect.getsource(module)
        match = _ESCAPE_HATCHES.search(source)
        assert match is None, f"escape-hatch token found: {match.group(0) if match else None}"
