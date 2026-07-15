# 0001 — Verification tooling: marker-based SPEC coverage; run_mutation deferred

- **Status:** Accepted
- **Date:** 2026-07-15
- **Scope:** `tools/`, `tests/`, `pyproject.toml`. No money module is touched.

## Context

`CLAUDE.md` mandates "Status comes from CI, never from your own prose claim" and
"Verify before claiming done" via `make verify`. But every step of `make verify` and of
`.github/workflows/verify.yml` invokes a `tools/*.py` script that did not exist. Until
those exist, no spec slice can be verified, so the verification harness is the dependency
root and therefore the first slice built. Several design points are under-specified by
SPECIFICATION.md §12.3–§12.4 and must be pinned down; this ADR records those choices.

## Decisions

1. **Test → SPEC-ID coverage via a pytest marker: `@pytest.mark.spec("SPEC-XXX")`**
   (function, class, or module-level `pytestmark`). The manifest
   (`docs/spec-manifest.yaml`) remains the single authoritative ID registry. Coverage is
   attributed at file granularity (which SPEC-IDs a test file references, and whether that
   file is a property test). Bidirectional invariant: every enforced `active`/`verified` ID
   needs ≥1 referencing test; every referenced ID must exist in the manifest (else it is an
   "unknown ID" — SPECIFICATION.md §12.3).

2. **Division of labour.** `check_spec_coverage.py` verifies *declaration + coverage +
   consistency* (a referencing test exists, a property test exists for money IDs, causal
   declarations are complete, no unknown references, no verification loss). The separate
   `pytest` steps in CI enforce that those tests *pass*. Together they satisfy §12.3's "any
   ID lacks a passing test". A checker that also executed pytest would duplicate the
   dedicated pytest steps and couple concerns.

3. **`--require-properties-for money`**: every enforced money ID needs ≥1 marker in a file
   under `tests/properties/` (SPECIFICATION.md §12.4, §15 — property-based tests are the
   primary anti-stub defence for the numerical core).

4. **`--require-causal-declarations` = completeness, not universality.** An enforced money
   ID that declares *either* `relevant_inputs` or `metamorphic_properties` MUST declare
   *both* (non-empty). Structural/guard money IDs that legitimately have neither — e.g.
   SPEC-051 (three prices are distinct *types*), SPEC-054 (one runner per market), SPEC-102
   (no Delayed-key real money), SPEC-103 (budget separation) — are **not** forced to invent
   numerical declarations. This mirrors the manifest as authored: only the numerical
   decision IDs (EV, stake, fill, stage-two, gate) carry declarations. Forcing declarations
   onto structural IDs would require *fabricating* metamorphic properties, which the money
   rules forbid. Tightening this to "all money IDs must declare" is a legitimate but
   **human-owned** manifest change (CODEOWNERS covers `docs/spec-manifest.yaml`); the tool
   enforces whatever the manifest actually declares.

5. **Facts freshness semantics** (`check_facts_freshness.py`): a fact with a null
   `recheck_by` **and** a null `value` is UNPOPULATED → OK (not yet in use); a fact with a
   value but no `recheck_by` is a misconfiguration → FAIL; a `recheck_by` before the
   as-of date is STALE → FAIL (SPECIFICATION.md §13.5). `--as-of` is injectable for tests;
   it defaults to today (UTC). At bootstrap every fact is null, so the check passes — the
   registry is not yet relied upon by any active gate.

6. **Import quarantine** (`check_import_quarantine.py`): a transitive static import-graph
   walk (AST) from the `--from` packages; any reachable first-party module that imports the
   `--forbid` package (or a submodule) is a violation, reported with the import chain
   (SPECIFICATION.md §13.1, SPEC-100). Licence *taint* through copied data (§6.12) is a
   separate, non-static concern and out of scope for this static check.

7. **`run_mutation.py` is DEFERRED** to the first slice that introduces a money module with
   property tests — its first real mutation target. Rationale: there is nothing to mutate
   yet; an isolated mutation orchestrator cannot be validated end-to-end, and §11 warns
   against building generic plumbing in isolation. Until then `make mutants` and the
   `mutants-critical` CI job report red (they run only on pull requests). `cosmic-ray` is
   therefore added to the dev dependencies in that later slice, not now.

## Consequences

- `make verify` remains **red** until the Phase-1 `active` IDs are implemented and covered.
  The tools reporting uncovered active IDs is them working, not failing.
- The four `verify`-job tools are green on their own unit tests (`tests/unit/tools/`) and
  clean under `ruff` and `mypy --strict`.
- The marker convention (`@pytest.mark.spec`) is now the contract every later slice uses to
  declare which SPEC-IDs its tests cover.
