"""Hardened per-mutant revalidator (STAGE3-0006 §4/§5): apply a mutation, run its distinguishing
tests in an isolated session, restore the source, and PROVE both process cleanup and byte-identical
source restoration before scoring the outcome.

Outcome states (founder §4):
  NORMAL                 - tests completed and PASSED -> a genuine surviving mutant
  KILLED_BY_TEST         - tests completed and FAILED -> mutant detected
  TIMEOUT_CLEANED        - tests hung; the whole group was reaped -> mutant detected (a hang is a
                           fault), NEVER a survivor
  TIMEOUT_CLEANUP_FAILED - tests hung and a descendant survived cleanup -> STOP the gate
  WORKER_ERROR           - the runner could not start the command
  SOURCE_RESTORE_FAILED  - the target source was not byte-identical after the run -> STOP the gate

TIMEOUT_CLEANUP_FAILED and SOURCE_RESTORE_FAILED are terminal: a gate MUST NOT continue, and such a
job MUST NOT enter a survivor packet. Only NORMAL is a survivor.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path

from tools.isolated_exec import IsolatedResult, RunState, run_isolated


class MutationOutcome(str, enum.Enum):
    NORMAL = "NORMAL"                                  # survived (tests passed on the mutant)
    KILLED_BY_TEST = "KILLED_BY_TEST"
    TIMEOUT_CLEANED = "TIMEOUT_CLEANED"
    TIMEOUT_CLEANUP_FAILED = "TIMEOUT_CLEANUP_FAILED"
    WORKER_ERROR = "WORKER_ERROR"
    SOURCE_RESTORE_FAILED = "SOURCE_RESTORE_FAILED"


STOP_STATES = frozenset({MutationOutcome.TIMEOUT_CLEANUP_FAILED, MutationOutcome.SOURCE_RESTORE_FAILED})
SURVIVOR_STATE = MutationOutcome.NORMAL


@dataclass(frozen=True)
class RevalidationResult:
    outcome: MutationOutcome
    run: IsolatedResult
    source_restored: bool


def revalidate_mutant(module_path: str | Path, mutated_text: bytes, test_cmd: list[str],
                      timeout: float, *, cwd: str | None = None, grace: float = 5.0,
                      ) -> RevalidationResult:
    """Write ``mutated_text`` over ``module_path``, run ``test_cmd`` isolated, ALWAYS restore the
    original bytes, verify byte-identical restoration, and score a :class:`MutationOutcome`."""
    path = Path(module_path)
    original = path.read_bytes()
    restored = False
    try:
        path.write_bytes(mutated_text)
        run = run_isolated(test_cmd, timeout, cwd=cwd, grace=grace)
    finally:
        try:
            path.write_bytes(original)
            restored = path.read_bytes() == original
        except OSError:
            restored = False

    if not restored:
        return RevalidationResult(MutationOutcome.SOURCE_RESTORE_FAILED, run, False)
    if run.state is RunState.COMPLETED:
        outcome = MutationOutcome.NORMAL if run.returncode == 0 else MutationOutcome.KILLED_BY_TEST
    elif run.state is RunState.TIMEOUT_CLEANED:
        outcome = MutationOutcome.TIMEOUT_CLEANED
    elif run.state is RunState.TIMEOUT_CLEANUP_FAILED:
        outcome = MutationOutcome.TIMEOUT_CLEANUP_FAILED
    else:
        outcome = MutationOutcome.WORKER_ERROR
    return RevalidationResult(outcome, run, True)
