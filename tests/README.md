# tests — the executable specification

**Spec:** SPECIFICATION.md §15 · **Human-owned** via `/tests/**` (see `CODEOWNERS`).

Line coverage does not prove risk logic correct. Suites (each a CI step in
`docs/CI-AND-TRUST.md` §3):

| Dir | Purpose |
|---|---|
| `unit/`              | unit tests |
| `integration/`       | integration tests |
| `properties/`        | Hypothesis property-based — the primary anti-stub defence |
| `stateful/`          | order-lifecycle model-based tests |
| `failure_injection/` | delayed acks, dropped responses, reconnects, clock skew, … |
| `replay_regression/` | canonical replay: same env digest → same canonical hash |
| `fixtures/`          | TEST_ONLY doubles — un-importable from production, never in a model/training manifest |

**Never weaken, delete, or alter a test to make an implementation pass** (CLAUDE.md rule 2).
A test correction is a separate, human-approved PR citing the SPEC-ID.

> **Status: no tests yet.** Write failing tests first, commit them separately, then implement.
