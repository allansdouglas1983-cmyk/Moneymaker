# l4b_fill — L4b Fill-probability model  ⚠️ MONEY-CRITICAL

**Layer:** L4b · **Spec:** SPECIFICATION.md §6.5 · **Criticality:** money
**Requirements:** SPEC-040, SPEC-041, SPEC-042, SPEC-043 · see `docs/spec-manifest.yaml` · **Phase 5 (`planned`)**
**Path-scoped rule:** `.claude/rules/moneycritical.md`.

Outputs `P(filled by τ | x, a)` with uncertainty — **not** an exact queue position (queue
position is latent and unrecoverable from historical data). Three envelopes always computed
together: pessimistic / optimistic / calibrated. **Optimistic-only profitability is a rejection.**

> ⚠️ **Money-critical. Never stub, placeholder, constant-return, or simplify.** If a
> SPEC-ID cannot be implemented fully, STOP and report which and why. CI greps this tree
> for escape hatches and runs mutation testing. Property tests on declared relevant inputs.
> **Status: not yet implemented** — Phase 5 IDs are `planned`.
