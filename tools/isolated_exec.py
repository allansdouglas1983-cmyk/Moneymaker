"""Process-group-isolated command runner with proven timeout cleanup (STAGE3-0006 §4 harness).

The mutation-runner process-isolation defect (MUTATION_HARNESS_PROCESS_ISOLATION_DEFECT, incident
2026-07-22): a per-mutant test command that spawns children (pytest → workers → Python) could, on
timeout, leave a descendant alive after the parent exited — an ORPHANED_RUNAWAY_PYTEST_PROCESS that
consumed a full core for ~62 minutes and contaminated a concurrent run with resource pressure.

This module runs a command as the leader of a NEW session (its own process group), and on timeout:
  1. sends SIGTERM to the whole group,
  2. waits a bounded grace period,
  3. sends SIGKILL to every process still in the group,
  4. reaps the direct child,
  5. verifies (by scanning /proc) that no non-zombie descendant remains in the group,
  6. returns a typed outcome; TIMEOUT_CLEANUP_FAILED is distinguished from TIMEOUT_CLEANED.

Used two ways: as the cosmic-ray ``test-command`` wrapper (CLI ``main``; a hanging mutant is
cleaned up AND reported as killed so no orphan escapes and no timeout is mis-scored as a survivor),
and as the isolated executor inside ``tools/mutation_harness.py`` (which adds source-restoration
proof). Pure stdlib; no third-party deps. Time via ``time.monotonic``.
"""
from __future__ import annotations

import argparse
import enum
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass


class RunState(str, enum.Enum):
    COMPLETED = "COMPLETED"                          # the command exited on its own
    TIMEOUT_CLEANED = "TIMEOUT_CLEANED"              # timed out; whole group proven reaped
    TIMEOUT_CLEANUP_FAILED = "TIMEOUT_CLEANUP_FAILED"  # timed out; a descendant survived cleanup
    SPAWN_ERROR = "SPAWN_ERROR"                      # could not start the command


@dataclass(frozen=True)
class IsolatedResult:
    state: RunState
    returncode: int | None       # the command's exit code when COMPLETED, else None
    duration_s: float
    survivors: int               # non-zombie processes still in the group after cleanup
    stdout_tail: str


def _proc_pgid(pid: int) -> int | None:
    """Process-group id of ``pid`` from /proc (field 5 of stat), or None if gone."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    # stat: "pid (comm) state ppid pgrp ...". comm may contain spaces/parens -> split on last ')'.
    rparen = data.rfind(b")")
    if rparen == -1:
        return None
    fields = data[rparen + 2:].split()
    if len(fields) < 3:
        return None
    try:
        return int(fields[2])            # pgrp is the 3rd field after state
    except ValueError:
        return None


def _proc_is_zombie(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/stat", "rb") as fh:
            data = fh.read()
    except OSError:
        return True                      # gone counts as not-alive
    rparen = data.rfind(b")")
    if rparen == -1:
        return True
    fields = data[rparen + 2:].split()
    return bool(fields) and fields[0] == b"Z"


def group_members(pgid: int) -> list[int]:
    """Live (non-zombie) pids whose process group is ``pgid``. Scans /proc; empty ⇒ group gone."""
    out: list[int] = []
    try:
        entries = os.listdir("/proc")
    except OSError:
        return out
    for name in entries:
        if not name.isdigit():
            continue
        pid = int(name)
        if _proc_pgid(pid) == pgid and not _proc_is_zombie(pid):
            out.append(pid)
    return out


def _killpg(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def run_isolated(cmd: list[str], timeout: float, *, cwd: str | None = None,
                 grace: float = 5.0) -> IsolatedResult:
    """Run ``cmd`` as a new-session leader; clean up the whole group on timeout. Never raises for
    a command that merely fails or hangs — returns a typed :class:`IsolatedResult`."""
    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd, start_new_session=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except OSError as exc:
        return IsolatedResult(RunState.SPAWN_ERROR, None, time.monotonic() - start, 0, str(exc))

    pgid = proc.pid                      # start_new_session makes the child its own group leader
    try:
        out, _ = proc.communicate(timeout=timeout)
        return IsolatedResult(RunState.COMPLETED, proc.returncode, time.monotonic() - start, 0,
                              _tail(out))
    except subprocess.TimeoutExpired:
        pass

    # --- timeout path: graceful group term, bounded grace, forced group kill, verify, reap ---
    _killpg(pgid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and group_members(pgid):
        time.sleep(0.05)
    if group_members(pgid):
        _killpg(pgid, signal.SIGKILL)
        hard = time.monotonic() + grace
        while time.monotonic() < hard and group_members(pgid):
            time.sleep(0.05)

    try:
        proc.wait(timeout=grace)         # reap the direct child (its stdout pipe closes on exit)
    except subprocess.TimeoutExpired:
        pass
    try:
        out = proc.stdout.read() if proc.stdout else ""
    except (OSError, ValueError):
        out = ""
    finally:
        if proc.stdout:
            proc.stdout.close()

    remaining = group_members(pgid)
    state = RunState.TIMEOUT_CLEANED if not remaining else RunState.TIMEOUT_CLEANUP_FAILED
    return IsolatedResult(state, None, time.monotonic() - start, len(remaining), _tail(out))


def _tail(text: str, n: int = 4000) -> str:
    return text[-n:] if text and len(text) > n else (text or "")


# Exit codes for the cosmic-ray test-command wrapper. A hanging mutant is CLEANED and reported
# non-zero so cosmic-ray records it KILLED (a hang IS a detected fault) — never a survivor.
_EXIT_TIMEOUT_CLEANED = 124
_EXIT_TIMEOUT_CLEANUP_FAILED = 125
_EXIT_SPAWN_ERROR = 126


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Run a command in an isolated session with timeout cleanup.")
    p.add_argument("--timeout", type=float, required=True)
    p.add_argument("--grace", type=float, default=5.0)
    p.add_argument("cmd", nargs=argparse.REMAINDER,
                   help="the command, after a literal --")
    args = p.parse_args(argv)
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        print("isolated_exec: empty command", file=sys.stderr)
        return 2
    res = run_isolated(cmd, args.timeout, grace=args.grace)
    if res.stdout_tail:
        sys.stdout.write(res.stdout_tail)
    if res.state is RunState.COMPLETED:
        return int(res.returncode or 0)
    if res.state is RunState.TIMEOUT_CLEANED:
        sys.stderr.write(f"isolated_exec: TIMEOUT_CLEANED after {res.duration_s:.1f}s\n")
        return _EXIT_TIMEOUT_CLEANED
    if res.state is RunState.TIMEOUT_CLEANUP_FAILED:
        sys.stderr.write(f"isolated_exec: TIMEOUT_CLEANUP_FAILED survivors={res.survivors}\n")
        return _EXIT_TIMEOUT_CLEANUP_FAILED
    sys.stderr.write(f"isolated_exec: SPAWN_ERROR {res.stdout_tail}\n")
    return _EXIT_SPAWN_ERROR


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
