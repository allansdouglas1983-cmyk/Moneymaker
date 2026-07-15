# 0007 — L7 market-level settlement (SPEC-080/082)

- **Status:** Accepted
- **Date:** 2026-07-15
- **Scope:** `l7_settle/` (SPEC-080, SPEC-082 — both `money`).
- **Spec:** SPECIFICATION.md §6.8, §6.10; spec-manifest SPEC-080/082.

## Context

Settlement computes market P&L from matched positions and the market outcome. Betfair commission
is on the **net market result**, so per-order commission is artificial and forbidden. v1 places
one BACK position per market, but SPEC-082 requires the engine to *handle* multiple orders,
multiple runners, dead heats, reduction factors, voids, resettlements, rounding, duplicate acks
and unknown status — so the engine is general (BACK-only, no lay in v1).

## Decisions

1. **Money types.** Stakes and all P&L are exact **integer minor units** (pence); odds and
   reduction factors are exact `Decimal`; commission rate is `Decimal`. No float anywhere. There
   is **no `commission_est` field on any position** (SPEC-080) — commission exists only at the
   market level.

2. **Per-position gross P&L** (`pnl.py`). For a BACK stake `S` (minor units) at matched odds `O`:
   - Effective odds after reduction factors: `E = 1 + (O − 1)·∏(1 − rf_i)` for the runners removed
     *after* this bet was matched (each position carries its own applicable RFs — match/removal
     timing is decided upstream, not re-derived here). Betfair reduction-factor semantics, **not**
     bookmaker "Rule 4".
   - WINNER (dead-heat count `D`): `S/D·(E − 1) − S·(D−1)/D` (for `D = 1` this is `S·(E − 1)`).
   - LOSER: `−S`. REMOVED (this bet's own runner) or VOID market: `0` (stake returned).
   - Each position's P&L is rounded to minor units with `ROUND_HALF_UP` (Betfair settles per bet),
     then summed — see decision 4.

3. **Commission on the net market result** (`settlement.py`, SPEC-080). `actual_net_market_pnl` is
   the sum of per-position rounded P&L. `actual_commission = round(rate · max(0, net))` — commission
   is charged only on net winnings, never on a loss. `final_net_pnl = net − commission − transaction_charges`.
   `gross_pnl_by_selection_scenario` is the payoff matrix: for each non-removed runner, the net
   market P&L if that runner is the sole winner.

4. **Rounding** is per bet, to minor units, `ROUND_HALF_UP`. Betfair settles each bet to the penny
   and the statement sums them; the exact rounding mode is a dated operational fact (§13.4) —
   `ROUND_HALF_UP` is the documented default here, changeable via the facts registry.

5. **Unknown status blocks settlement** (SPEC-082). If the market status or any relevant runner
   status is `UNKNOWN`, `settle_market` raises `SettlementBlocked` — a settlement is never guessed.
   `VOID`/`ABANDONED` markets settle every position to `0`.

6. **Idempotent, versioned ledger** (`ledger.py`, SPEC-082). `SettlementLedger.apply`:
   - a duplicate acknowledgement (same `market_id` + `settlement_version`) is idempotent — it must
     be byte-identical or it raises `SettlementConflict`; it never doubles exposure;
   - a resettlement (higher `settlement_version` **with** `resettlement_flag`) supersedes;
   - a higher version without the flag, or a stale (lower) version, raises `SettlementConflict`.

7. **The mutation harness lands with this slice** (ADR 0008) — `l7_settle` is its first real
   target. Settlement is not the account-statement reconciliation itself (SPEC-081/083 are
   `planned`); local settlement here is the hypothesis those later gates reconcile against.

## Consequences

- SPEC-080 and SPEC-082 (money) each get spec-marked property tests under `tests/properties/l7/`
  (commission-on-net monotonicity and the settlement identity; ledger idempotency and void→0).
- After this slice all 23 active IDs are covered.
- Sporting result vs contractual settlement (§6.10) stays separate: this module measures P&L from
  Betfair's settlement, not from the sporting result.
