"""STAGE3-0006 §4/§5 — red tests for the hardened per-mutant revalidator.

Pins: only a completed-and-passing mutant is NORMAL (a survivor); a completed-and-failing mutant
is KILLED_BY_TEST; a hanging mutant is TIMEOUT_CLEANED (never a survivor) with the source proven
restored (case H); a source that cannot be restored is SOURCE_RESTORE_FAILED (a stop state).
"""
from __future__ import annotations

import sys
from pathlib import Path

from tools.mutation_harness import (STOP_STATES, SURVIVOR_STATE, MutationOutcome,
                                    revalidate_mutant)

_PY = sys.executable


def _mod(tmp_path: Path) -> Path:
    p = tmp_path / "victim.py"
    p.write_bytes(b"ORIGINAL = 1\n")
    return p


def test_normal_survivor(tmp_path: Path) -> None:
    p = _mod(tmp_path)
    r = revalidate_mutant(p, b"MUTATED = 1\n", [_PY, "-c", "pass"], timeout=5, grace=1)
    assert r.outcome is MutationOutcome.NORMAL
    assert r.source_restored
    assert p.read_bytes() == b"ORIGINAL = 1\n"


def test_killed_by_test(tmp_path: Path) -> None:
    p = _mod(tmp_path)
    r = revalidate_mutant(p, b"MUTATED = 1\n", [_PY, "-c", "import sys; sys.exit(1)"],
                          timeout=5, grace=1)
    assert r.outcome is MutationOutcome.KILLED_BY_TEST
    assert r.source_restored
    assert p.read_bytes() == b"ORIGINAL = 1\n"


def test_h_source_restored_on_timeout(tmp_path: Path) -> None:
    p = _mod(tmp_path)
    r = revalidate_mutant(p, b"MUTATED = 1\n", [_PY, "-c", "while True: pass"],
                          timeout=1.5, grace=1)
    assert r.outcome is MutationOutcome.TIMEOUT_CLEANED       # a hang is a detected fault
    assert r.outcome is not SURVIVOR_STATE                     # never a survivor
    assert r.source_restored
    assert p.read_bytes() == b"ORIGINAL = 1\n"                # byte-identical restoration


def test_worker_error(tmp_path: Path) -> None:
    p = _mod(tmp_path)
    r = revalidate_mutant(p, b"MUTATED = 1\n", ["/nonexistent/xyz-binary"], timeout=5, grace=1)
    assert r.outcome is MutationOutcome.WORKER_ERROR
    assert r.source_restored


def test_stop_states_membership() -> None:
    assert MutationOutcome.TIMEOUT_CLEANUP_FAILED in STOP_STATES
    assert MutationOutcome.SOURCE_RESTORE_FAILED in STOP_STATES
    assert MutationOutcome.NORMAL not in STOP_STATES
