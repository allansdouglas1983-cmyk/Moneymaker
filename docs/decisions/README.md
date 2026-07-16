# docs/decisions — Architecture Decision Records

**Spec:** SPECIFICATION.md §14

An ADR for every non-obvious choice. One file per decision: `NNNN-short-title.md`
(context · decision · consequences).

| ADR | Title |
|---|---|
| [0001](0001-verification-tooling.md) | Verification tooling: marker-based SPEC coverage; run_mutation deferred |
| [0002](0002-l0-raw-truth-layer.md) | L0 raw-truth layer: dual clock, append-only framing, persist-before-send |
| [0003](0003-l1-reducer.md) | L1 deterministic reducer & canonical replay |
| [0004](0004-l3-knowledge-time.md) | L3 knowledge-time stamps; two-mechanism BSP-leakage guard; live actual-off exclusion; no-float feature hash |
| [0005](0005-l5-decision.md) | L5 tick ladder; three distinct price types; exact-Decimal EV; one-runner selection; taker-v1 |
| [0006](0006-governance.md) | governance/ package + money-lint; licensed-source registry; no-delayed-key by construction; budget separation |
| [0007](0007-l7-settlement.md) | L7 commission on net market result; reduction factors & dead heats; idempotent versioned ledger |
| [0008](0008-mutation-harness.md) | cosmic-ray mutation harness; survivor classification file; report vs enforce |
| [0009](0009-price-preregistration.md) | Frozen price pre-registration: p_market_info / odds_exec / p_close (info/exec/close v1) |
| [0010](0010-retrospective-audit.md) | 2026-07-16 retrospective audit: verdict, remediation design, equivalent-mutant policy |
| [0011](0011-gate-evaluator.md) | Deterministic gate evaluator (SPEC-093) + frozen specs/gates/v1.yaml — accepted & implemented; severity-aggregated verdicts |
| [0012](0012-l4-pricing.md) | L4 pricing: pure-Python deterministic two-stage model, cross-fit provenance, edge-distribution type boundary (SPEC-030–035) |

Note: ADRs are ordinary docs. Only the specific paths in `CODEOWNERS` are human-owned —
`docs/SPECIFICATION.md`, `docs/spec-manifest.yaml`, and `docs/facts.yaml`, not all of `docs/`.
