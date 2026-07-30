# TE-0048 — REGISTRATION: the 1.50–2.00 dead band, a pre-registered selection test

**Date:** 2026-07-30. **Type:** pre-registration, frozen before any qualifying data is
scored. **Origin:** TE-0043 Finding 3 — the 1.50–2.00 odds band returns essentially zero
in all four measured configurations (5%/2% commission × all-fills/supported: +0.54%,
+0.87%, +0.13%, +0.54%, every one spanning zero), while 3.00–6.00 is the strongest band
in all four. Four-way replication on materially different bet sets, which TE-0043 itself
says is the ONLY kind of cell that may graduate into a candidate finding — and it also
says no threshold or band may be adopted without a pre-registered selection rule and a
multiplicity correction. This document is that pre-registration.

## Hypothesis (declared before the data that will judge it exists)

H1: excluding backs whose odds fall in [1.50, 2.00) from the fired set improves the
per-unit ROI of the fired portfolio, because the band contributes turnover and variance
with ~zero expectation.

H0: the band's measured ~zero is sampling noise around the pooled positive edge and
exclusion buys nothing.

## The test, exactly

- **Universe:** bets fired by the operative rule (MODEL source, min_edge 0.02 strict,
  SUPPORTED fills, 2% commission) on data with knowledge-time strictly after
  **2026-07-19** — the end of the untouched May–Jul window already partially inspected.
  Data seen before this registration (the 11-year corpus AND the May–Jul window) is
  formation evidence and may never be re-scored as confirmation.
- **Comparison:** paired, per UTC day — portfolio A (fired, all odds) vs portfolio B
  (fired, odds in [1.50, 2.00) removed). Same days, same prices, same model; the
  difference isolates the band rule.
- **Endpoint:** day-clustered bootstrap CI95 (2,000 draws, whole UTC days) of the
  difference in per-unit ROI, B minus A.
- **Decision rule:** adopt the exclusion only if the CI95 lower bound of (B − A) is
  strictly above zero at **α = 0.05/3** (Bonferroni: this registration is one of three
  live selection hypotheses this programme may plausibly run — dead band, 6.00+ cap,
  threshold refit; the divisor is declared now so it cannot shrink later).
- **Minimum evidence:** no evaluation before the qualifying window holds ≥ **500 fired
  bets** spanning ≥ **60 distinct days** — roughly the corpus's fired cadence over two
  months. Peeking earlier is prohibited; SPEC-096-style anytime-valid methods may
  replace this fixed gate only by amendment before the first look.
- **While pending:** the band stays IN the fired set everywhere — site, ledger, staking
  card. Nothing changes on registration day. The D7 allocator sizes the band's bets
  like any other (their conservative edge is what it is); the correlation charge k
  counts them.

## Why not adopt now

The four-way replication is strong formation evidence, but every cell of it was
computed on data that also chose the model, the threshold sweep grid and the band
boundaries themselves. Adopting from the same data that suggested the hypothesis is the
multiple-comparisons trap TE-0043's own caveats name. The cost of waiting is small
(the band's measured contribution is ~zero — that is the hypothesis); the cost of a
false adoption is a permanently narrowed universe justified by noise.

## Ledger

No SPEC-ID changes. No gate evaluated. No selection rule changed today. Evaluation
tooling: `tools/sweep_selection.py` already scores band-restricted portfolios; the
paired evaluation runs when the minimum evidence exists, and its result appends here.
