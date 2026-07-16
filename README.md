# Betfair Racing Research Platform

A **research and measurement platform** — *not* a betting bot. It may become one only if the
evidence supports it, and only through the gates. The most likely outcome is that **no
exploitable edge exists**; the platform's job is to establish that cheaply and honestly.
Treat every surprisingly good backtest as a suspected bug.

> **Approval posture (v1.1):** conditionally approved for **offline implementation through
> Phase 2 only**. NO live Betfair credentials, NO API order submission, NO real money, NO
> passive-execution claims, NO dynamic model updates, NO Kelly sizing, NO production
> deployment. Those remain HALTED until their gates are satisfied and separately approved.
> Full checklist: `docs/HALT-CHECKLIST.md`.

## Start here
- **`CLAUDE.md`** — the lean root map and the three rules
- **`docs/SPECIFICATION.md`** — the master specification (authoritative narrative)
- **`docs/spec-manifest.yaml`** — the authoritative, phase-aware requirement list (SPEC-IDs)
- **`docs/facts.yaml`** — volatile facts registry (values re-verified before gates)
- **`docs/CI-AND-TRUST.md`** — the trust boundary and CI
- **`docs/HALT-CHECKLIST.md`** — gate-by-gate halt checklist
- **`.claude/rules/`** — path-scoped money-critical & evidence rules (load on demand)

## Layout
Layered `l0_raw` → `l8_evidence` (see each directory's `README.md` and SPECIFICATION.md §14).
**Money-critical modules** — `l4b_fill`, `l5_decision`, `l5b_risk`, `l6_broker`, `l7_settle`,
`l8_evidence/gates` — are never stubbed and require property-based + mutation tests.

## Status — Phase 1 in progress

**Live progress and session handover: [`docs/PROGRESS.md`](docs/PROGRESS.md).**

**The entire active Phase-1 surface is implemented — all 23 active SPEC-IDs, `make verify` green**
(349 tests; `mypy --strict` over 120 files, `ruff`/`pylint W0613` clean). A founder-requested
retrospective audit (2026-07-16, ADR 0010) confirmed no silent trims or weakened tests and
hardened the verification net; `l7_settle` mutation testing is **enforced** (329 mutants,
321 killed, 8 founder-approved equivalent survivors):
- **Verification harness** (`tools/`) — the CI enforcement backbone incl. the mutation harness
  (ADR 0001, 0008).
- **L0 raw truth layer** (`l0_raw/`, SPEC-001–004) — append-only capture, dual clock,
  persist-before-send (ADR 0002).
- **L1 deterministic reducer** (`l1_reduce/`, SPEC-010–012) — pure reduction, canonical
  replay, reducer versioning (ADR 0003).
- **L3 knowledge-time & leakage** (`l3_features/`, SPEC-020–024) — knowledge-time semantics,
  two-mechanism BSP-leakage guard, feature-hash reproducibility (ADR 0004).
- **L5 decision layer** (`l5_decision/`, SPEC-050–054, money) — tick ladder, three price types,
  EV at odds_exec, one-runner, taker-v1 (ADR 0005).
- **Governance** (`governance/`, SPEC-100–103) — scraping quarantine, licensed-source gate,
  no-delayed-key real money, budget separation (ADR 0006).
- **L7 market-level settlement** (`l7_settle/`, SPEC-080/082, money) — commission on the net
  market result, reduction factors, dead heats, idempotent versioned ledger (ADR 0007).
- **L8 gate evaluator** (`l8_evidence/gates/`, SPEC-093, money) — the deterministic four-valued
  promotion-gate verdict bound to data/model hashes; `specs/gates/v1.yaml` frozen structure-only;
  an LLM never decides a gate (ADR 0011).

Work continues autonomously in **Phase 2 (offline, pre-approved)** — the price/gate
pre-registration specs are frozen (ADRs 0009/0011); next are L4 pricing and the remaining L8
evidence components with synthetic-fixture tests, activating
each ID once it is implemented and covered. Phase 3+ (risk, broker, live execution) stay HALTED by the
approval posture until their gates are met. See `docs/PROGRESS.md`.

Build per the session discipline in `CLAUDE.md`: **one spec slice per session, failing tests
first (committed separately), then implementation, then `make verify`.** Status comes from
CI, never from a prose claim of completion. To resume, follow the checklist in
`docs/PROGRESS.md`.
