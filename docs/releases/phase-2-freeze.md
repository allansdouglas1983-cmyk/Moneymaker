# Phase-2 release freeze and attestation

**Frozen commit:** `419d84bbe71b17b78a7be458b87f0a817ef1488b`
(local annotated tag `phase-2-freeze-419d84b`; the remote's push policy rejects tags
(HTTP 403, branch-only), so this committed document is the authoritative attestation
record — it pins the commit hash directly.)

**Date:** 2026-07-16 · **Attested by:** founder direction ("Phase-2 completion is
accepted"), recorded by the agent session that produced the release.

## What is frozen

Every Phase-2 SPEC-ID is `enforcement_state: active` at the frozen commit. Later phases
remain `planned` and are NOT authorised: no Phase 3, Phase 5 or Gate P1 activation, no
live credentials, no paid purchase, no real-money order, no passive-execution work.

## Attestation digests (computed at the frozen commit)

| Artifact | Digest |
|---|---|
| `docs/spec-manifest.yaml` (active manifest) | `sha256:0a8445cba1d66d1f787ad1c0371618e68b2fd78ea69bffc61c88719f295b9858` |
| `uv.lock` (full dependency set) | `sha256:460babf89cb6efb9111404830832c2cb928e9e711682c031665fe552f70fffe6` |
| `l1_reduce.reducer.environment_digest()` (runtime/container digest) | `sha256:a0d06b291f7cfea0678d5ce09eb7d44534334638816aa6ac1bb5e102e80c6ec3` |

Manifest state at freeze: **42 active** enforcement entries, **23 planned** (Phases 3/5,
Gate P1, SPEC-047/048, and other human-gated items).

## Verification results at the frozen commit

- `make verify`: **exit 0** — 1,135 tests passed (unit, integration, properties,
  stateful, failure-injection); ruff (incl. ARG) clean; pylint W0613 on money modules
  10.00/10; escape-hatch greps clean; scraping and BSP import quarantines clean;
  `mypy --strict` clean over 210 source files; spec-coverage checks (active+verified,
  causal declarations, property coverage for money IDs) all green.
- `make replay` (canonical replay regression): **exit 0** — 6 passed; bit-exact replay
  holds under the environment digest above.
- `make mutants` scope at freeze: `l8_evidence/gates` + `l7_settle` enforced with
  `--require-kill-non-equivalent`; every prior survivor classified and human-approved in
  `specs/mutation-survivors.yaml` (approved 2026-07-16, retrospective-audit session).
  Neither target directory changed between that enforcement run and the frozen commit.

## Post-freeze governed corrections

Two founder-directed clarification corrections land immediately AFTER the freeze, each
in its own commit citing the SPEC-ID and the founder's 2026-07-16 direction (they change
naming/metadata only, before any real evidence exists):

1. SPEC-095: `ExecutionPolicyValue` renamed `ExecutionCaptureDelta` (it is
   realised-minus-intended on matched orders — execution capture, not full outcome-based
   policy value). The name `ExecutionPolicyValue` is RESERVED for a future full
   outcome-based policy evaluation across fills, unfilled orders, no-actions and
   fallbacks. Historical meaning is fixed now, before real evidence begins.
2. SPEC-097: Wilson reliability intervals carry an explicit `interval_kind =
   DESCRIPTIVE_WILSON` marker — descriptive only; never Gate 1/Gate 5 evidence or an
   external confidence claim; inferential calibration uncertainty must come from
   race/meeting-day block resampling (SPEC-090 machinery).

A separate governed test-correction PROPOSAL (not an implementation) covers source
rights review metadata: `docs/proposals/test-correction-0001-source-rights-review.md`.
`fair_odds_basis` is DEFERRED until Gate P1 (the internal contract's fair-odds priority
order is documented and unambiguous in `l8_evidence/prediction_snapshots.py`).
