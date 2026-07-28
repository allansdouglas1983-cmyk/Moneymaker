# DR-TENNIS-FORECAST-LIT-001 — Pre-off tennis forecasting that beats a market price (ADVISORY)

**Status:** REQUESTED / AWAITING FOUNDER EXTERNAL RESEARCH. Contains **no conclusions**.
Findings inform decisions and never prove a gate (Amendment A §4).

**Classification:** ADVISORY. No work pauses on this. It exists to stop us re-deriving,
badly, methods the literature has already tested — and to stop us spending weeks on
approaches already shown not to survive out-of-sample.

**Requested:** 2026-07-27.
**Related:** SPEC-030, SPEC-031, SPEC-032, SPEC-034, SPEC-090, SPEC-097; ADR 0013;
`tennis-edge/tennis_edge/residual_features.py`, `residual_model.py`.

## Why this is being asked now

The platform holds a market-anchored residual model: the de-vigged closing price enters as an
**unpenalised offset** and 22 features add signed corrections, fitted by full Newton with
ridge L2 = 25.0 fixed a priori. Out-of-sample over 63,576 matches it beats the closing price
by **+0.001058 nats**, 95% CI [+0.000635, +0.001471], day-clustered. A feature-permutation
placebo returns −0.000161 [−0.000265, −0.000053].

That gain is real but small. The layers added so far returned, paired: serve decomposition
+0.000047 [+0.000013, +0.000081]; durability (head-to-head, retirement risk, workload,
surface switch) +0.000150 [+0.000004, +0.000293]. Each clears zero by a hair on a large
sample. We have plausibly exhausted the obvious feature families, and the question is whether
the literature knows of families we have not tried.

**Current feature families** (so the answer can skip them or explain why ours are weaker):
Elo variants (standard, surface-specific, weighted); a pyramid Elo spanning Grand Slam down
to Futures with a tournament-week lag; ATP/WTA ranking gap; a Barnett–Clarke point model
driven by serve/return rates; decomposed serve statistics (first-serve rate, first- and
second-serve win rates, ace rate, double-fault rate, break-point save rate, return rate);
head-to-head shrunk toward a prior; retirement propensity; 14- and 28-day workload; surface
transition since last event.

## Questions (answers with sources and publication dates)

1. **Published methods that beat a market price out-of-sample.** Since roughly 2018, which
   pre-off tennis forecasting methods have demonstrated an out-of-sample improvement over a
   *bookmaker or exchange price* — not merely over a ranking baseline or a naive Elo? For
   each: the exact benchmark used, the sample size, the effect size, and whether the
   evaluation was clustered or assumed independence between matches in a tournament.
2. **Effect sizes for calibration.** What magnitude of log-score or Brier improvement over a
   closing price is typical in credible published work? Our +0.001058 nats needs a reference
   class: is that at the low end of real published effects, in line with them, or larger than
   most (which would make us suspicious of our own result)?
3. **Feature families we have not tried.** Which inputs have published evidence of
   *incremental* value over an Elo-plus-serve-statistics baseline? Point-by-point data,
   fatigue and travel, altitude and ball type, court speed indices, injury reports, scheduling
   and time-of-day, momentum or in-match state carried across matches, opponent-adjusted
   serve/return, anything else. Please distinguish evidence of incremental value from evidence
   of value in isolation — most of our candidates correlate heavily with what we already have.
4. **Model classes.** Is there credible evidence that a particular model class (gradient
   boosting with a grouped objective, Bayesian hierarchical, state-space/dynamic rating,
   neural) reliably outperforms a well-specified market-anchored linear residual for this
   problem? Specifically at our scale — roughly 96,000 matches, 22 features.
5. **Where the market is weakest.** Published or well-evidenced practitioner findings on
   which market segments are least efficient in tennis: lower tiers (Challenger/ITF),
   women's versus men's, early rounds, particular surfaces, qualifying, specific price bands.
   We measured our own tier result once — the Challenger/ITF tier cost 3.67% ATP and 4.66%
   WTA round-trip against 1.12% on the main-tour exchange — so segment claims must come with
   an execution-cost caveat to be useful.
6. **Negative results.** Which approaches have been *tried and shown not to work* in credible
   work? This is as valuable as the positive list and is rarely published prominently.
7. **Evaluation practice.** What is considered correct practice for evaluating a tennis
   forecast against a market: unit of analysis, clustering, multiplicity control, the
   treatment of retirements and walkovers, and how closing-line value is and is not used.
   We treat the match as the unit and cluster by day; CLV is a diagnostic family and never a
   training target.

## Constraints on the answer

- **Jurisdiction/date:** current as of 2026-07. Sources dated.
- **Source hierarchy:** peer-reviewed and preprint literature first; reputable practitioner
  work with disclosed methodology second; marketing material and tipster claims are not
  evidence and should be excluded rather than caveated.
- **Anything requiring paid data must be flagged as such.** The founder has ruled out
  further data purchase. A method that needs point-by-point or paid feeds should be reported
  as unavailable-to-us rather than recommended, and it is still worth listing so the boundary
  is explicit.
- **No betting advice, no staking systems, no tipping services.**

## Deliverables

1. A table of candidate methods: method, benchmark beaten, effect size, sample, data
   required, whether that data is free, and a confidence note.
2. A short list of feature families with published *incremental* value over our baseline.
3. A negative-results list.
4. A note on whether our measured effect size is plausible, small, or suspiciously large.

## Acceptance criteria

Every claim carries a source and a date. Effect sizes are reported with their benchmark and
sample size, or omitted. Where the literature disagrees, the disagreement is shown rather
than resolved by preference.

## If unresolved

Work continues. We proceed with the exchange re-anchoring and cross-market coherence already
scoped, which do not depend on this. The cost of never answering it is that we may spend
effort on feature families the literature already knows to be empty.
