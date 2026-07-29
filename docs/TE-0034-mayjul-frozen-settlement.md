# TE-0034 — the frozen money rule on the founder-supplied May–July 2026 archive

Registration committed before the priced table existed (`mayjul_settlement.py`). Source:
founder-provided `may_jul.tar` (sha256:4fda22c9…, BASIC May/Jun/Jul 2026, 49,903 members,
complete). Pipeline identical to every frozen measurement: same link bridge, T-600
horizon, no-threshold bet rule, 2% commission, trade-through fill falsification. Model
fitted once on the 95,072 rows dated ≤ 2026-05-12; the window trained nothing. 944 scored
matches on 68 days (2026-05-13 → 2026-07-19; corpus edge truncates the archive's July).

## The readings (day-clustered 95%)

| | bets | ROI | CI 95% |
|---|---|---|---|
| **PRIMARY: model, SUPPORTED fills** | 526 | **+1.18%** | [−9.93%, +12.81%] — spans zero |
| model, all fills credited | 800 | +2.01% | [−7.33%, +10.96%] — spans zero |
| control, SUPPORTED | 480 | −6.60% | [−15.95%, +2.09%] — spans zero |
| control, all fills | 697 | −6.01% | [−14.39%, +2.97%] — spans zero |

Forecast leg vs the exchange baseline: −0.0019 nats [−0.0084, +0.0031] — spans zero
(the historical gain is +0.0011; a ten-week window cannot separate the two).

## The honest reading

1. **Nothing contradicted the frozen claims.** The model's point ROI is positive in both
   readings and sits inside a whisker of the historical +2.63%; the control — the same
   rule driven by the market's own probability — *lost* ~6%, exactly the historical
   pattern that says the model's selection, not the price mechanics, carries whatever is
   there.
2. **Nothing was confirmed either, and could not have been.** 526 supported bets price a
   ±11% interval. TE-0012's power arithmetic (≈31,000 bets to resolve a 2% return at this
   variance) predates this run and predicted precisely this shape. Ten weeks of the whole
   tour produces ~500 qualifying bets; the money question resolves on years of prospective
   volume or not at all — this is a property of betting variance, not of the platform.
3. **What the window was worth**: it was the first money evaluation in the project's
   history where *every* rule provably predates *every* price. The +2.63% class survived
   contact with genuinely unseen prices in sign and rough size, while the control's loss
   reproduced. That is consistency evidence of the strongest available kind for this
   sample size — and it is recorded as exactly that, not as proof.

All numbers are hypothetical trade-through returns; TE-0020's execution-cost band applies
unchanged. One run, as registered; the window is spent.
