# l8_evidence — L8 Evidence (trial ledger, gate evaluator, diagnostics)

**Layer:** L8 · **Spec:** SPECIFICATION.md §9, §10 · **Criticality:** evidence (gates/ is money)
**Requirements:** SPEC-090…SPEC-097 · see `docs/spec-manifest.yaml` · **SPEC-093 `active`; the rest Phase 2/5 (`planned`)**
**Path-scoped rule:** `.claude/rules/evidence.md`.

Race-level paired inference (block bootstrap by meeting-day; runner-level independence
forbidden). Immutable trial ledger with multiplicity accounting. Lockbox inspected once,
at Gate 1 only. CLV is a diagnostic family, never a training target. Anytime-valid
monitoring only. The deterministic gate evaluator lives in `gates/` (see its README).

## Present
- `gates/` — the **deterministic gate evaluator** (SPEC-093, **money**, `active`, ADR 0011).
  Four-valued verdicts bound to data/model hashes, evaluated from the frozen
  `specs/gates/v1.yaml` structure + each experiment's §9.7 pre-registration + `docs/facts.yaml`.
  See `gates/README.md` for the pinned CLI contract.
- `reconciled_bsp.py` — the **grading-only** reconciled-BSP taint marker, built as part of the
  L3 BSP-leakage guard (SPEC-021). It is deliberately never imported by `l3_features` (enforced
  by `tools/check_import_quarantine.py --forbid l8_evidence.reconciled_bsp --from l3_features`).

> **Status:** the rest of the L8 layer (trial ledger, race-level paired inference,
> calibration/CLV diagnostics — SPEC-090–092, 094–097) is **Phase 2/5 `planned`**, not yet
> implemented.
