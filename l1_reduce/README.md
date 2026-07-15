# l1_reduce — L1 Deterministic reducers & canonical replay

**Layer:** L1 · **Spec:** SPECIFICATION.md §6.2
**Requirements:** SPEC-010, SPEC-011, SPEC-012 · see `docs/spec-manifest.yaml`

`reduce(raw_events, reducer_version)` is a pure function. Same approved environment
(raw+reducer+config+container digests) → same **canonical output hash**. Reducer version
is immutable and recorded with every derived artefact; old versions stay runnable.

> **Status: not yet implemented.** Scaffold marker. Tests first, committed separately.
