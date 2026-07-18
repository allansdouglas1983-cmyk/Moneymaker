# Stage 2C — AFFINE_LOGIT_CALIBRATION_V2 pre-June remediation scorecard

**Evidence class: REMEDIATION / DEVELOPMENT.** This scorecard was generated *after* the
temperature-only calibration-in-the-large shortfall (+0.02328) was observed, so — by
Stage 2C §4 — it **does not close M1** and is **not** fresh external confirmation. June
2026 remains the untouched external transfer check. No June data, no odds, no returns, no
CLV entered this computation.

## What this is

The selected model is **F2 global Elo** (`EXP-STAGE2-F2-GLOBAL-ELO-001`); F3 closed
FAIL_HARM (`specs/programme/f3-closure-record-v1.yaml`). The registered remediation
(`specs/programme/calibration-policy-v2.yaml`) replaces the finalization step with an
affine map in logit space:

```
z_cal = intercept + z / temperature      (z = logit(p_raw), temperature > 0)
p_cal = sigmoid(z_cal)
```

`temperature` alone (calibration-policy-v1) fixed the slope but has no intercept, so it
could not move the mean; the added intercept corrects the +0.02328 residual and nothing
else. ATP and WTA are calibrated with separate parameters because the frozen F2 policy
already runs the two tours as fully independent models.

## Fold-safety (`scripts/affine_remediation.py`)

Per outer fold Y, per tour: (1) inner OOF F2 predictions from outer-training only
(data < Y); (2) fit `(intercept, temperature)` by MLE on those inner OOF preds+outcomes;
(3) refit F2 on the full outer-training; (4) apply the fitted calibration to the outer-eval
matches (year Y); (5) stamp per-fold provenance. No outer-eval match informs its own
calibration. The **final pre-June parameters** are one `(intercept, temperature)` per tour
fitted on all pre-June OOF — the parameters the staged June opening would apply unchanged.

## Result (34,038 honest OOF matches; raw kept separately)

| Metric | Temperature-only (v1, diagnostic) | Affine (v2, remediation) | M1 band |
|---|---|---|---|
| overall log loss | 0.62211 | **0.62217** | < ln2 (0.69315) ✓ |
| overall Brier | 0.21697 | **0.21699** | < 0.25 ✓ |
| overall cal-in-the-large | +0.02328 ✗ | **+0.00406** | ∈ [−0.02, 0.02] ✓ |
| overall cal slope | 1.0048 | **1.0028** | ∈ [0.90, 1.10] ✓ |
| validation − OOF log loss | −0.00145 | **−0.00150** | ≤ 0.01 ✓ |
| max reliability decile gap | 0.0121 | **0.0132** | ≤ 0.05 (bands ≥500) ✓ |
| ATP cal-in-the-large | +0.02179 | **−0.00332** | ∈ [−0.03, 0.03] ✓ |
| WTA cal-in-the-large | +0.02489 ✗ | **+0.01203** | ∈ [−0.03, 0.03] ✓ |

The affine intercept moves the mean into band while leaving slope, log loss, Brier and
reliability essentially unchanged. Every frozen M1 numeric band is met on this **pre-June
remediation** evidence — but that is development evidence: M1 closure still requires the
June external transfer check under the M1 remediation amendment.

**Final pre-June parameters (to be frozen before June):** ATP `intercept 0.025399,
temperature 1.218638`; WTA `intercept 0.029204, temperature 1.150681`.

Scorecard digest: `sha256:6001657753c8a26ea2ba53e3d323c0a132b1034161b6708d65c2c45e30284470`
(over the file bytes of `AFFINE_REMEDIATION_SCORECARD.json`). The temperature-only vintage
(`docs/evidence/stage2b-f3-confirmatory/M1_SCORECARD.json`) is retained unchanged.
