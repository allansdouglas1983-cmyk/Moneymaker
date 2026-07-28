# TE-0020 — The Roll execution-cost band: the strict money number does not survive the declared cost assumption

TE-0019's headline was that the supported-only reading cleared zero for the first time:
+2.63% [+0.94%, +4.29%] on 24,886 bets over eleven years. That number still assumed every
fill costs nothing — the bet is credited at the last-traded print itself. The
DR-TENNIS-MICROSTRUCTURE-001 standard, adopted as binding, says a trace-only money claim is
quoted with an execution-cost sensitivity band or it is not quoted. This is the band.

## What was declared before any number was computed

Recorded in `tennis_edge/experiments/roll_band.py`'s module docstring, committed before the
run: per-selection Roll spread over each market's full pre-off print series (the
conservative window); the fired-bet set held fixed; winning returns recomputed at
`odds · exp(−f·s)` for f = ½ (central) and f = 1 (pessimistic); unmeasured sides imputed
with the pooled median of measured fired-bet sides, labelled, coverage reported. **The
verdict question: does the supported-only reading still clear zero at the half-Roll
haircut?**

## The measurement

Baseline reproduced exactly (same seed, same rule, same table): 24,886 bets,
+2.63% [+0.94%, +4.29%]. Spread coverage over the fired supported bets: 94.0% measured
(93.8% matched to the backed side, 0.2% ambiguous-side taking the larger spread), 6.0%
imputed at the pooled median. Measured relative spread: median 1.91%, IQR [1.45%, 3.11%].

| reading | ROI | 95% CI | verdict |
|---|---|---|---|
| uncosted (TE-0019) | +2.63% | [+0.94%, +4.29%] | clears zero |
| **half-Roll haircut (central)** | **+1.25%** | **[−0.41%, +2.86%]** | **spans zero** |
| full-Roll haircut (pessimistic) | −0.09% | [−1.70%, +1.46%] | spans zero |

**The answer to the declared question is no.** At the central cost assumption the point
estimate stays positive but the interval spans zero; at the pessimistic bound the point
estimate itself is approximately zero.

## What this means, and what it does not

- The eleven-year money verdict, quoted whole, is now: *positive at every reading, resolved
  from zero only under the zero-cost fill assumption.* The forecast edge (+2.63% against a
  control losing −1.33% at the same prices) is real in the record; whether it survives
  crossing the book is exactly as unresolved as the band says.
- This is the machinery working, not a reversal. TE-0019 already owed this band before any
  customer-shaped quoting; the band was computed and the number is what it is.
- The estimator window (full pre-off series) was declared conservative — spreads tighten
  toward the off, so the true cost of crossing at T-600s is plausibly below the median
  1.91% used here. **That observation licenses nothing.** An execution-window variant is a
  new pre-registered slice if it is ever run; it was not part of this declaration, and this
  result is not re-litigated by narrowing the window after seeing it.
- The AU-events commission caveat still attaches to every row (flat 2% is a labelled
  modelling assumption, not valid for Australian-based events).
- Nothing changes on the site: no model, threshold or policy is derived from any of these
  rows. The site's shadow numbers remain research display with the hypothetical banner.

## Standing money statement after TE-0019 + TE-0020

Over 2015–2026 at T-600s crossable-in-record prices, the model's flat-stake hypothetical
return is +2.63% [+0.94%, +4.29%] before execution costs, +1.25% [−0.41%, +2.86%] at the
central Roll cost, −0.09% [−1.70%, +1.46%] at the pessimistic bound — supported fills only,
NO_EVIDENCE kept in the denominator of the evidence split, control negative at the same
prices. That whole sentence is the claim; no clause of it is quotable alone.
