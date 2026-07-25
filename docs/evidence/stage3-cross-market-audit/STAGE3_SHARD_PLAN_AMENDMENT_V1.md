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
