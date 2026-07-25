"""STAGE3-0006 §4 — red tests for the process-group-isolated command runner.

These pin the MUTATION_HARNESS_PROCESS_ISOLATION_DEFECT fix: on timeout the runner must terminate
and reap the ENTIRE descendant tree (child, grandchild, signal-ignoring child, orphaned child) so
no ORPHANED_RUNAWAY_PYTEST_PROCESS survives; a completed run must never kill another run's group;
and every run must leave a clean process table.

The synthetic loopers are short-lived (small timeout + grace) and each asserts the group is empty
afterward (case I), so the suite itself leaves no orphan.
"""
from __future__ import annotations

import sys
import threading

from tools.isolated_exec import IsolatedResult, RunState, run_isolated

_PY = sys.executable
_T = 1.5      # per-case timeout
_G = 1.0      # grace


def _run(code: str) -> IsolatedResult:
    return run_isolated([_PY, "-u", "-c", code], _T, grace=_G)


def test_a_loop_forever_is_cleaned() -> None:
    r = _run("\nwhile True:\n    pass\n")
    assert r.state is RunState.TIMEOUT_CLEANED
    assert r.survivors == 0


def test_b_child_loops_parent_waits() -> None:
    code = (
        "import subprocess, sys\n"
        "c = subprocess.Popen([sys.executable, '-c', 'while True: pass'])\n"
        "c.wait()\n"
    )
    r = _run(code)
    assert r.state is RunState.TIMEOUT_CLEANED
    assert r.survivors == 0


def test_c_orphan_child_parent_exits() -> None:
    # parent spawns a looping child and exits immediately; the child (now orphaned) must still be
    # killed because it is in the runner's session group. This is the incident scenario.
    code = (
        "import subprocess, sys, os\n"
        "subprocess.Popen([sys.executable, '-c', 'while True: pass'])\n"
        "os._exit(0)\n"
    )
    r = _run(code)
    assert r.state is RunState.TIMEOUT_CLEANED
    assert r.survivors == 0


def test_d_grandchild_is_cleaned() -> None:
    code = (
        "import subprocess, sys\n"
        "inner = 'import subprocess,sys; subprocess.Popen([sys.executable,\"-c\",\"while True: pass\"]).wait()'\n"
        "subprocess.Popen([sys.executable, '-c', inner]).wait()\n"
    )
    r = _run(code)
    assert r.state is RunState.TIMEOUT_CLEANED
    assert r.survivors == 0


def test_e_child_ignores_sigterm() -> None:
    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "while True:\n    time.sleep(0.01)\n"
    )
    r = _run(code)
    assert r.state is RunState.TIMEOUT_CLEANED     # SIGKILL must finish the job SIGTERM could not
    assert r.survivors == 0


def test_f_concurrent_timeouts_each_cleaned() -> None:
    results: list[IsolatedResult] = []
    lock = threading.Lock()

    def go() -> None:
        r = _run("\nwhile True:\n    pass\n")
        with lock:
            results.append(r)

    threads = [threading.Thread(target=go) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 3
    assert all(r.state is RunState.TIMEOUT_CLEANED and r.survivors == 0 for r in results)


def test_g_completed_run_does_not_kill_a_concurrent_group() -> None:
    # a fast COMPLETED run must not disturb a concurrently-looping run's group (each cleans only its
    # own session pgid). Start the looper, run several quick completions, then confirm the looper
    # still times out cleanly rather than being pre-empted.
    looper_result: list[IsolatedResult] = []

    def looper() -> None:
        looper_result.append(_run("\nwhile True:\n    pass\n"))

    t = threading.Thread(target=looper)
    t.start()
    for _ in range(3):
        quick = run_isolated([_PY, "-c", "print('ok')"], _T, grace=_G)
        assert quick.state is RunState.COMPLETED
        assert quick.returncode == 0
    t.join()
    assert looper_result[0].state is RunState.TIMEOUT_CLEANED
    assert looper_result[0].survivors == 0


def test_completed_nonzero_is_reported() -> None:
    r = run_isolated([_PY, "-c", "import sys; sys.exit(3)"], _T, grace=_G)
    assert r.state is RunState.COMPLETED
    assert r.returncode == 3


def test_completed_zero_is_reported() -> None:
    r = run_isolated([_PY, "-c", "pass"], _T, grace=_G)
    assert r.state is RunState.COMPLETED
    assert r.returncode == 0


def test_j_sequential_runs_are_independent_and_clean() -> None:
    # a later run starts from a clean state regardless of an earlier timeout (case J), and case I
    # (no orphan) holds for every run.
    r1 = _run("\nwhile True:\n    pass\n")
    r2 = run_isolated([_PY, "-c", "print('clean')"], _T, grace=_G)
    assert r1.state is RunState.TIMEOUT_CLEANED and r1.survivors == 0
    assert r2.state is RunState.COMPLETED and r2.returncode == 0


def test_spawn_error_is_typed() -> None:
    r = run_isolated(["/nonexistent/definitely-not-a-binary-xyz"], _T, grace=_G)
    assert r.state is RunState.SPAWN_ERROR
