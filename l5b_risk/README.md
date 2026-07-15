# l5b_risk — L5b Risk (budget, caps, kill switch, watchdog)  ⚠️ MONEY-CRITICAL

**Layer:** L5b · **Spec:** SPECIFICATION.md §6.7 · **Criticality:** money
**Requirements:** SPEC-060…SPEC-065 · see `docs/spec-manifest.yaml` · **Phase 3 (`planned`)**
**Path-scoped rule:** `.claude/rules/moneycritical.md`.

Fixed minimum stake + absolute experiment-loss budget (NOT Kelly). Skip when exchange
minimum exceeds permitted risk — never round up into a breaching bet. Unknown order state
blocks ALL placement. Kill switch is 7-part and never auto-hedges. Loss budget is
monotonically non-increasing absent a logged, human-approved top-up. Watchdog runs
**outside** the trading process.

> ⚠️ **Money-critical. Never stub.** Property tests on declared relevant inputs; mutation
> testing on this tree. **Status: not yet implemented** — Phase 3 IDs are `planned`.
