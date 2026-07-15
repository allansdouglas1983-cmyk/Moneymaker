# l3_features — L3 Features (knowledge-time aware) + leakage guard

**Layer:** L3 · **Spec:** SPECIFICATION.md §6.3 · **Criticality:** evidence
**Requirements:** SPEC-020, SPEC-021, SPEC-022, SPEC-023, SPEC-024 · see `docs/spec-manifest.yaml`
**Path-scoped rule:** `.claude/rules/evidence.md` loads when you edit this tree.

Knowledge-time stamps per feature; a feature not provably knowable before the off is
rejected at build time (error, not warning). Reconciled BSP joins at grading only.
Actual-off time is post-hoc only. Backfill does not confer historical validity.

## Modules

- `knowledge_time.py` — `KnowledgeStamps` (§6.3 timestamps), `SourceProvenance`
  (live-captured vs backfilled + true publication time), and `assert_knowable_before_off`
  (build-time `LeakageError`). SPEC-020, SPEC-023.
- `build_context.py` — `FeatureBuildContext` with an explicit `BuildMode`; actual-off seconds
  raise `LiveModeViolation` in live mode. SPEC-022.
- `leakage.py` — runtime BSP guard (`assert_no_bsp`) detecting the reconciled-BSP taint marker
  without importing the grading-only module. The static half is the import-graph gate over
  `l8_evidence.reconciled_bsp`. SPEC-021.
- `feature_set.py` — `build_feature` (the single guarded construction path) and the
  order-independent, no-float `feature_set_hash`. SPEC-024.

See `docs/decisions/0004-l3-knowledge-time.md`. The concrete `p_market_info` feature awaits the
frozen `specs/prices/info-price-v1.yaml` (a human Phase-0 decision) and is intentionally not
built here.
