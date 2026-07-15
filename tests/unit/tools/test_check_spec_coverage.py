"""Unit tests for tools/check_spec_coverage.py.

These exercise the SPEC-coverage checker against synthetic manifests and test trees.
They carry no @pytest.mark.spec of their own — the tool is support/evidence infrastructure,
not a numbered SPEC-ID.
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from tools import _spec_lib
from tools import check_spec_coverage as csc


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")


def _manifest(root: Path, body: str) -> Path:
    m = root / "spec-manifest.yaml"
    m.write_text(textwrap.dedent(body), encoding="utf-8")
    return m


def test_find_spec_markers_variants() -> None:
    src = """
    import pytest
    pytestmark = pytest.mark.spec("SPEC-001")

    @pytest.mark.spec("SPEC-002", "SPEC-003")
    def test_a() -> None: ...

    class TestGroup:
        @pytest.mark.spec("SPEC-004")
        def test_b(self) -> None: ...
    """
    got = _spec_lib.find_spec_markers_in_source(textwrap.dedent(src))
    assert got == {"SPEC-001", "SPEC-002", "SPEC-003", "SPEC-004"}


def test_active_id_without_test_fails(tmp_path: Path) -> None:
    m = _manifest(
        tmp_path,
        """
        - id: SPEC-050
          component: l5_decision
          criticality: money
          enforcement_state: active
        """,
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    rc = csc.main(
        ["--manifest", str(m), "--enforce-states", "active,verified", "--tests-dir", str(tests)]
    )
    assert rc == 1


def test_active_id_with_property_marker_passes(tmp_path: Path) -> None:
    m = _manifest(
        tmp_path,
        """
        - id: SPEC-050
          component: l5_decision
          criticality: money
          enforcement_state: active
          relevant_inputs: [win_probability]
          metamorphic_properties: [ev monotonic in win_probability]
        """,
    )
    tests = tmp_path / "tests"
    _write(
        tests / "properties" / "test_ev.py",
        """
        import pytest

        @pytest.mark.spec("SPEC-050")
        def test_ev() -> None: ...
        """,
    )
    rc = csc.main(
        [
            "--manifest", str(m),
            "--enforce-states", "active,verified",
            "--tests-dir", str(tests),
            "--require-properties-for", "money",
            "--require-causal-declarations",
        ]
    )
    assert rc == 0


def test_unknown_marker_id_fails(tmp_path: Path) -> None:
    m = _manifest(
        tmp_path,
        """
        - id: SPEC-050
          component: l5_decision
          criticality: money
          enforcement_state: active
          relevant_inputs: [p]
          metamorphic_properties: [x]
        """,
    )
    tests = tmp_path / "tests"
    _write(
        tests / "properties" / "test_ev.py",
        """
        import pytest

        @pytest.mark.spec("SPEC-050")
        def test_ev() -> None: ...

        @pytest.mark.spec("SPEC-999")
        def test_ghost() -> None: ...
        """,
    )
    rc = csc.main(["--manifest", str(m), "--enforce-states", "active", "--tests-dir", str(tests)])
    assert rc == 1


def test_money_requires_property_test(tmp_path: Path) -> None:
    m = _manifest(
        tmp_path,
        """
        - id: SPEC-050
          component: l5_decision
          criticality: money
          enforcement_state: active
          relevant_inputs: [p]
          metamorphic_properties: [x]
        """,
    )
    tests = tmp_path / "tests"
    # Covered only by a non-property (unit) test.
    _write(
        tests / "unit" / "test_ev.py",
        """
        import pytest

        @pytest.mark.spec("SPEC-050")
        def test_ev() -> None: ...
        """,
    )
    rc = csc.main(
        [
            "--manifest", str(m),
            "--enforce-states", "active",
            "--tests-dir", str(tests),
            "--require-properties-for", "money",
        ]
    )
    assert rc == 1


def test_causal_declarations_incomplete_fails(tmp_path: Path) -> None:
    m = _manifest(
        tmp_path,
        """
        - id: SPEC-060
          component: l5b_risk
          criticality: money
          enforcement_state: active
          relevant_inputs: [estimated_edge]
        """,
    )
    tests = tmp_path / "tests"
    _write(
        tests / "properties" / "test_stake.py",
        """
        import pytest

        @pytest.mark.spec("SPEC-060")
        def test_stake() -> None: ...
        """,
    )
    rc = csc.main(
        [
            "--manifest", str(m),
            "--enforce-states", "active",
            "--tests-dir", str(tests),
            "--require-causal-declarations",
            "--require-properties-for", "money",
        ]
    )
    assert rc == 1


def test_structural_money_without_declarations_ok(tmp_path: Path) -> None:
    # SPEC-054 style: money, but a guard/structural invariant with no numerical declarations.
    m = _manifest(
        tmp_path,
        """
        - id: SPEC-054
          component: l5_decision
          criticality: money
          enforcement_state: active
        """,
    )
    tests = tmp_path / "tests"
    _write(
        tests / "properties" / "test_one_runner.py",
        """
        import pytest

        @pytest.mark.spec("SPEC-054")
        def test_one_runner() -> None: ...
        """,
    )
    rc = csc.main(
        [
            "--manifest", str(m),
            "--enforce-states", "active",
            "--tests-dir", str(tests),
            "--require-causal-declarations",
            "--require-properties-for", "money",
        ]
    )
    assert rc == 0


def test_planned_id_not_enforced(tmp_path: Path) -> None:
    m = _manifest(
        tmp_path,
        """
        - id: SPEC-030
          component: l4_pricing
          criticality: money
          enforcement_state: planned
        """,
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    rc = csc.main(
        ["--manifest", str(m), "--enforce-states", "active,verified", "--tests-dir", str(tests)]
    )
    assert rc == 0


def test_verification_loss_skips_without_base(tmp_path: Path) -> None:
    m = _manifest(
        tmp_path,
        """
        - id: SPEC-050
          component: l5_decision
          criticality: money
          enforcement_state: active
          relevant_inputs: [p]
          metamorphic_properties: [x]
        """,
    )
    tests = tmp_path / "tests"
    _write(
        tests / "properties" / "test_ev.py",
        """
        import pytest

        @pytest.mark.spec("SPEC-050")
        def test_ev() -> None: ...
        """,
    )
    rc = csc.main(
        [
            "--manifest", str(m),
            "--enforce-states", "active",
            "--tests-dir", str(tests),
            "--detect-verification-loss",
            "--base-ref", "refs/does-not-exist",
            "--require-properties-for", "money",
            "--require-causal-declarations",
        ]
    )
    assert rc == 0


# --- Advisory-review hardening (ADR 0001 amendment): skipped tests and money downgrades ---


def test_skipped_marker_not_counted() -> None:
    src = """
    import pytest

    @pytest.mark.skip(reason="wip")
    @pytest.mark.spec("SPEC-001")
    def test_skipped() -> None:
        assert False

    @pytest.mark.spec("SPEC-002")
    def test_real() -> None: ...
    """
    assert _spec_lib.find_spec_markers_in_source(textwrap.dedent(src)) == {"SPEC-002"}


def test_module_skipped_marker_not_counted() -> None:
    src = """
    import pytest

    pytestmark = [pytest.mark.skip, pytest.mark.spec("SPEC-003")]

    @pytest.mark.spec("SPEC-004")
    def test_x() -> None: ...
    """
    assert _spec_lib.find_spec_markers_in_source(textwrap.dedent(src)) == set()


def test_skipped_active_id_fails_coverage(tmp_path: Path) -> None:
    m = _manifest(
        tmp_path,
        """
        - id: SPEC-050
          component: l5_decision
          criticality: money
          enforcement_state: active
          relevant_inputs: [p]
          metamorphic_properties: [x]
        """,
    )
    tests = tmp_path / "tests"
    _write(
        tests / "properties" / "test_ev.py",
        """
        import pytest

        @pytest.mark.skip(reason="wip")
        @pytest.mark.spec("SPEC-050")
        def test_ev() -> None: ...
        """,
    )
    rc = csc.main(["--manifest", str(m), "--enforce-states", "active", "--tests-dir", str(tests)])
    assert rc == 1


def test_verification_loss_active_money_downgrade() -> None:
    base: list[dict[str, Any]] = [
        {"id": "SPEC-050", "criticality": "money", "enforcement_state": "active"}
    ]
    index: dict[str, dict[str, Any]] = {
        "SPEC-050": {"id": "SPEC-050", "criticality": "evidence", "enforcement_state": "active"}
    }
    errors = csc._verification_loss(base, index)
    assert any("money -> evidence" in e for e in errors)


def test_verification_loss_planned_money_downgrade() -> None:
    base: list[dict[str, Any]] = [
        {"id": "SPEC-060", "criticality": "money", "enforcement_state": "planned"}
    ]
    index: dict[str, dict[str, Any]] = {
        "SPEC-060": {"id": "SPEC-060", "criticality": "evidence", "enforcement_state": "planned"}
    }
    errors = csc._verification_loss(base, index)
    assert any("SPEC-060" in e and "money -> evidence" in e for e in errors)


def test_verification_loss_active_deletion() -> None:
    base: list[dict[str, Any]] = [
        {"id": "SPEC-050", "criticality": "money", "enforcement_state": "active"}
    ]
    errors = csc._verification_loss(base, {})
    assert any("SPEC-050" in e and "absent" in e for e in errors)


def test_verification_loss_clean() -> None:
    base: list[dict[str, Any]] = [
        {"id": "SPEC-050", "criticality": "money", "enforcement_state": "active"}
    ]
    index: dict[str, dict[str, Any]] = {
        "SPEC-050": {"id": "SPEC-050", "criticality": "money", "enforcement_state": "active"}
    }
    assert csc._verification_loss(base, index) == []
