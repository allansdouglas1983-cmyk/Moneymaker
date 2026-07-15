# 0004 — L3 knowledge-time semantics & leakage guards

- **Status:** Accepted
- **Date:** 2026-07-15
- **Scope:** `l3_features/` and `l8_evidence/reconciled_bsp.py`
  (SPEC-020, SPEC-021, SPEC-022, SPEC-023, SPEC-024 — all `evidence`).
- **Spec:** SPECIFICATION.md §6.3; spec-manifest SPEC-020..024; `.claude/rules/evidence.md`.

## Context

L3 is where leakage manufactures a phantom edge (SPECIFICATION §16.3). This slice implements
the **framework guards** that keep un-knowable information out of features. It deliberately
does **not** compute any concrete feature: the actual `p_market_info` construction needs
`specs/prices/info-price-v1.yaml`, a frozen Phase-0 human decision (§4) that is not
agent-fabricated. The guards stand alone and gate every future feature.

No money logic lives here — this is evidence integrity. An LLM never prices anything.

## Decisions

1. **Knowledge-time stamps as a frozen contract** (`knowledge_time.py`, SPEC-020).
   `KnowledgeStamps` carries the §6.3 timestamps: `event_time`, `source_publication_time`,
   `provider_timestamp`, `ingestion_receive_time`, `first_usable_time`, and the
   later-known `decision_time` / `correction_time` (default `None` — unknown at build time).
   All are required timezone-aware UTC.

2. **Rejection is a build-time error, never a warning** (SPEC-020).
   `assert_knowable_before_off(stamps, market_off, source=…)` raises `LeakageError` unless
   `first_usable_time` is **strictly** before the off. "Provably before" is strict: a value
   first usable *at* the off is out. A timezone-naive `market_off` is itself unprovable and
   rejected.

3. **`LeakageError` is not a `ValueError`.** Pydantic re-wraps only `ValueError`/`AssertionError`
   raised inside a validator into a `ValidationError`. Making `LeakageError` a plain `Exception`
   lets it propagate **unwrapped** from `SourceProvenance`/`KnowledgeStamps` validators, so
   callers catch a clean, specific leakage error rather than a generic validation failure.

4. **Backfill does not confer historical validity** (`SourceProvenance`, SPEC-023).
   A `BACKFILLED` source MUST declare `true_publication_time` (enforced in the model). And
   `assert_knowable_before_off` rejects any backfilled feature whose `first_usable_time`
   precedes that true publication — populating a first-seen timestamp during backfill cannot
   make a retrospective file knowable earlier than it was actually published.

5. **Actual-off time is not a live feature** (`build_context.py`, SPEC-022).
   `FeatureBuildContext` requires an explicit `BuildMode` (no default). `seconds_to_scheduled_off`
   is always available; `seconds_to_actual_off` raises `LiveModeViolation` in `LIVE` mode
   (unconditionally, even if `actual_off` happens to be populated) and is available only in
   `POST_HOC` mode. `LiveModeViolation` is a `RuntimeError`, distinct from the `ValueError`
   raised when post-hoc mode simply lacks `actual_off`, so a leak is never confused with
   missing data.

6. **BSP-leakage guard has two independent mechanisms** (SPEC-021).
   - *Static:* reconciled BSP lives in `l8_evidence/reconciled_bsp.py`; a dedicated
     import-graph gate (`tools/check_import_quarantine.py --forbid l8_evidence.reconciled_bsp
     --from l3_features`) forbids any path from L3 to it, wired into CI and `make verify`
     alongside the scraping quarantine.
   - *Runtime:* `l3_features.leakage.assert_no_bsp` rejects a reconciled-BSP value used as a
     feature input. It detects the value **structurally** via a class-level taint marker and
     deliberately does **not** import the grading-only module — importing it would create
     exactly the forbidden edge the static gate exists to prevent. The marker string is
     duplicated (not imported) and a test asserts the two literals agree so they cannot drift.

