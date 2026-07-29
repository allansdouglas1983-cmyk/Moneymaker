# TE-0028 — S9: the anchor temperature is dead, as its own registration expected

Harness `tennis_edge/experiments/s9_temperature.py`, the governed exception documented in
the module before the run (the pseudo-feature is the row's own offset at identical
knowledge time — zero new information), L2=25 and MIN_TRAIN untouched, the staleness
interaction dropped as lookahead.

## The row (family 4, 98.75%)

| | gain (nats) | CI |
|---|---|---|
| temperature over exchange+features | −0.000002 | [−0.000027, +0.000020] — **spans zero** |
| placebo (within-day permutation) | +0.000009 | [−0.000062, +0.000080] — spans zero ✓ |

Per-year δ: +0.031, +0.004, +0.020, +0.033, +0.026, +0.046, +0.022 (2017–2023), then
**−0.028, −0.023, −0.052 (2024–2026)**. Sign-stable: **NO**.

**Acceptance: FAIL** — the row does not clear and the sign is unstable (the placebo
behaves). Per the pre-registered rule: recorded and stopped; **this row is never re-run
to a different answer.** The 22 price-correlated features evidently already span whatever
shrink direction existed, and the two cited mechanisms cancel to numerical zero.

## The diagnostic worth keeping (diagnostic only — it licenses nothing)

The δ sign flip at 2023/2024 is the third independent appearance of the same structural
story: TE-0019 found the exchange-anchor advantage halving once 2023–2026 entered; TE-0024
found the model's gain concentrated on fresh prices; and now the fitted temperature wants
to *shrink* the anchor pre-2024 and *sharpen* it after. The information relationship
between the T-600s exchange price and outcomes changed in recent seasons. Three
diagnostics, one candidate cause (composition shift vs genuine market sharpening),
zero licence to refit — distinguishing them remains future pre-registered work.

## Programme state

The estimation lens is now exhausted: every registered estimation idea has either shipped
(S3), been shelved with no live path (dispersion), been killed on measurement (network,
temperature), or failed its deployment gate honestly (the re-anchor). What remains of
TE-0017 is S8 (computing) and P4 (precondition check computing).
