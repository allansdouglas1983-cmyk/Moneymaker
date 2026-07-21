# Stage 2G DP1 development evaluation — FROZEN VERDICT: STOP_DP1_HARM

Applied `specs/programme/stage2g-dp1-continuation-rule-v1.yaml` to the single corrected
per-tour-isolated evaluation (execution commit 470b2865). No threshold changed after opening.

| requirement | result |
|---|---|
| A integrity | PASS (ATP raw = unread reference byte-identical; WTA double-run byte-identical; reconciliation EXACT/1e-6; all 146 survivors founder-approved) |
| B paired proper-score non-harm (≤ +0.0007) | **FAIL** — DP1−F2 raw development paired delta ATP +0.02247, WTA +0.01353 nats |
| C overall calibrated adequacy | PASS (log loss 0.6268 < ln2; Brier 0.2185 < 0.25; cal-in-large −0.0007 ∈ ±0.02; slope 0.9708 ∈ [0.90,1.10]) |
| D tour adequacy (ATP,WTA) | PASS both |
| E calibration improvement over F2 | FAIL (DP1 pooled |slope−1| 0.0292 vs F2 0.0279 — not better overall) |
| F temporal transfer | PASS (val ≤ oof+0.01 both; no annual ≥1000-pred block ≥ ln2) |
| G uncertainty | DIAGNOSTIC — structural properties property-tested; empirical coverage is a governance gap (no frozen gate), not converted to a post-result threshold |

**Verdict: STOP_DP1_HARM.** DP1 (dynamic Glicko-2) is materially worse on proper score than
the frozen F2-v1 global Elo baseline on the paired development population, exceeding the
+0.0007 harm boundary on both tours. Both models beat the structural null (ln2 = 0.6931),
so DP1 carries real information — but the added dynamic complexity (rating deviation,
volatility, inactivity) does not improve, and in fact degrades, development proper score
relative to the simpler baseline. Calibration is adequate; discrimination is not superior.

Per continuation-rule §H and founder §7: DP1 is preserved as a **failed registered model**;
**Slice 4 is NOT begun**; returned to the founder. This is the platform's expected outcome —
no incremental edge established, cheaply and honestly.
