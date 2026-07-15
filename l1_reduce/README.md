# l1_reduce — L1 Deterministic reducers & canonical replay

**Layer:** L1 · **Spec:** SPECIFICATION.md §6.2 · **Requirements:** SPEC-010/011/012 · **implemented**
**Design:** `docs/decisions/0003-l1-reducer.md`

`reduce(raw_events, reducer_version)` is a pure function. Same inputs + reducer + environment
→ same **canonical output hash**. Reducer version is an immutable string recorded with every
result; old versions stay runnable (registry never drops entries).

## Modules
| Module | Responsibility | SPEC |
|---|---|---|
| `state.py`     | derived book state (markets → runners → ladders / definition) | — |
| `canonical.py` | deterministic serialisation + `canonical_hash` of derived state | SPEC-010/011 |
| `mcm_v1.py`    | `reducer-mcm-v1`: reduce Betfair MCM into book state (image/delta, batb/batl/atb/atl, ltp/tv, marketDefinition) | SPEC-010 |
| `reducer.py`   | registry keyed by immutable version; `reduce()` refuses unknown versions; `ReductionResult` | SPEC-012 |
| `replay.py`    | `replay_from_log` — reconstruct L2 from the L0 append-only log | SPEC-011 |

## Invariants under test
- `reduce` is pure/deterministic: same events → byte-identical canonical output (SPEC-010,
  Hypothesis property over generated MCM sequences). Numbers parsed as `Decimal`, never float.
- L2 is reconstructible from L0 + reducer version, byte-identical; a committed golden hash
  pins `reducer-mcm-v1`'s output so any logic change fails the replay regression (SPEC-011).
- Reducer version is immutable and recorded; unknown versions are refused; changing logic
  requires a version bump (enforced by the golden regression) (SPEC-012).

Tests: `tests/unit/l1/`, `tests/properties/l1/`, `tests/replay_regression/l1/`.
