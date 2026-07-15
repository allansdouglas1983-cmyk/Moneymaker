# l6_broker — L6 Broker (flumine wiring, order state machine)  ⚠️ MONEY-CRITICAL

**Layer:** L6 · **Spec:** SPECIFICATION.md §5, §15 · **Criticality:** money
**Requirements:** SPEC-070, SPEC-071, SPEC-072, SPEC-073, SPEC-074 · see `docs/spec-manifest.yaml` · **Phase 3 (`planned`)**
**Path-scoped rule:** `.claude/rules/moneycritical.md`.

Order state machine (illegal transitions raise; stateful/model-based test required).
Idempotent placement via `customerOrderRef` — a duplicate command adds no economic exposure.
`marketVersion` guard: lapse rather than match into a changed market. Transaction-rate alarm
well below the qualifying-per-hour threshold. Stream API preferred over polling.

> ⚠️ **Money-critical. Never stub.** Mutation testing on the state machine; property test
> for exposure invariance under duplicated commands. **Status: not yet implemented** — `planned`.
