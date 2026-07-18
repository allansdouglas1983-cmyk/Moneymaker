"""Stage-2A: the reserved tennis outcome-extraction home refuses until authorised, and is
import-quarantined from pre-lockbox consumers (enforced statically by the Makefile
`verify` import-quarantine line; asserted structurally here). SPEC-092 / SPEC-021."""
from __future__ import annotations

import pytest

from l8_evidence.tennis_outcomes import (
    OutcomeAccessNotAuthorisedError,
    extract_match_outcome,
)

pytestmark = [pytest.mark.spec("SPEC-092")]


def test_extraction_always_refuses() -> None:
    with pytest.raises(OutcomeAccessNotAuthorisedError):
        extract_match_outcome("1.234", {"anything": "here"})


def test_prelockbox_packages_do_not_import_the_outcome_home() -> None:
    # Structural mirror of the Makefile import-quarantine line: no pre-lockbox package
    # reaches the outcome-extraction module. Uses the same first-party import walk.
    from pathlib import Path

    from tools.check_import_quarantine import find_violations

    violations = find_violations(
        root=Path("."),
        forbid="l8_evidence.tennis_outcomes",
        from_pkgs=["l3_features", "l4_pricing"],
    )
    assert violations == [], violations
