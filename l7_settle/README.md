# l7_settle — L7 Reconciliation & market-level settlement  ⚠️ MONEY-CRITICAL

**Layer:** L7 · **Spec:** SPECIFICATION.md §6.8 · **Criticality:** money
**Requirements:** SPEC-080, SPEC-081, SPEC-082, SPEC-083 · see `docs/spec-manifest.yaml` · **SPEC-080/082 active**
**Path-scoped rule:** `.claude/rules/moneycritical.md`.

Commission is charged on the **net market result** — per-order `commission_est` MUST NOT
exist as an authoritative field. The account statement is the accounting truth; local P&L
is a hypothesis reconciled against it, and any unresolved difference blocks all further
placement. Handles partial matches, dead heats, reduction factors, voids, resettlements.

> ⚠️ **Money-critical. Never stub.** Mutation testing + property tests. Settlement fixtures
> must cover every §6.8 case. **Status: not yet implemented.** SPEC-080/082 are `active` (Phase 1).
