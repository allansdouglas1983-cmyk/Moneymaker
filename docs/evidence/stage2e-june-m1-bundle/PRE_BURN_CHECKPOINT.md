# Stage 2E — PRE-BURN CHECKPOINT (June still SEALED)

The complete pre-burn checkpoint. **The June lockbox is UNSPENT and no June outcome field has
been read.** The burn runs only on the founder's exact `BURN JUNE STAGE A`.

## 1. Governed test-correction — disposition + semantic change
Commit `b2afc22` (correction) then `f0edec5` (implementation), Rule-2 separate. The prior test
asserted the outcome-access vocabulary *could not express June*. Corrected to: the vocabulary is
EXACTLY `{PRE_JUNE_DEVELOPMENT, JUNE_M1_TRANSFER}`; `JUNE_M1_TRANSFER` works ONLY with the exact
v2 seal digest and an explicit authorised market set; every other scope and every non-authorised
June market still refuses (membership AND data); anomalous settlements still refuse. No generic
JUNE/RESEARCH/MODEL/M2/ROI scope. `tests/unit/l8/test_tennis_outcomes_governed.py`.

## 2. Final v2 seal authorisation digest
`specs/evidence/lockbox-june-2026-tennis-v2.yaml` →
`sha256:f552c7bfafd8432693a26d01519ffac29e1d81d7554901041553952b2ddb88c8` (pinned in
`l8_evidence.tennis_outcomes.JUNE_M1_SEAL_AUTHORISATION_DIGEST`).

## 3. Conditional Stage-A/Stage-B use-policy digest
`specs/evidence/june-outcome-artifact-use-policy-v1.yaml` →
`sha256:84efd4a22cc4c778ff31867afc9a52a67718a22226aaefec97f942e279661338` (pinned in
`l8_evidence.june_stage_a_extraction.JUNE_ARTIFACT_USE_POLICY_DIGEST`). Permitted: M1; conditional
Stage-B SPEC-032 dev ONLY on M1 PASS, reusing the immutable artifact, never reopening raw.

## 4. Reconciliation 1,213 vs 1,218
`RECONCILIATION_1213_vs_1218.md`. The 5-market gap is cross-tour homonym mis-resolution
(Black B./Britton D./Johnson S.), correctly refused `REFUSED_TOUR_PROVENANCE:MIXED_TOUR`. No
outcome used, no manual removal, not a defect. **The 5 stay refused.**

## 5. Final prospective M1 manifest + digest
`docs/evidence/stage2d-june-m1-transfer/` →
`sha256:d192b4e3a3980fd3e2108a3efd68feb03d15e041a436569353178395f8b17b23`.

## 6. ATP/WTA + cohort counts
M1-valid **1,213**: ATP **592**, WTA **621** (both ≥ 500 → supported); strict 1,150 / primary-only
63. Prior-history (ATP/WTA): 1-4 223/197, 5-9 74/64, 10-19 59/74, 20+ 236/286.

## 7. UTC-day cluster counts
Overall **30** calendar-day clusters (min 5 / median 36 / max 125); ATP 30 days, WTA 29.

## 8. Expected outcome-join funnel (outcome-blind)
1,213 candidates; **all 1,213 have a present, verified pre-off stream** (0 missing under the
ADVANCED extract root — note one June-scheduled market, `1.259492505`, is filed under a `Jul/1/`
processing folder; its selection ids were verified against its real pre-off book). At burn each
market yields one MinimalOutcome via the governed extractor; a market refuses ONLY if its
settlement is anomalous (0/≥2 winners → `OutcomeUndeterminedError`) or the winner selection is
neither designated nor other (`HarnessJoinError`) — both stay visible exclusions. The scored/refused
split is knowable only at the burn (pre-scanning settlement would itself read the lockbox).

## 9. Synthetic end-to-end harness results
`tests/unit/l8/test_june_m1_harness.py` (join: winner→competitor by id, order-invariant;
unknown/mismatch refuse; deterministic scorecard; 500-support flags; verdict evaluator incl.
insufficient-evidence-never-PASS) and `test_june_stage_a_dryrun.py` (artifact regenerates the
scorecard byte-identically; raw never reopened) and `test_june_stage_a_driver.py` (the REAL 1,213
bundle scores deterministically under synthetic winners; both tours supported). All pass.

