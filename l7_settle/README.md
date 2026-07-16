# l7_settle — L7 Reconciliation & market-level settlement  ⚠️ MONEY-CRITICAL

**Layer:** L7 · **Spec:** SPECIFICATION.md §6.8 · **Criticality:** money
**Requirements:** SPEC-080, SPEC-082 **implemented**; SPEC-081, SPEC-083 `planned` · **Design:** `docs/decisions/0007-l7-settlement.md`
**Path-scoped rule:** `.claude/rules/moneycritical.md`.

Commission is charged on the **net market result** — a per-order `commission_est` MUST NOT
exist as an authoritative field. Exact integer minor units / `Decimal`, never float.

## Modules
| Module | Responsibility | SPEC |
|---|---|---|
| `outcomes.py`   | `MarketStatus`/`RunnerResult` enums; `MatchedPosition`, `RunnerOutcome`, `MarketOutcome` (no per-order commission) | SPEC-080/082 |
| `pnl.py`        | per-position gross P&L: win/lose/void, Betfair reduction factors, dead-heat split, per-bet `ROUND_HALF_UP` | SPEC-080/082 |
| `settlement.py` | `settle_market` → `MarketSettlement` (§6.8 schema); commission on net only; unknown-status blocks; void→0; scenario matrix | SPEC-080/082 |
| `ledger.py`     | `SettlementLedger` — idempotent duplicate acks, versioned resettlements, conflict/stale refusal | SPEC-082 |

## Mutation posture (ADR 0010)
**Enforced**: CI runs `run_mutation.py --target l8_evidence/gates l7_settle
--require-kill-non-equivalent --survivors-must-be-classified`. Standing: 329 mutants,
321 killed; the 8 survivors are founder-approved equivalent mutants (enum singleton
identity, ×0 identity at net==0, one dominated comparison domain) classified in
`specs/mutation-survivors.yaml`, whose entry set is pinned by a test.

## Invariants under test
- Commission is charged only on net winnings; `final = net − commission − charges`; commission
  monotone in the rate; a losing market is never charged (SPEC-080, property-tested).
- Reduction factors use Betfair semantics (not "Rule 4"); dead heats split the stake; results
  round to minor units per bet (SPEC-082).
- Unknown status raises `SettlementBlocked`; void/abandoned settles to zero.
- Duplicate acknowledgements add no exposure; resettlements supersede by version (SPEC-082,
  property-tested).

SPEC-081 (account statement is truth) and SPEC-083 (differential reconciliation) are Phase-3
`planned`; local settlement here is the hypothesis those later gates reconcile against.

Tests: `tests/unit/l7/`, `tests/properties/l7/`.
