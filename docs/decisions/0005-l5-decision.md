# 0005 — L5 decision layer (EV, price types, tick ladder, one-runner, taker-v1)

- **Status:** Accepted
- **Date:** 2026-07-15
- **Scope:** `l5_decision/` (SPEC-050, 051, 052, 053, 054 — all `money`, all `active`).
- **Spec:** SPECIFICATION.md §6.6; spec-manifest SPEC-050..054; `.claude/rules/moneycritical.md`.

## Context

The **first money-critical module**. The three rules apply in full: nothing stubbed, no test
weakened, no LLM in any numeric path. Every money SPEC-ID needs a spec-marked test **and** a
property test; SPEC-050 additionally declares `relevant_inputs`/`metamorphic_properties`, which
are tested directly. SPEC-051–054 declare neither (both-or-neither is satisfied) and are treated
as structural/guard IDs — still property-tested.

## Decisions

1. **Canonical tick ladder is data, built once with exact `Decimal`** (`ladder.py`, SPEC-053).
   350 ticks, `1.01`–`1000`, ten bands. Band tops belong to the higher band (so `2.00` is the
   first tick of the `.02` band). `price_of`/`index_of` are exact inverses; the reverse lookup is
   a dict keyed by `Decimal`, which hashes by value, so `2`, `2.0`, `2.00` resolve to one tick.
   Floats and bools are rejected as indices; floats are rejected as prices; off-ladder prices
   raise. **No float ever represents a price.**

2. **Three prices are unrelated frozen types** (`prices.py`, SPEC-051). `OddsExec`,
   `MarketInfoPrice`, `ClosePrice` share no base but `BaseModel`, so a function requiring
   `OddsExec` will not type-check against the others. `OddsExec`/`ClosePrice` carry integer tick
   indices; `MarketInfoPrice` carries an implied probability in `(0,1)`. Consumers also guard at
   runtime for dynamically-typed call sites.

3. **EV is exact and typed at both ends** (`ev.py`, SPEC-050).
   `EV = p·(O−1)·(1−c) − (1−p)` in `Decimal`. `O` comes only from `OddsExec`; `p` is a
   `WinProbabilityLowerBound` — a distinct type expressing the **conservative lower bound**, so a
   bare probability or point estimate is not consumable (anticipating SPEC-034's type
   enforcement; producing a genuine lower bound from the edge distribution is L4/Phase-2 work,
   not fabricated here). Runtime `isinstance` guards reject `p_close`/`p_market_info` as odds and
   a bare `Decimal` as the probability, so a mis-typed dynamic call raises rather than mispricing.
   The declared monotonicities (EV non-decreasing in `p`, non-increasing in `c`) are property
   tests; `p_close` exclusion is enforced by type and guard.

4. **One runner per market, two mechanisms** (`one_runner.py`, SPEC-054).
   `select_market_position` chooses exactly one candidate by highest conservative net EV, ties
   broken by lowest `selection_id` — an explicit, deterministic, outcome-independent key — and
   records every rejected candidate. `MarketPositionLedger` refuses committing a second position
   to a market that already holds one (including a repeat of the identical selection). The guard
   dominates: a second position is refused regardless of its EV or fields.

5. **`taker-v1` is a fully-pinned order** (`execution.py`, SPEC-052).
   `TakerV1Order` fixes `timeInForce=FILL_OR_KILL`, `persistenceType=LAPSE`,
   `minFillSize == full stake` (no remainder can rest), back-only, and carries a `market_version`
   on every order. Non-`LAPSE` persistence, non-`FILL_OR_KILL` TIF, a `minFillSize` ≠ stake, and
   `LAY` are all refused, so **passive posting is unreachable** — there is no maker constructor.
   Stakes are **integer minor units**. The actual lapse-on-version-increment behaviour is the
   broker's (SPEC-072, L6, `planned`); L5's duty is that every order *carries* the guard.

## Consequences

- SPEC-050..054 are covered; the uncovered active set drops to SPEC-080/082 (l7_settle) and
  SPEC-100–103 (governance). `make verify` stays red by design until those land.
- **Mutation harness not stood up this slice.** ADR 0001 deferred `run_mutation.py`/`make
  mutants` to "the first money module to mutate." CI's `mutants-critical` job targets
  `l8_evidence/gates`, `l5b_risk`, `l7_settle` — all still `planned`/unbuilt — and does **not**
  target `l5_decision`. Building a cosmic-ray harness now would have nothing to mutate, so it
  remains a separate tooling slice landing with the gate/risk/settle modules. L5 gets its
  money-critical rigour from property tests + `pylint W0613` + the CI anti-stub grep + `mypy
  --strict`.
- `WinProbabilityLowerBound` is a **consumption contract**, not the edge distribution (SPEC-034,
  `planned`). It guarantees the decision layer never consumes a bare probability/point estimate;
  it does not itself prove a value is a true lower bound — that is L4's responsibility.