## 10. Atomic extraction + restart-safety
`l8_evidence.june_stage_a_extraction` (`test_june_stage_a_extraction.py`). **Requirement A**: the
burn record is fsync'd BEFORE the single raw read, so no crash window has an outcome read while the
durable state is unopened. Recovery: complete artifact → finalize (no raw re-read); burn record but
no finalizable artifact → typed `StageAIncidentError` (stop, preserve; a second raw access is
forbidden; a new period is required). **Residual risk (reported):** a crash during the single
in-memory→temp fsync leaves the seal burned with no artifact → unrecoverable-without-a-new-period;
the window is one fsync of an already-complete in-memory artifact. **Requirement B**: the immutable
artifact is read once; Stage B needs the exact use-policy digest + a genuine tokened
`M1PassAttestation` bound to the artifact digest; CONTINUE/FAIL/technical-failure/mismatch/forgery →
structurally unreachable; no raw reference on the Stage-B path.

## 11. Exact one-time burn command
Runs ONLY on `BURN JUNE STAGE A`:
```python
from datetime import date, datetime, timezone
from pathlib import Path
from l8_evidence.lockbox import LockboxRegistry, LockboxDefinition
from l8_evidence.prediction_snapshots import DualClockTimestamp
from l8_evidence.tennis_outcomes import load_sealed_market_ids
from l8_evidence.june_stage_a_driver import run_stage_a_burn

reg = LockboxRegistry()
reg.define(LockboxDefinition(lockbox_id="lockbox-june-2026-tennis-v1",
    period_start=date(2026,6,1), period_end=date(2026,6,30),
    defined_at=DualClockTimestamp(wall_utc=datetime.now(timezone.utc), monotonic_ns=0),
    defined_by="founder"))
result = run_stage_a_burn(
    registry=reg, lockbox_id="lockbox-june-2026-tennis-v1",
    at=DualClockTimestamp(wall_utc=datetime.now(timezone.utc), monotonic_ns=0),
    sealed_market_ids=load_sealed_market_ids(),
    model_manifest_sha256=<F2+calib manifest>, feature_manifest_sha256=<bundle manifest>,
    data_manifest_sha256=<vintage manifest>, granted_on=date.today(),
    streams_root=Path(".../pilot-data/extracted/ADVANCED"),   # full ADVANCED extract
    burn_record_path=Path("docs/evidence/stage2e-june-m1-artifact/BURN_RECORD.json"),
    artifact_path=Path("docs/evidence/stage2e-june-m1-artifact/OUTCOME_ARTIFACT.json"))
# -> {"verdict": {...}, "scorecard": {...}, "n_scored", "exclusions", digests}
```

## 12. Commit SHA + verification
HEAD `9737302` on `claude/project-files-followup-dif8al`. Verify green: 1,918
unit/integration/property/stateful/failure-injection/replay tests; ruff (full + ARG) + mypy
--strict clean on all new modules; spec coverage 44 enforced IDs; import quarantine holds (l3/l4
do not import the outcome/harness modules). **Mutation:** the new seal/extraction/gating logic is
pinned by behaviour tests (crash-window ordering, refusal paths, forgery); a full cosmic-ray pass
over `tennis_outcomes.py` + `june_stage_a_extraction.py` is recommended to run in background before
the burn — flagged, not yet executed.

## 13. Real June lockbox remains unspent
`is_uncontaminated(lockbox-june-2026-tennis-v1)` is True; no `LockboxRegistry` GATE-1 access on real
data; no `BURN_RECORD.json` / `OUTCOME_ARTIFACT.json` exists.

## 14. No June outcome field read
The bundle was built only from pre-off `OPEN` marketDefinitions (id+name) + pre-June ratings; the
governed June extraction path was exercised only with synthetic streams in tests; verification reads
touched only pre-off runner id+name. No winner/status/settled/result field was read.

## 15. No M2/ROI/P&L/CLV/EV/selection code reachable from the Stage-A path
`run_stage_a_burn` imports only the bundle loader, the governed extractor, the atomic extraction,
the join, and the deterministic M1 verdict. No execution/staking/settlement/combination module is on
the path; Stage B (SPEC-032) is gated behind the M1-PASS attestation and is not invoked here.
