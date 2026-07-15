# docs/decisions — Architecture Decision Records

**Spec:** SPECIFICATION.md §14

An ADR for every non-obvious choice. One file per decision: `NNNN-short-title.md`
(context · decision · consequences).

| ADR | Title |
|---|---|
| [0001](0001-verification-tooling.md) | Verification tooling: marker-based SPEC coverage; run_mutation deferred |
| [0002](0002-l0-raw-truth-layer.md) | L0 raw-truth layer: dual clock, append-only framing, persist-before-send |
| [0003](0003-l1-reducer.md) | L1 deterministic reducer & canonical replay |

Note: ADRs are ordinary docs. Only the specific paths in `CODEOWNERS` are human-owned —
`docs/SPECIFICATION.md`, `docs/spec-manifest.yaml`, and `docs/facts.yaml`, not all of `docs/`.