7. **Reproducible feature-set hash** (`feature_set.py`, SPEC-024).
   `feature_set_hash` is `sha256` of a deterministic, order-independent canonical serialisation.
   Feature values are limited to `bool | int | Decimal | str | None` — **no float** — both to
   honour "Decimal, never float" for numeric quantities and to keep the hash independent of
   platform float formatting. Decimals are numeric-normalised (`format(d.normalize(), "f")`),
   so `12.5` and `12.50` hash identically. `Feature`/`FeatureSet` are `strict=True` pydantic,
   so a float is rejected rather than silently coerced.

8. **`build_feature` is the single construction path.** It accepts `value: object` on purpose
   — the runtime BSP guard exists to catch values the static type graph might not — and applies
   the guards in order: BSP (SPEC-021) → knowable-before-off (SPEC-020/023) → allowed-scalar
   type check.

## Consequences

- SPEC-020..024 are covered: `check_spec_coverage` drops them from the uncovered list; the
  remaining active IDs (L5 decision, L7 settle, governance) keep `make verify` red by design.
- A property test (`tests/properties/l3/`) proves SPEC-024 hashing is order-independent and
  value-sensitive over generated feature sets, though `evidence` IDs do not require one.
- The static BSP gate is now a named CI step mirroring SPEC-100's scraping quarantine, so the
  static half of SPEC-021 is enforced independently of the pytest suite.

## Note on the test-hygiene commit

The failing tests were committed first (TDD, per §16). A subsequent test-only commit removed
three unused `# type: ignore` comments and rephrased one always-true enum comparison to satisfy
`mypy --strict` — **no assertion or test logic changed**. Implementation and tests remain in
separate commits.

## Amendment (advisory review, 2026-07-15)

An advisory verifier (SPECIFICATION.md §16.4) reviewed the slice — confirming nothing is
stubbed, no LLM makes a numeric decision, and no test was weakened. Findings addressed by
strengthening guards and adding tests (never loosening one):

- **SPEC-021 (HIGH) — the anti-drift net was documented but absent.** `leakage.py` duplicates
  the BSP taint string (it must not import the grading-only module), and the docstring claimed
  a test kept the two literals in sync — but none existed, so an edit to either could silently
  turn the runtime guard into a no-op. Added
  `test_taint_marker_matches_grading_module` asserting
  `l3_features.leakage._RECONCILED_BSP_TAINT == l8_evidence.reconciled_bsp.RECONCILED_BSP_TAINT`
  (importing both from a *test* creates no forbidden edge). The grading module now exports
  `RECONCILED_BSP_TAINT` as the single source of truth.
- **SPEC-022 (MEDIUM) — actual_off was a readable leakage surface in live mode.** The guarded
  method refused it, but a live builder could still read `ctx.actual_off` directly. The
  validator now rejects a non-`None` `actual_off` on a `LIVE` context at construction
  (`LiveModeViolation`), so a live context structurally cannot carry it. The method-level guard
  is retained as defence in depth. The corresponding test was tightened to assert the stronger
  construction-time rejection.
- **SPEC-020 (MEDIUM) — no coherence floor on first_usable_time.** Live-captured sources had no
  analogue to the backfill `true_publication_time` floor, so a caller could declare a value
  usable before it was received or published. `KnowledgeStamps` now rejects
  `first_usable_time < ingestion_receive_time` and `first_usable_time < source_publication_time`
  as build-time `LeakageError`s.
- **SPEC-024 (LOW/NIT) — untested collision path and signed zero.** Added a duplicate-name
  order-independence test (exercising the total-order sort's collision branch) and normalised
  `Decimal("-0")` to `Decimal("0")` so numerically-equal signed zeros hash identically, with a
  test.
- **Inherent, noted not fixed:** the runtime BSP guard sees the wrapper object, not a plain
  `Decimal` extracted from it — acceptable because the static import-graph gate is the primary
  defence (SPEC-021's "second line of defence" framing).
