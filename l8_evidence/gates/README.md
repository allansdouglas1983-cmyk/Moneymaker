# l8_evidence/gates — Deterministic gate evaluator  ⚠️ MONEY-CRITICAL

**Spec:** SPECIFICATION.md §10 · **Criticality:** money
**Requirements:** SPEC-093 · see `docs/spec-manifest.yaml` · **Phase 2 (`planned`)**
**Path-scoped rule:** `.claude/rules/moneycritical.md`.

`gate evaluate --spec specs/gates/v1.yaml --experiment <id> --data-manifest sha256:…
--model-manifest sha256:… --facts-registry docs/facts.yaml` returns a result from a
versioned spec bound to data and model hashes. **An LLM MUST NOT decide a gate.** Every
evidence gate returns one of **PASS | CONTINUE | FAIL_HARM | FAIL_FUTILITY — never a
boolean.** Stale facts (past `recheck_by`) must fail the gate. Constructed
insufficient-evidence inputs must never return PASS.

> ⚠️ **Money-critical. Never stub.** 100% of NON-EQUIVALENT mutants killed; every survivor
> classified + human-approved. Property test on insufficient-evidence inputs.
> **Status: not yet implemented** — Phase 2 IDs are `planned`.
