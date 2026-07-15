# l5_decision — L5 Decision (EV, execution policy, tick arithmetic)  ⚠️ MONEY-CRITICAL

**Layer:** L5 · **Spec:** SPECIFICATION.md §6.6 · **Criticality:** money
**Requirements:** SPEC-050, SPEC-051, SPEC-052, SPEC-053, SPEC-054 · see `docs/spec-manifest.yaml` · **active**
**Path-scoped rule:** `.claude/rules/moneycritical.md`.

`EV = p·(O−1)·(1−c) − (1−p)` per unit stake, single position only, using **odds_exec**
(never p_market_info, never p_close — distinct types) and the conservative lower bound of
the edge distribution. v1 execution is `taker-v1` (FOK, minFillSize = full stake, no resting
remainder). Price is an integer tick index into the canonical ladder — never a float.

> ⚠️ **Money-critical. Never stub or let an LLM produce a number here.** CI grep +
> pylint W0613 + mutation testing + property tests apply. `persistenceType: LAPSE` and a
> `marketVersion` guard on every order; passive posting unreachable until Gate 4.
> **Status: not yet implemented.** Several SPEC-IDs here are `active` (Phase 1).
