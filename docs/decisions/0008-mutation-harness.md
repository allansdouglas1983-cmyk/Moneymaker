# 0008 — Mutation testing harness (`tools/run_mutation.py`)

- **Status:** Accepted
- **Date:** 2026-07-15
- **Scope:** `tools/run_mutation.py`, `specs/mutation-survivors.yaml`, `cosmic-ray` dev dep.
- **Spec:** SPECIFICATION.md §12.4, §15; CI-AND-TRUST.md §3 (`mutants-critical` job); ADR 0001 (deferral).

## Context

ADR 0001 deferred the mutation harness to "the first money module to mutate". L7 settlement is
that module, so the harness lands now. CI's `mutants-critical` job runs:

```
run_mutation.py --target l8_evidence/gates --require-kill-non-equivalent --survivors-must-be-classified
run_mutation.py --target l5b_risk l7_settle --report
```

## Decisions

1. **Engine: cosmic-ray**, driven via subprocess (`init` → `exec` → `dump`). A temp config +
   sqlite session per target; the dump (one `[work_item, work_result]` JSON line per job) is
   parsed for survivors (`test_outcome == "survived"`).

2. **Survivor identity** is `"<module_path>::<operator_name>::<occurrence>"` — stable across runs
   (cosmic-ray enumerates mutations deterministically), unlike the random per-run `job_id`.

3. **Classification file** `specs/mutation-survivors.yaml` (human-owned, CODEOWNERS). A survivor is
   allowed only if listed with `classification ∈ {equivalent-mutant, unreachable-defensive,
   tooling-limitation}`, a rationale, and `approved_by`. `--require-kill-non-equivalent` fails on an
   unclassified survivor or one classified `test-deficiency` (kill it with a test);
   `--survivors-must-be-classified` fails on any unlisted survivor; `--report` lists without enforcing.

4. **Empty targets are skipped** (0 mutants → pass). `l8_evidence/gates` and `l5b_risk` are still
   `planned` (no `.py`), so today the enforced run is vacuously green and `l7_settle` is
   report-only — matching the CI invocation. Enforcement on gates activates when gates are built.

5. **Split responsibilities for testability.** The pure logic (`parse_dump`, `load_classifications`,
   `evaluate`) is unit-tested against fixture data (fast, no cosmic-ray); the cosmic-ray subprocess
   orchestration is exercised end-to-end manually, not in the `verify` suite (mutation is slow and
   belongs in the separate `mutants-critical` job).

6. **Per-target test command** is derived by convention (`l7_settle` → `tests/unit/l7`,
   `tests/properties/l7`), overridable with `--test-command`, falling back to the whole suite.

## Consequences

- `make mutants` and the CI `mutants-critical` job are now real. Type-annotation `|`→`+` mutations
  (no runtime effect under `from __future__ import annotations`) and error-message-text mutations
  are the expected survivor classes; they are classified `tooling-limitation`/`equivalent-mutant`
  when a target becomes enforced.
- `cosmic-ray` is added to the dev dependencies (ADR 0001's deferral is now discharged).
