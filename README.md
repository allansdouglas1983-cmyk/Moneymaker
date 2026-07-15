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

## Status — repository bootstrap
Specification, governance, and directory scaffolding are in place. **There is no
implementation yet.** In particular, the `tools/` CI-enforcement scripts and the test suites
are not written, so `.github/workflows/verify.yml` will report **red** until they exist —
that is expected and honest, not a green build that checks nothing. (The workflow only runs
on pull requests and pushes to `main`, so simply pushing a feature branch does not trigger it.)

Build per the session discipline in `CLAUDE.md`: **one spec slice per session, failing tests
first (committed separately), then implementation, then `make verify`.** Status comes from
CI, never from a prose claim of completion.
