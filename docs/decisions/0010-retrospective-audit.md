# 0010 — 2026-07-16 retrospective audit: findings and remediation design

## Context

Founder-requested audit of every prior implementation session: verify that all 23 active
SPEC-IDs were built to the letter with no silent scope trims, no weakened tests, and no
violations of the three rules. Method: six independent clause-by-clause component audits
(L0/L1, L3, L5, L7, governance + repo-wide prohibitions, git-history test-integrity), each
decomposing the manifest requirement text into individual clauses and citing file:line
evidence or a finding; plus a fresh CI-grade `make verify`/`make replay`, and a cosmic-ray
mutation baseline of `l7_settle` (the only money module with real code). The lead re-verified
load-bearing citations directly.

## Audit verdict

**No rule-2 violations, no stubs, no silently trimmed requirements, no LLM in any numeric
path.** `docs/SPECIFICATION.md`, `docs/spec-manifest.yaml`, `docs/facts.yaml` and
`.claude/rules/` were touched only by the bootstrap commit. Every Makefile/CI change in
history was enforcement-adding. TDD red-then-green ordering held for every slice except the
mutation harness itself (`0ba508f`, tools/support criticality — tests and implementation in
one commit; recorded, not repairable without rewriting pushed history). All findings were
verification-net gaps or structural hardenings, not functional defects: the auditors' probes
plus the new tests confirmed the shipped arithmetic and guards behave correctly.

## Findings and remediation decisions

1. **L3 guards were conventions, not structure** (HIGH). Direct `Feature(...)` construction
   bypassed the SPEC-020/023 leakage guards, and SPEC-022's explicit build mode was wired to
   nothing. Decision: the `Feature` type runs the guards itself in a `mode="before"`
   validator requiring a `FeatureBuildContext` via pydantic validation context;
   `build_feature` derives the knowability boundary from the context (live → scheduled
   start; post-hoc → actual off, else scheduled start). **Design note:** pydantic 2.13 in
   strict mode re-validates nested model instances (even with `revalidate_instances=
   "never"`), with `context=None`; the guard therefore admits already-constructed frozen
   `Feature` instances (mint-time guarding) and demands the context only when constructing
   from raw data. `model_construct`/`model_copy` remain pydantic's documented no-validation
   escape hatches, as everywhere in this codebase.
2. **Equal instants hashed differently across UTC offsets** (SPEC-024). Decision: aware
   datetimes normalise to UTC in `mode="before"` validators (stamps, provenance, build
   context); naive datetimes still rejected with the original error types.
3. **Two of §6.2's four reproducibility digests did not exist** (SPEC-011). Decision:
   `ReductionResult` records `config_digest` (sha256 of the reducer's canonical config,
   registered at the registry site — empty JSON object for `reducer-mcm-v1`) and
   `container_digest` (sha256 of a deterministic environment manifest: interpreter,
   platform, pydantic version — the honest v1 meaning of "container" in an offline research
   environment with no image digest). Digests ride alongside the canonical payload and MUST
   NOT enter `canonical_bytes`; the pinned golden replay hashes did not move.
4. **SPEC-012 version-bump discipline was heuristic.** Decision: a source pin test
   (sha256 of `mcm_v1.py`) turns any reducer source change into a failing test until the
   version is bumped or the pin is consciously re-set in a reviewed commit.
5. **`stream_clock` was typed `int`** but Betfair's `clk`/`initialClk` is an opaque base64
   string. Widened to `str | None` now, while no persisted data exists.
6. **SPEC-082 verification holes** (multi-runner, ABANDONED, multi-factor reduction,
   dead-heat×reduction, rounding-mode discrimination, no pnl property tests). Decision:
   additive directed + property tests; the commission-on-net vs per-order distinction is now
   pinned by a case where the two disagree (245 ≠ 242).
7. **Mutation was unenforced on the only real money module** (CI's enforced target is the
   still-empty `l8_evidence/gates`; `l7_settle` ran report-only — disclosed in ADR 0008 but
   below CLAUDE.md's stated bar). Decision: drive `l7_settle` to zero non-equivalent
   survivors via killer tests plus two semantics-identical mutation-hostile restructures
   (drop the redundant dead-heat==1 fast path — an equivalent-mutant factory; reorder
   `ledger.apply` so equality is reached by fall-through and every comparison is
   observable). True equivalent mutants (e.g. enum `==` vs `is` — indistinguishable for
   singletons) are classified in `specs/mutation-survivors.yaml` with rationale;
   **`approved_by` is a human field and stays empty until the founder approves**, so the CI
   escalation of `l7_settle` to `--require-kill-non-equivalent` waits on that approval.
   Mutation runs execute in disposable git worktrees — an interrupted run can no longer
   leave a mutant applied to the working tree (retires the ADR 0008 hazard).
8. **Budget separation was label-based** (SPEC-103). Decision: nominal account subclasses
   with pinned kinds typed into `SeparatedBudgets` (mypy layer) plus an exact-type runtime
   backstop — the SPEC-102 two-layer pattern.
9. **Quarantine checker blind spots** (SPEC-100): literal `importlib.import_module`/
   `__import__` targets are resolved as import edges (module and function aliases included);
   non-literal dynamic imports and unreadable/unparseable files fail closed, scoped to
   modules reachable from `--from`. Runtime dependency injection remains inherently outside
   any static import-graph mechanism (documented boundary).
10. **SPEC-101 had no standalone gate check.** Decision: `tools/check_licensed_sources.py`,
    invoked by `make verify` and CI.
11. **Escape-hatch grep gaps** (case-sensitive, no synonyms, no bare `pass`, money dirs
    only). Decision: case-insensitive bounded pattern + evidence-layer coverage. Zero hits
    at adoption.
12. **SPEC-080/082 declared no `relevant_inputs`/`metamorphic_properties`** (the checker's
    both-absent rule hid it). Decision: declared in the manifest, mirroring what the tests
    already exercise. Tightening-only edit to the human-owned manifest, flagged to the
    founder.

## Accepted interpretations / recorded boundaries

- SPEC-023 "feature registry" = per-feature `SourceProvenance` (no separate catalogue is
  defined by the spec; a training-manifest catalogue arrives with L4).
- SPEC-082 "unknown order status after timeout": the settlement layer blocks on unknown
  market/runner status; order-level timeout semantics belong to the SPEC-070 order state
  machine (`l6_broker`, phase 3) and MUST be revisited there — recorded so it cannot be
  silently lost.
- SPEC-050's conservative-lower-bound *provenance* is SPEC-034's obligation (Phase 2);
  l5 enforces the type boundary (`WinProbabilityLowerBound`), per ADR 0005.
- Cross-version reducer coexistence (SPEC-012) is architecturally supported but untestable
  until a second reducer version exists; re-audit then.
- Branch protection / required-check enforcement on the hosting platform cannot be verified
  from inside the repo; it remains the root of trust behind CI claims.

## Consequences

`make verify` now runs 12 checks including licensing and evidence-layer anti-stub greps;
the full suite grew from 269 to 350+ tests; `l7_settle` mutation stands at zero
non-equivalent survivors pending the founder's classification approvals for the handful of
true equivalents; and the L8 gate-evaluator slice (deferred by this audit) resumes next.
