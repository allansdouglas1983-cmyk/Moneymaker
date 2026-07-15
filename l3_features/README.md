# l3_features — L3 Features (knowledge-time aware) + leakage guard

**Layer:** L3 · **Spec:** SPECIFICATION.md §6.3 · **Criticality:** evidence
**Requirements:** SPEC-020, SPEC-021, SPEC-022, SPEC-023, SPEC-024 · see `docs/spec-manifest.yaml`
**Path-scoped rule:** `.claude/rules/evidence.md` loads when you edit this tree.

Six knowledge-time stamps per feature; a feature not provably knowable before the off is
rejected at build time (error, not warning). Reconciled BSP joins at grading only.
Actual-off time is post-hoc only. Backfill does not confer historical validity.

> **Status: not yet implemented.** Scaffold marker.
