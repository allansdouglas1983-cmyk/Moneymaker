# l8_evidence — L8 Evidence (trial ledger, gate evaluator, diagnostics)

**Layer:** L8 · **Spec:** SPECIFICATION.md §9, §10 · **Criticality:** evidence (gates/ is money)
**Requirements:** SPEC-090…SPEC-097 · see `docs/spec-manifest.yaml` · **Phase 2/5 (`planned`)**
**Path-scoped rule:** `.claude/rules/evidence.md`.

Race-level paired inference (block bootstrap by meeting-day; runner-level independence
forbidden). Immutable trial ledger with multiplicity accounting. Lockbox inspected once,
at Gate 1 only. CLV is a diagnostic family, never a training target. Anytime-valid
monitoring only. The deterministic gate evaluator lives in `gates/` (see its README).

> **Status: not yet implemented.** Scaffold marker.
