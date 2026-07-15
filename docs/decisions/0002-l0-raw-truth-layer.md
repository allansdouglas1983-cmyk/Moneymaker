# 0002 — L0 raw-truth layer design

- **Status:** Accepted
- **Date:** 2026-07-15
- **Scope:** `l0_raw/` (SPEC-001, SPEC-002, SPEC-003, SPEC-004). SPEC-003 is `money`.
- **Spec:** SPECIFICATION.md §6.1, §6.2, §6.9; spec-manifest SPEC-001…004.

## Context

L0 is the raw-truth layer: it persists raw bytes exactly as received, append-only, with the
timestamps and provenance needed for everything above L1 to be reproducible. Several
implementation choices are not fully pinned by the spec and are recorded here.

## Decisions

1. **Record models are frozen Pydantic v2 models** (`records.py`). Pydantic at the persisted
   contract boundary (§6.9); frozen because L0 is immutable/append-only. Types follow §6.9:
   `payload_bytes: bytes`, timestamps carry both a UTC wall clock and a monotonic clock,
   versions/hashes are immutable strings.

2. **Dual clock as a first-class value** (`clock.py`). `ClockStamp` carries `wall_utc`,
   `monotonic_ns`, **and** a `domain_fingerprint`. `latency_ns()` uses **monotonic only**
   (SPEC-004) and **raises** when the two stamps come from different clock domains —
   monotonic clocks are not comparable across process/boot domains or hosts (§6.2). A
   `ClockDomain` records `host_id`, `boot_id`, `process_id`, `process_start_utc`,
   `monotonic_origin_ns`; the raw capture's `CaptureMeta` carries those plus
   `capture_sequence`, `raw_partition_id`, `raw_partition_hash` (§6.2).

3. **Append-only log format** (`store.py`). A magic-prefixed file of length-framed records:
   `>II` (metadata length, payload length) + metadata JSON + **payload bytes verbatim**. The
   payload is stored byte-for-byte with no transform or normalisation (SPEC-001); metadata is
   deterministic JSON (`sort_keys`). The class exposes only `append()` and `read()` — there is
   **no update or delete API**, so append-only is a property of the type, not a convention.
   `append()` `fsync`s for durability. `read()` verifies the magic header.

4. **Capture preserves duplicates and order** (`capture.py`). `RawStreamCapture` appends
   whatever it is handed, in call order, assigning a monotonically increasing
   `capture_sequence`. It never deduplicates or reorders, so duplicate and out-of-order
   messages are retained unmodified (SPEC-002). `checksum = sha256(payload)` and is **verified
   on read** — a payload that no longer matches its checksum raises (integrity).

5. **`raw_partition_hash = sha256(raw_partition_id)`** — a deterministic identity hash of the
   partition. A running per-partition hash-chain (tamper-evidence) is a possible future
   hardening; the identity hash is sufficient for the frozen-universe/reproducibility needs of
   Phase 1 and is deterministic for canonical replay.

6. **API command persistence is TWO events** (`commands.py`, SPEC-003). §6.2 says "API
   commands carry both clocks on **both events**" — a **send event** and a **response event**.
   This also reconciles the §6.1 single-record listing (which mixes pre-send fields with the
   post-send `response_*`) with append-only immutability: the send event is written first and
   never mutated; the response event is a second append linked by `command_id`. The send event
   carries `payload_hash` (not the payload — §6.1 lists only the hash) and `send_time`; the
   response event carries `response_time` and `response_payload`.

7. **Persist-before-send is enforced by construction** (`CommandGateway.send`, SPEC-003).
   The gateway (a) builds the send event and calls `journal.record_send()`, then — **only
   after that returns** — (b) calls `transport.send()`, then (c) records the response. If
   `record_send()` raises (journal/disk failure), the exception propagates and the transport
   is **never invoked**: the command fails closed. A send that is durably logged with no
   response event is the correct, reconcilable state after a crash between (a) and (c); it is
   never a silently-sent-but-unlogged command.

## Consequences

- SPEC-001/002/004 (evidence) and SPEC-003 (money) become covered. SPEC-003's property tests
  live under `tests/properties/`; its persist-before-send and fail-closed behaviour are
  verified by a property test and a failure-injection test.
- `make verify` remains red overall until the other active IDs (L1, L3, L5, L7, governance)
  are implemented — this slice covers L0 only.
- L0 is deliberately read-back capable (`AppendOnlyLog.read`, `records.decode`) so the L1
  reducer (SPEC-010/011, a later slice) can replay from raw bytes.
