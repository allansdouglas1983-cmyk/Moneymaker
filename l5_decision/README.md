# l5_decision — L5 Decision (EV, execution policy, tick arithmetic)  ⚠️ MONEY-CRITICAL

**Layer:** L5 · **Spec:** SPECIFICATION.md §6.6 · **Criticality:** money
**Requirements:** SPEC-050, SPEC-051, SPEC-052, SPEC-053, SPEC-054 · see `docs/spec-manifest.yaml` · **active**
**Path-scoped rule:** `.claude/rules/moneycritical.md`.

`EV = p·(O−1)·(1−c) − (1−p)` per unit stake, single position only, using **odds_exec**
(never p_market_info, never p_close — distinct types) and the conservative lower bound of
the edge distribution. v1 execution is `taker-v1` (FOK, minFillSize = full stake, no resting
remainder). Price is an integer tick index into the canonical ladder — never a float.

> ⚠️ **Money-critical. Never stub or let an LLM produce a number here.** CI grep +
> pylint W0613 + property tests + `mypy --strict` apply. `persistenceType: LAPSE` and a
> `marketVersion` guard on every order; passive posting unreachable until Gate 4.

## Modules

- `ladder.py` — canonical 350-tick Betfair ladder (exact `Decimal`); `price_of`/`index_of` exact
  inverses; floats/bools rejected as indices, floats rejected as prices. SPEC-053.
- `prices.py` — `OddsExec` / `MarketInfoPrice` / `ClosePrice` as **unrelated** frozen types, so
  the type system prevents conflation. SPEC-051.
- `ev.py` — `expected_value = p·(O−1)·(1−c) − (1−p)` (exact `Decimal`) consuming a
  `WinProbabilityLowerBound` (never a point estimate), `OddsExec`, and a `CommissionRate`. SPEC-050.
- `one_runner.py` — `select_market_position` (highest conservative net EV, lowest-id tie-break,
  rejected recorded) + `MarketPositionLedger` refusing any second position. SPEC-054.
- `execution.py` — `TakerV1Order` / `taker_v1` pinned to FOK + LAPSE + minFill==stake +
  marketVersion, back-only; passive posting unreachable. Stakes are integer minor units. SPEC-052.

See `docs/decisions/0005-l5-decision.md`. The conservative edge **distribution** that produces
the `WinProbabilityLowerBound` is L4 (SPEC-034, Phase 2) and is not built here.
