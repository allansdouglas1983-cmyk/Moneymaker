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
| [0013](0013-analytics-consumer.md) | Prediction/analytics consumer foundations: SPEC-ID remapping, read-only boundary, Gate P1 (planned) |

Note: ADRs are ordinary docs. Only the specific paths in `CODEOWNERS` are human-owned —
`docs/SPECIFICATION.md`, `docs/spec-manifest.yaml`, and `docs/facts.yaml`, not all of `docs/`.
| [0014](0014-phase-3a-offline-broker.md) | Phase 3A offline broker construction: founder-authorised scope ceiling (SPEC-070/071/062/063/064/083/102 offline halves; simulated adapters only) |
| [0015](0015-betfair-account-exclusion-block.md) | BLOCKING: founder Betfair account exclusion/closure — purchase paused; no-bypass invariant (permanent); consequence map incl. analytics-only terminal state |
| [0016](0016-tennis-pivot-proposal.md) | (superseded by 0017) Tennis pivot proposal: impact assessment, migration plan |
| [0017](0017-sport-agnostic-transition.md) | Tennis-first sport-agnostic transition program (founder 12-phase directive); supersedes ADR 0016 scope; racing preserved as sport adapter |
| [0018](0018-june-tennis-market-feasibility-review.md) | Stage-1 closure: June-2026 tennis market-feasibility review; Gate M0 PASS; programme baseline frozen (`specs/programme/baseline-v1.yaml`); Stage-2 probability programme defined; critical failure-mode review |
| [0019](0019-personal-predictor-tip-assistant-v1.md) | Stage 2G: personal tennis predictor & tip assistant V1 (SPEC-105..115; DP1 Glicko-2; BET_CANDIDATE structurally disabled; £0 budget freeze) |
| [0020](0020-account-restored-bounded-manual-trial.md) | Account status updated: the 2018 six-month exclusion expired and was lifted through Betfair's own process; supersedes ADR 0015's blocking state. No-bypass invariant remains permanent. Bounded founder-manual real-stake trial protocol (flat stakes, hard pre-set loss budget, statement is truth, nothing in the repo places an order) |
