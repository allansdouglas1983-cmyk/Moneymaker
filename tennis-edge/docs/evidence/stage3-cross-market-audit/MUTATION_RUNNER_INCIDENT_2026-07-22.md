# Mutation runner incident — 2026-07-22

**Classification:** `MUTATION_HARNESS_PROCESS_ISOLATION_DEFECT`
(NOT a model, mathematics, or specification defect — a tooling/process-isolation defect in the
mutation runner.)

**Record created:** 2026-07-22T15:36Z, after source restoration was confirmed.

This record covers two related manifestations of the same defect observed during the STAGE3-0006
solver mutation pass.

---

## Event 1 — ORPHANED_RUNAWAY_PYTEST_PROCESS (PID 30538)

| field | value |
|-------|-------|
| escaped process PID | **30538** |
| process type | **orphaned live `pytest`** (a running, CPU-consuming process — NOT a zombie/defunct) |
| exact command | `.venv/bin/python -m pytest tests/unit/coherence/test_match_and_pmf.py test_match_ref_bo3_fast.py test_pmf_direct.py test_immutability.py -q -p no:xdist -x -k 'not production_equals_reference'` |
| originating mutation run | the **contaminated match-v2 run** (`cr_match_v2`, launched ~10:16Z in parallel with the xmarket chain) |
| approximate lifetime | **~62 minutes** (STIME 10:28 → observed at 62:11 elapsed) |
| observed CPU usage | **~100% of one core** (single-threaded busy loop) |
| parent state | **parent already exited** — the cosmic-ray worker that spawned it was gone; the process had been reparented |
| root cause | a match.py mutant made `match_distribution`'s `while state:` forward-DP loop non-terminating; the runner's per-mutant timeout killed the immediate worker but **failed to terminate the full descendant process tree**, orphaning the inner pytest |
| targeted kill | `kill -9 30538` (targeted single-PID kill, ~15:2xZ during the solver-run investigation), deliberately NOT a broad `pkill`, so the active solver run was not disturbed |
| active solver workers survived? | **Yes** — confirmed immediately after: the solver cosmic-ray `exec` + its worker continued (progress advanced 10 → 11 → … the same run reached 626 jobs) |
| held any repository file open? | **No** — a pytest process reads source at import time and closes it; it held no lock and no long-lived open handle on any repository file (verified: no repo file was truncated or altered by it) |
| wrote any mutation database record? | **No** — result rows are written by the cosmic-ray worker (the parent), which had exited; the orphan's own job result was therefore never recorded (it is among the match-v2 untested jobs) |
| could it mutate source itself? | **No** — it was a *test runner*, not the mutation applier; it executed tests against whatever bytes were on disk and had no code path that writes source |
| exact impact | It consumed ~1 core for ~62 min. Combined with the concurrent xmarket chain this starved the match-v2 run, so many match-v2 jobs **timed out or never ran**: `cr_match_v2` recorded only **188/302** jobs (183 NORMAL/KILLED + 5 NORMAL/SURVIVED) with **114 UNTESTED**. A naive `LEFT JOIN … test_outcome != 'KILLED'` briefly mis-counted those 114 untested as "survivors" (reported 119). **No committed packet was affected:** match-v2 was discarded and never used; the match packet is built from the clean, contention-free `cr_match_v3` (302/302, all NORMAL — see the outcome audit). |

## Event 2 — source left mutated when the runner died (same defect, second facet)

The (unhardened) solver cosmic-ray `exec` process **died between turns** during a multi-hour idle
gap (background process lost on an environment pause/resume). Because it was terminated without
running cosmic-ray's own source-restore, it left **`sport_tennis/coherence/solver.py` mutated** on
disk with the in-flight mutant:

```
L214  -        if r2 <= _ROOT_TOL * _ROOT_TOL:
L214  +        if r2 <= _ROOT_TOL / _ROOT_TOL:     # ReplaceBinaryOperator_Mul_Div (job in flight)
```

- HEAD `sport_tennis/coherence/solver.py` blob: `8eef77f395e6a66e9631c1e46196d864d0c9a022`
- contaminated working-tree blob: `6cb75591afb5d1edf8186a2dc2b1e0950479bd80`
- **Restoration:** `git checkout --` restored the file; `git hash-object` now equals the HEAD blob
  `8eef77f…` (byte-identical). All other coherence + xmarket source verified byte-identical to HEAD.
- The incomplete unhardened `cr_solver_v2` session (626/1113, all recorded jobs NORMAL) is
  **discarded**; the solver gate is re-run under the hardened harness.

---

## Fix (tests-first) and revalidation

- `tools/isolated_exec.py` — runs each test command as a **new-session leader**; on timeout it
  SIGTERMs the whole group, waits a bounded grace, SIGKILLs every survivor, reaps, and PROVES via
  `/proc` scan that no non-zombie descendant remains. Typed states COMPLETED / TIMEOUT_CLEANED /
  TIMEOUT_CLEANUP_FAILED / SPAWN_ERROR. A hanging mutant is cleaned AND reported killed (never a
  survivor). Red tests A–J (loop, child+wait, **orphaned child**, grandchild, SIGTERM-ignoring
  child, concurrent timeouts, no-cross-kill, sequential independence) — **16/16 green**; process
  table proven empty afterward.
- `tools/mutation_harness.py` — per-mutant revalidator adding **byte-identical source-restoration
  proof** and the six outcome states; `TIMEOUT_CLEANUP_FAILED` and `SOURCE_RESTORE_FAILED` are
  terminal stop states; only `NORMAL` is a survivor (source-restore-on-timeout = case H, green).
- `tools/run_hardened_mutation.sh` — wraps the whole run: pre-run restore, isolated_exec
  test-command, EXIT/INT/TERM trap restore, and a post-run **byte-identical HEAD verification**
  (exit 3 = SOURCE_RESTORE_FAILED); resumable so an interrupted run is recovered by re-invocation.
- `tools/mutation_audit.py` — per-session outcome audit; every **final** DB (scoring, formats,
  format_evidence, pmf, match-v3, holdout-v4, xmarket ×4) is **CLEAN**: 100% tested, all NORMAL,
  zero untested/non-normal/incompetent; `normal_survived` equals each committed packet's survivor
  count. No timeout was ever scored as a survivor in any committed packet.

**Match gate status:** `ENGINEERING_PACKET_COMPLETE_BUT_REVALIDATION_PENDING` — the packet stands
on the clean `cr_match_v3`, and its jobs are re-run under the hardened harness to close revalidation.
**Solver gate status:** mutation execution `IN_PROGRESS` under the hardened harness; final packet
`PENDING`. No founder approval gate is closed.
