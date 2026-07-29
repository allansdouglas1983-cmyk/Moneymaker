# TE-0030 — P4: the coherence probe ran, and the layer is dead

Registration: TE-0017 §3 P4 ("deliberately last, with a realistic prior of death").
Harness `tennis_edge/experiments/p4_probe.py`; precondition `p4_precondition.py` (PASS:
5,473 probe-eligible events on 1,290 UTC days, floor 2,000/100). All declarations,
including the two questions, the 97.5% Bonferroni bar and the stop rule, were committed
before the first run.

## The verdict (both questions at 97.5%, day-clustered, seed 20260725)

| | n | estimate | CI 97.5% | reading |
|---|---|---|---|---|
| **(A) gap value conditional on Match Odds** | 130 | **−0.001509 nats** | [−0.010770, +0.005863] | **FAILS to clear** |
| (B) derivative convergence toward MO | 122 | slope +0.0202 | [−0.0077, +0.1846] | does not clear |

**Stop rule, applied as written: (A) fails → the layer is DEAD.** The negative point
estimate says the fitted coherence gap, if anything, mildly *hurt* out-of-sample log score
once the contemporaneous Match Odds price was in the regression. (B)'s failure to clear
means the staleness mechanism was not separately demonstrated either — the sample is
simply too thin to say more, and no more is claimed. The test is never re-sliced; the
solver remains built, tested and unused; `NO_GO_UNPROVEN_INFORMATION_ORIGIN` stays closed.

## Why the sample is 130 rows — the structural finding worth the record

Of 21,142 priced tail events, only **497 (2.4%)** carried a complete, fresh, pre-off
derivative complex (all SET_BETTING outcomes plus a SET_WINNER book printed within the
final hour before T-600):

| exclusion | events |
|---|---|
| SET_WINNER never completely priced pre-off | 16,981 |
| SET_BETTING incomplete pre-off | 2,306 |
| cross-market name attribution failed | 1,008 |
| ambiguous SET_WINNER listing | 348 |
| shape anomalies | 2 |

The literature's warning (DR-COHERENCE-METHOD-001: Match Odds leads price discovery
82–100%+ at one-minute sampling) is visible in the raw listing behaviour: derivative
markets at BASIC granularity barely trade before the off. Projection residuals on the 497
(median 0.0069, p90 0.0160) sit exactly at vig scale — the complexes that do trade are
mutually consistent to within the noise of their own overround, carrying no measurable
independent signal.

## Honesty ledger for this slice

- Three governed plumbing corrections were made between runs, each in its own commit,
  each before ANY row was ever scored: archive duplicate members + per-set SET_WINNER
  pairs; player-relative SET_BETTING scorelines; exact-feasibility screen (a root-solve
  tolerance misused as a market-noise model) replaced by the min-max projection fit, plus
  cross-style name matching. Runs 1–3 scored zero rows; outcomes first entered a
  statistic in run 4, whose numbers stand above unedited.
- One authorised measurement; no re-run to a different answer; the 97.5% bar and both
  question definitions unchanged throughout.

## Programme state

P4 was the last open slice of TE-0017. The programme is complete.
