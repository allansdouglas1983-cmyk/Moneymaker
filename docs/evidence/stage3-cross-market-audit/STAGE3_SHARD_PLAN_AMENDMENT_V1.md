# Shard-plan amendment (append-only) — STAGE3-0006C-D-A3-VERIFY-V1 §7

## Amendment 1 — S004 timeout split

- **Incident:** shard `S004` (`tests/unit/coherence/test_rootset_independent.py`, 6 nodes)
  reached the 540 s hard shard limit and was cleaned (`TIMEOUT_CLEANED`, `process_cleanup: OK`,
  source byte-identical to HEAD, no orphan process). The attempt is preserved as
  `S004.TIMEOUT_INCIDENT.result.json` and is **excluded from final verification evidence**.
  It is NOT a pass and NOT a test failure — the shard exceeded its wall-clock budget on a
  slower run (the same shard completed in 506 s on the previous run).
- **Action (deterministic, per §7):** the shard's node IDs were sorted lexically and split into
  two equal halves, `S004a` (first 3) and `S004b` (last 3). Union equals the original set
  exactly; the halves do not overlap.
- **Rerun:** both child shards are rerun from a clean source state. Their results supersede the
  timed-out attempt for coverage reconciliation.
- **No test, timeout, tolerance or expected value was changed.**

## Amendment 2 — S004a further split (timeout)

`S004a` (3 nodes) also reached the 540 s limit and was cleaned; attempt preserved as
`S004a.TIMEOUT_INCIDENT.result.json`, excluded from pass evidence. Split lexically into
`S004a1` (2 nodes) and `S004a2` (1 node). Both PASS (375.67 s, 258.19 s). Together with
`S004b` (3 nodes, PASS) the original S004 node set is fully covered exactly once.

## Amendment 3 — S005 proactive split (observed slowdown)

This run is measurably slower than the previous one (S002 137→164 s, S011 272→318 s,
S003 256→310 s, S006 319→376 s: ≈1.2×). `S005` (`tests/unit/coherence/test_solver.py`,
11 nodes) took 500 s previously, so it is now *known to approach the foreground cap* —
§6 forbids leaving such a shard unsplit. Split lexically into `S005a` (6 nodes) and
`S005b` (5 nodes) BEFORE execution; union equals the original set, no overlap. No test,
timeout or expected value was changed.
