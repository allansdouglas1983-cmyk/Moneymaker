# l0_raw — L0 Raw truth layer

**Layer:** L0 · immutable, append-only · **Spec:** SPECIFICATION.md §6.1, §6.2, §6.9
**Requirements:** SPEC-001, SPEC-002, SPEC-003 (money), SPEC-004 · **implemented**
**Design:** `docs/decisions/0002-l0-raw-truth-layer.md`

Persist raw stream/order/command bytes *exactly as received* — the Betfair application
message bytes captured before parsing, never a normalised or derived artefact. Both wall
(UTC) and monotonic clocks on every record; API commands persisted *before* send.

## Modules
| Module | Responsibility | SPEC |
|---|---|---|
| `clock.py`    | dual wall+monotonic `ClockStamp`; `latency_ns` uses monotonic only and refuses cross-domain comparison | SPEC-004 |
| `records.py`  | frozen Pydantic record contracts + verbatim append-log framing + checksum verification | SPEC-001/002/003 |
| `store.py`    | `AppendOnlyLog` — length-framed, payload stored byte-for-byte, no update/delete API | SPEC-001/002 |
| `capture.py`  | `RawStreamCapture` — market/order capture; preserves duplicates and order; dense `capture_sequence` | SPEC-001/002 |
| `commands.py` | `CommandGateway` — persists the send event **before** calling the transport; fails closed | SPEC-003 |

## Invariants under test
- Payload stored byte-for-byte; `checksum = sha256(payload)` verified on read (SPEC-001).
- Every message retained, duplicates and out-of-order included; never deduped or reordered (SPEC-002).
- A command's send event is durably persisted before the transport is invoked; if persistence
  fails, the command is **not** sent (SPEC-003, money — property + failure-injection tests).
- Latency is the monotonic delta, invariant to wall-clock (NTP) jumps; monotonic is not
  comparable across clock domains (SPEC-004).

Tests: `tests/unit/l0/`, `tests/properties/l0/`, `tests/failure_injection/l0/`.
