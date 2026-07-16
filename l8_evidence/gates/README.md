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

**Implemented** (ADR 0011): `outcomes.py` (four-valued enum + frozen result, both refuse
`bool()`), `spec.py` (structure-only loader, numeric leaves refused, sha256-bound),
`experiment.py` (§9.7 record, floats refused), `facts.py` (§13.5 freshness join),
`evaluator.py` (pure, deterministic, safety-first precedence, exact-multiplication
multiplicity), `cli.py` (exit codes PASS 0 / CONTINUE 1 / FAIL_HARM 2 / FAIL_FUTILITY 3 /
error 4). The repo root is not a packaged project, so the `gate` entry point is invoked as
`uv run python -m l8_evidence.gates.cli evaluate …` with exactly the pinned arguments;
experiment records resolve from `--experiment-root` (default `ledger/experiments`).
