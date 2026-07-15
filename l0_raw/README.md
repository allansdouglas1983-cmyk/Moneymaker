# l0_raw — L0 Raw truth layer

**Layer:** L0 · immutable, append-only · **Spec:** SPECIFICATION.md §6.1
**Requirements:** SPEC-001, SPEC-002, SPEC-003 (money), SPEC-004 · see `docs/spec-manifest.yaml`

Persist raw stream/order/command bytes *exactly as received* — the Betfair application
message bytes captured before parsing, never a normalised or derived artefact. Both wall
(UTC) and monotonic clocks on every record; API commands persisted *before* send.

> **Status: not yet implemented.** Scaffold marker. Implement per the session discipline
> in `CLAUDE.md`: one spec slice, failing tests committed separately, then implementation,
> then `make verify`.
