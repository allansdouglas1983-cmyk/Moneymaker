# 0003 — L1 deterministic reducer & canonical replay

- **Status:** Accepted
- **Date:** 2026-07-15
- **Scope:** `l1_reduce/` (SPEC-010, SPEC-011, SPEC-012 — all `evidence`).
- **Spec:** SPECIFICATION.md §6.2; spec-manifest SPEC-010/011/012.

## Context

L1 turns L0 raw bytes into derived state via a versioned pure function
`reduce(raw_events, reducer_version)`. §6.2 rejects unqualified "bit-exact" (it depends on
serialisation, field ordering, Decimal representation, locale, …) and replaces it with a
**canonical output hash**: identical inputs + reducer + environment → identical canonical
hash. SPEC-010 (determinism), SPEC-011 (canonical replay), SPEC-012 (versioning) are the
enforced framework properties.

## Decisions

1. **Numbers are parsed as `Decimal`, never `float`** (§6.9). Payloads are decoded with
   `json.loads(..., parse_float=Decimal)` and every price/size/factor is coerced to `Decimal`.
   A float would make the canonical hash environment-dependent.

2. **Canonical serialisation** (`canonical.py`). Derived state is rendered to a deterministic
   structure — markets sorted by `market_id`, runners by `selection_id`, ladders by
   level/price, `Decimal` via `format(d, "f")`, ints as ints — then `json.dumps` with
   `sort_keys=True, separators=(",",":"), ensure_ascii=False`. `canonical_hash = sha256` of
   those bytes. The hash is of the **derived state only**; reducer version and input digests
   are separate metadata on the `ReductionResult`.

3. **Reducer registry keyed by immutable version string** (`reducer.py`, SPEC-012). `reduce`
   dispatches on `reducer_version`; an unknown version is refused (raises). Registered
   reducers are never removed, so old versions remain runnable for replay of historical
   conclusions. Each result records `reducer_version` and a `reducer_digest` (a declared
   logic-identity string bumped with the version).

4. **"Changing reducer logic requires a version bump" is enforced by the replay regression**
   (SPEC-011/012). A committed golden fixture pins `(reducer-mcm-v1, raw events) → canonical
   hash`. Any change to the reduction logic changes the hash and fails the regression, forcing
   either a version bump (new registry entry) or an explicit, reviewed golden update. This is
   the mechanical enforcement of SPEC-012's discipline.

5. **`reducer-mcm-v1` declared scope.** It reduces the Betfair Market Change Message (MCM)
   stream into a book state covering: `marketDefinition` (status, inPlay, version, betDelay,
   numberOfActiveRunners, and per-runner status/adjustmentFactor/sortPriority/removalDate) and
   per-runner book (`batb`, `batl`, `atb`, `atl`, `ltp`, `tv`). Image (`img`) replaces a
   market's state; deltas mutate it; a `0` size removes a level/price. MCM fields outside this
   set (e.g. starting-price fields, the traded ladder) are **out of the v1 declared scope**;
   adding them is a new reducer version, not an in-place edit — this is scoping *via
   versioning* (SPEC-012), not a stub.

## Consequences

- SPEC-010 gets a Hypothesis determinism property test over generated MCM sequences (as its
  requirement text demands); SPEC-011 gets a replay regression test (`tests/replay_regression/`)
  proving `replay_from_log == reduce(events)` and pinning the golden canonical hash; SPEC-012
  gets registry/version-recording tests.
- The reducer is pure — no wall clock, no randomness, no I/O — so determinism holds by
  construction, and `replay.py` can reconstruct L2 from the L0 append-only log.
- `make verify` remains red until the remaining active IDs (L3, L5, L7, governance) land.

## Amendment (advisory review, 2026-07-15)

An advisory verifier (SPECIFICATION.md §16.4) independently recomputed the golden hash
(matches) and confirmed `reduce` is pure/deterministic, nothing is stubbed, and no test was
weakened. Findings addressed:

- **Canonical hash is representation-canonical, not value-canonical (documented).** The hash
  is deterministic over the exact reduced numeric *representation* (`format(d, "f")` preserves
  scale, so `3.5` and `3.50` differ). This does **not** affect SPEC-010/011: L0 stores the raw
  bytes exactly, so the same capture always reduces to the same representation and replay is
  byte-identical. The property is intentional — L2 preserves the reduced wire representation
  rather than normalising it. There is exactly one encode path (`reduce → canonical`), so no
  second re-encoding can diverge. (Normalising values is a possible future, human-approved
  refinement, not required for the SPEC.)
- **Golden fixture surface widened (F2).** A second golden fixture
  (`test_full_scope_golden_canonical_hash_is_stable`) exercises every declared-scope field —
  `batb`, `batl`, `atb`, `atl`, `ltp`, `tv`, `adjustmentFactor`, `removalDate`, `sortPriority`,
  `numberOfActiveRunners`, `betDelay` — plus a level removal and a price removal, so a
  regression anywhere in the reducer's in-scope surface fails the version-bump guard.
- **Determinism property strengthened (F3).** An added property test generates multiple
  markets, every ladder, `tv`, and `marketDefinition`.
- **marketDefinition full-replace commented (F4).** The runner set is a complete snapshot,
  never a delta; the code now says so.

