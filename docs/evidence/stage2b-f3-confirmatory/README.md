# Stage-2B F3-vs-F2 confirmatory trial + M1 scorecard — FROZEN 2026-07-18

Nested chronological confirmatory comparison (registered design A) + M1 adequacy
evaluation of the selected model. Deterministic (seed 20260718, block bootstrap
20,000 resamples, l8_evidence.paired_inference). No June, no odds, no returns/CLV.

## F3-vs-F2 confirmatory (F3_CONFIRMATORY_REPORT.json, digest 216aa508...)
- Paired predictions: 34,038 (ATP 17,686 / WTA 16,352) — the registered count exactly;
  0 runtime refusals (Hard/Clay/Grass only in-window, all KNOWN surfaces).
- UTC-day clusters: 2,175 (min 1 / median 14 / p90 32 / max 87).
- Raw aggregate log score: F2 0.62393, F3 0.63345.
- Paired mean improvement d = ll_F2 - ll_F3 = -0.00952 (F3 WORSE).
- Cluster-aware 97.5% lower bound: -0.01199; upper -0.00708 -> CI entirely below zero.
- ATP mean_d -0.00657 (CI [-0.01001,-0.00317]); WTA -0.01271 ([-0.01618,-0.00921]).
- VERDICT: FAIL_HARM (material degradation; futility also satisfied). ATP/WTA secondary,
  never reinterpreted as primary. F3 not promoted; F2 retained as selected family.

## M1 scorecard (calibrated F2) — M1_SCORECARD.json / M1_VERDICT.json
Selected model F2 global Elo, per-fold one-parameter temperature scaling (T ~ 1.18-1.32,
fitted strictly on data < Y). Overall: log_loss 0.62211 (<ln2), Brier 0.21697 (<0.25),
slope 1.0048 (raw was ~0.83 -> temperature-corrected), coverage 100%. Temporal transfer:
validation 0.62087 vs OOF 0.62232 (val BETTER; +-0.01 band met). Reliability: max decile
gap 0.017 (<=0.05). Cold-start cohorts retained; worst 10-19 band 0.6441 (<ln2+0.02).
ATP/WTA both within looser bands.
- ONE band CONTINUE: overall calibration-in-the-large +0.02328 logit vs +-0.02 (over by
  0.0033). One-parameter temperature has no intercept and the frozen policy forbids a
  method contest, so the small mean offset persists. No band weakened, no re-tuning.
- M1 VERDICT: CONTINUE (adequacy AND-gate; 14/15 items PASS; the CONTINUE item is a
  CONTINUE-flavoured item, not FAIL). M1/Gate 1 NOT closed.
