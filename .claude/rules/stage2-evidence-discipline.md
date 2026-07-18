---
paths:
  - "l4_pricing/**"
  - "l8_evidence/**"
  - "sport_tennis/**"
  - "docs/experiments/**"
  - "specs/evidence/**"
---

# Stage-2 evidence discipline (loaded when you touch modelling / evidence surfaces)

This rule protects the scientific validity of every Stage-2 probability result. It is
binding from Stage 2A (ADR 0018 closure; `docs/architecture/stage2a-lockbox-protocol.md`)
until superseded by a governed decision. It strengthens, and never relaxes,
`.claude/rules/evidence.md`, SPEC-020/021/023/092/094 and the pre-registration record.

## Before the lockbox authorises outcome access — FORBIDDEN as justification

No Stage-2 modelling decision (choosing, keeping, dropping, tuning, or promoting a model,
feature, or comparison) may be justified — in code, commits, ADRs, or reasoning — by any of:

- betting returns, ROI, profit, or hypothetical P&L;
- CLV of any flavour (it is a diagnostic, never a training target — evidence.md);
- hindsight examples or "this match shows…";
- inspection of individual matches or their winners;
- visual inspection of who won / eyeballing results;
- retrospective "this feature looks useful" after seeing outcomes.

These are not merely discouraged — invoking one to steer a modelling decision before
authorised outcome access is a **contamination event**: stop, record it, and treat any
artefact it touched as burned.

## Before opening — the ONLY permitted criteria

- pre-registered proper scoring on the correct unit (choice-set log score / multiclass
  Brier), calibration (in-the-large + slope, SPEC-097), coverage-with-exclusions;
- out-of-fold, time-respecting cross-fitting (SPEC-031) with the winner read only on the
  training/validation partition, never the lockbox;
- structural/consistency criteria that read no result at all (sum-to-1, monotonicity,
  refusal on separated data, determinism/replay, feature-hash reproducibility);
- the abandonment / promotion / refusal criteria frozen in the pre-registration record —
  as written, with multiplicity debited to the trial ledger (SPEC-091).

## Structural backstops (already enforced)

- Corpus fields are classified in `specs/evidence/outcome-field-classification-v1.yaml`;
  `l8_evidence.outcome_fields.assert_pre_lockbox_readable` makes reading an outcome field a
  hard error; a pre-lockbox reader carries a `PreLockboxAccessRecorder` whose digest proves
  what it read (fail closed on any unclassified field).
- Outcome extraction lives only in `l8_evidence.tennis_outcomes` (refuses until authorised);
  `l3_features` / `l4_pricing` are import-forbidden from it (`make verify`).
- The lockbox partition is readable only by GATE-1 (SPEC-092); looking burns it.

## The standing expectation

Most likely there is no exploitable edge, and the first families are expected to fail their
gates. A surprisingly good result read before the lockbox opens is a suspected contamination
first and a discovery only after the governed evaluation says so. An LLM never creates,
alters, smooths, or repairs a probability, and never decides a gate.
