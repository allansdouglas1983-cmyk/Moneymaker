"""Structural pins backing the Stage 2G Slice-2 mutation-survivor packet
(docs/evidence/stage2g-dp1-development/MUTATION_SURVIVOR_PACKET_V1.json).

Founder pre-result controls §2: each proposed equivalence class must pin the
structural facts its proof rests on. Nothing here approves anything — approval is
per-ID and founder-only.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from l4_pricing.races import Race, RaceValidationError, RunnerRow
from sport_core.clustering import calendar_day_assignment

pytestmark = [pytest.mark.spec("SPEC-105"), pytest.mark.spec("SPEC-106")]

_REPO = Path(__file__).resolve().parents[3]
_MODULES = (
    _REPO / "sport_tennis/glicko2_family.py",
    _REPO / "sport_tennis/dp1_distribution.py",
    _REPO / "sport_tennis/dp1_calibration.py",
)


class TestClassAPep563ArchitecturePin:
    """Class A (PEP 563 annotation mutants) rests on: annotations in these modules are
    never evaluated at runtime by ANY consumer."""

    def test_modules_use_postponed_evaluation(self) -> None:
        for path in _MODULES:
            assert "from __future__ import annotations" in path.read_text().splitlines()[
                0:40
            ].__str__() or "from __future__ import annotations" in path.read_text(), path

    def test_no_runtime_annotation_consumer_in_repo(self) -> None:
        """No production module calls typing.get_type_hints / inspect.get_annotations,
        and the DP1 modules define no pydantic models (whose schema generation would
        evaluate annotations). Tests and tools are excluded; docs are archival."""
        offenders: list[str] = []
        for py in _REPO.rglob("*.py"):
            rel = py.relative_to(_REPO).as_posix()
            if rel.startswith(("tests/", "tools/", "docs/", ".venv", "research/")):
                continue
            for raw in py.read_text(encoding="utf-8", errors="replace").splitlines():
                code = raw.split("#", 1)[0]  # comments are not consumers
                if re.search(r"get_type_hints|inspect\.get_annotations|\.__annotations__", code):
                    offenders.append(rel)
                    break
        assert offenders == [], (
            "a runtime annotation consumer would break the Class-A equivalence proof: "
            f"{offenders}"
        )

    def test_dp1_modules_define_no_pydantic_models(self) -> None:
        for path in _MODULES:
            text = path.read_text()
            assert "BaseModel" not in text and "pydantic" not in text, path


class TestClassDRaceInvariantPin:
    """Class D (unreachable `len(active) < 2` side of `!= 2`) rests on the Race
    constructor invariant: no valid Race exists with fewer than two active runners."""

    def test_race_refuses_fewer_than_two_active(self) -> None:
        from decimal import Decimal

        with pytest.raises(RaceValidationError):
            Race(
                race_id="one-active",
                cluster=calendar_day_assignment("tennis", __import__("datetime").date(2025, 1, 1)),
                runners=(
                    RunnerRow(runner_id=1, features={"placeholder": Decimal("0")}),
                    RunnerRow(runner_id=2, features={"placeholder": Decimal("0")}, non_runner=True),
                ),
                winner_id=None,
            )

    def test_race_refuses_zero_runners(self) -> None:
        with pytest.raises(RaceValidationError):
            Race(
                race_id="empty",
                cluster=calendar_day_assignment("tennis", __import__("datetime").date(2025, 1, 1)),
                runners=(),
                winner_id=None,
            )

    def test_winner_must_be_an_active_runner(self) -> None:
        """Class C2's dominated-comparison proof also rests on winner in {a, b}."""
        from decimal import Decimal

        with pytest.raises(RaceValidationError):
            Race(
                race_id="foreign-winner",
                cluster=calendar_day_assignment("tennis", __import__("datetime").date(2025, 1, 1)),
                runners=(
                    RunnerRow(runner_id=1, features={"placeholder": Decimal("0")}),
                    RunnerRow(runner_id=2, features={"placeholder": Decimal("0")}),
                ),
                winner_id=9,
            )
