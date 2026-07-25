"""STAGE3-0006C-D-A3-VERIFY-V1 §4 — deterministic foreground pytest shard runner.

Runs exactly one pytest shard synchronously in the active foreground call under
FULL_VERIFY_SHARDED_V1 (specs/programme/stage3-sharded-verification-policy-v1.yaml). Acquires an
exclusive lock, refuses on source drift or an unexplained worker, proves the shard's node IDs are
collectable, executes them in an isolated process group with a wall-clock limit, cleans up on
timeout (never scoring a timeout as a pass), verifies source is byte-identical to HEAD after, and
writes an immutable shard result. No background process; no test/source change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOCK = REPO / ".stage3_verify_shard.lock"
GRACE_SECONDS = 15.0


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(REPO), text=True, capture_output=True, check=False)


def _tracked_source_dirty() -> str:
    """Non-empty string listing tracked files that differ from HEAD (untracked files ignored)."""
    out = _run(["git", "diff", "--name-only", "HEAD"]).stdout.strip()
    return out


def _unexplained_worker() -> str:
    ps = _run(["ps", "-eo", "pid,args"]).stdout.splitlines()
    hits = [ln for ln in ps
            if any(t in ln for t in ("cosmic-ray", "isolated_exec", "cr-exec"))
            and "grep" not in ln]
    return "\n".join(hits)


def _digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "ABSENT"


def _canonical(nodes: list[str]) -> list[str]:
    return sorted(set(nodes))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--shard-id", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--limit-seconds", type=float, required=True)
    ap.add_argument("--source-head", required=True, help="expected HEAD commit SHA")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    requested = [ln for ln in Path(args.manifest).read_text().splitlines() if "::" in ln]
    result: dict[str, object] = {
        "shard_id": args.shard_id, "manifest": args.manifest,
        "manifest_digest": _digest_text("\n".join(requested) + "\n"),
        "requested_count": len(requested), "limit_seconds": args.limit_seconds,
        "expected_head": args.source_head,
    }

    def finish(outcome: str, **extra: object) -> int:
        result["outcome"] = outcome
        result.update(extra)
        blob = json.dumps(result, indent=1, sort_keys=True) + "\n"
        (out_dir / f"{args.shard_id}.result.json").write_text(blob)
        try:
            LOCK.unlink()
        except FileNotFoundError:
            pass
        print(f"{args.shard_id} OUTCOME={outcome} "
              f"passed={result.get('passed')} failed={result.get('failed')} "
              f"elapsed={result.get('elapsed_s')}")
        return 0 if outcome == "PASS" else 1

    # 1) exclusive lock
    try:
        fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{args.shard_id} pid={os.getpid()}".encode())
        os.close(fd)
    except FileExistsError:
        return finish("WORKER_ERROR", detail="verification lock already held")

    # 2) source drift
    head = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    dirty = _tracked_source_dirty()
    if head != args.source_head or dirty:
        return finish("SOURCE_DRIFT", head=head, dirty_tracked_files=dirty)

    # 3) unexplained worker
    worker = _unexplained_worker()
    if worker:
        return finish("WORKER_ERROR", detail="unexplained worker present", processes=worker)

    # 4/5) prove collectable under the exact environment
    coll = _run(["uv", "run", "pytest", *requested, "--collect-only", "-q", "-p", "no:cacheprovider"])
    collected = _canonical([ln for ln in coll.stdout.splitlines() if "::" in ln])
    if coll.returncode != 0 or collected != _canonical(requested):
        (out_dir / f"{args.shard_id}.collect.txt").write_text(coll.stdout + "\n---STDERR---\n" + coll.stderr)
        return finish("COLLECTION_MISMATCH", collect_exit=coll.returncode,
                      collected_count=len(collected),
                      missing=sorted(set(_canonical(requested)) - set(collected)),
                      extra=sorted(set(collected) - set(_canonical(requested))))

    # 6/7/8) execute in own process group, synchronous, capture stdout/stderr + JUnit
    junit = out_dir / f"{args.shard_id}.junit.xml"
    src_before = _run(["git", "diff", "--stat", "HEAD"]).stdout
    log = out_dir / f"{args.shard_id}.log"
    cmd = ["uv", "run", "pytest", *requested, "-q", "-p", "no:cacheprovider",
           f"--junitxml={junit}"]
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=str(REPO), text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=True)
    timed_out = False
    try:
        stdout, _ = proc.communicate(timeout=args.limit_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        stdout = ""
        # 9) terminate the process group, grace, force-kill, reap
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + GRACE_SECONDS
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.5)
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            leftover, _ = proc.communicate(timeout=GRACE_SECONDS)
            stdout = leftover or ""
        except subprocess.TimeoutExpired:
            pass
    elapsed = round(time.monotonic() - t0, 2)
    log.write_text(stdout)
    result["elapsed_s"] = elapsed
    result["log_digest"] = _digest_file(log)
    result["junit_digest"] = _digest_file(junit)

    # 11) source byte-identical after
    src_after_dirty = _tracked_source_dirty()
    result["source_before_diffstat_empty"] = src_before.strip() == ""
    result["source_after_equals_head"] = src_after_dirty == ""

    # 12) no child process remains (the process group is gone)
    still = proc.poll() is None
    result["process_cleanup"] = "FAILED" if still else "OK"

    if src_after_dirty:
        return finish("SOURCE_DRIFT", dirty_tracked_files=src_after_dirty)

    if timed_out:
        if still:
            return finish("TIMEOUT_CLEANUP_FAILED")
        return finish("TIMEOUT_CLEANED")

    # parse pytest tallies from JUnit
    passed = failed = skipped = errors = 0
    if junit.exists():
        import xml.etree.ElementTree as ET
        root = ET.fromstring(junit.read_text())
        suites = [root] if root.tag == "testsuite" else list(root)
        tests = sum(int(s.get("tests", "0")) for s in suites)
        failed = sum(int(s.get("failures", "0")) for s in suites)
        errors = sum(int(s.get("errors", "0")) for s in suites)
        skipped = sum(int(s.get("skipped", "0")) for s in suites)
        passed = tests - failed - errors - skipped
    result.update(passed=passed, failed=failed, skipped=skipped, errors=errors,
                  pytest_exit=proc.returncode)

    if proc.returncode == 0 and failed == 0 and errors == 0:
        return finish("PASS")
    return finish("TEST_FAILURE", pytest_exit=proc.returncode)


if __name__ == "__main__":
    sys.exit(main())
