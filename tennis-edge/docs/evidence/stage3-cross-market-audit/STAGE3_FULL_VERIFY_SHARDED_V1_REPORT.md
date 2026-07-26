# STAGE3 sharded full-verify report — VERDICT: FULL_VERIFY_SHARDED_FAIL

Commit `93f0ea696c211201505dece3d9df641bf518af50`. Policy FULL_VERIFY_SHARDED_V1.

## pytest (the exact make-verify selection) — COMPLETE, GREEN
- 3097/3097 nodes PASS across 21 shards; skip 0, xfail 0, xpass 0, fail 0.
- missing 0, extra 0, duplicate 0, pending 0.
- longest shard S000 (518.1s). Claim: EXACT_TEST_SELECTION_EXECUTED_WITH_COMPLETE_SHARDED_COVERAGE.

## non-pytest gates — 22/24 PASS, 2 FAIL (pre-existing)
- FAIL `ruff check --select ARG .` (11 errors) — both files PRE-EXISTING (test_root_dedup.py, test_solver_nonfinite_reachability.py).
- FAIL `mypy --strict .` (38 errors) — 9/10 files PRE-EXISTING; the one A3-touched file (test_solver_golden.py) fails only on its pre-existing untyped `mk` helper + a pre-existing type:ignore.
- A3's own changed source+test files pass ruff-ARG and mypy --strict individually: **A3 introduced zero lint/type regressions.**

## disposition
- Per §11/§12 two non-zero non-pytest gates => FULL_VERIFY_SHARDED_FAIL.
- Per §13 NO source/test changed to make verify pass; the pre-existing failures are returned for founder decision.
- Monolithic one-process `make verify` NOT completed in this environment (600s cap); remains required before release.
