# TE-0032 — the untouched ten weeks: positive, historical-sized, not yet conclusive

Harness `tennis_edge/experiments/untouched_window.py`, declarations committed before the
run. Window 2026-05-13 → 2026-07-19 (endpoints are external facts: the exchange archive's
edge and the corpus's edge). One fold: coefficients fit strictly on the 95,072 rows before
the window; 980 matches scored that no money reading, gate or frozen coefficient ever
consumed.

## The reading (single question, 95% day-clustered)

| | n | gain (nats) | CI 95% |
|---|---|---|---|
| model − Bet365 baseline | 980 | **+0.002613** | [−0.000342, +0.005631] — **spans zero** (narrowly) |

Per month: May +0.004632 (n=316), June +0.002468 (n=425), July +0.000201 (n=239).
Calibration slope on the window: **+0.959** — the model's probabilities mean what they say
on data it never saw.

## What this does and does not establish

- The frozen pipeline's forecast edge **did not evaporate** on new data: the point
  estimate is positive and of historical size, and calibration held. Ten weeks at ~100
  matches a week is simply not enough volume for this effect size to clear a 95% bar —
  the pre-run power arithmetic already implied roughly double this sample would be
  needed, so "spans zero (narrowly)" is the expected shape of a true-but-small edge at
  this n, and equally the expected shape of no edge. **Neither confirmation nor alarm.**
- The declining month profile (May > June > July) is a diagnostic worth watching in the
  live scorecard, not a finding at these sample sizes.
- Scope limits as declared: Bet365 anchor, forecast quality only. The exchange-anchored
  deployment claim and every money number (fills, SUPPORTED class, Roll band) remain
  untestable on this window until an exchange archive covering it exists — newer BASIC
  months sit behind a Betfair login, which ADR 0015 rules out absolutely; the prior
  archives were founder-provided files.
- One run, as declared. This window is now spent for screening purposes; the next
  fresh evidence is the live scorecard's own accumulation.
