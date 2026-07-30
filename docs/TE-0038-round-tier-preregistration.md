# TE-0038 — PRE-REGISTRATION: does the model's edge vary by round and tournament tier?

**Written and committed BEFORE the measurement is run.** Nothing below may be revised
after seeing a result; a changed declaration is a new trial with its own record.

## Why ask

Every one of the model's 22 features is a *difference between the two players*. None
describes the match context. `round_name` and `tier` are parsed from the corpus
(`tennis_edge/corpus.py`) and never reach the model.

The interesting question is not whether to add them as features — the market knows the
round too, so a main effect would largely be absorbed by the anchor. It is whether the
model's **edge over the market** is concentrated somewhere. TE-0001 already found tier
inefficiency at Challenger/ITF level; early rounds and lower tiers draw less attention
and less liquidity, which is where mispricing should survive longest if it survives
anywhere.

## Declarations

**Metric.** Per-match log-score gain of the model over the exchange de-vigged price:
`gain = log p_model(winner) − log p_market(winner)`. The same quantity as the headline
+0.0011 nats. **Deliberately NOT ROI**: TE-0035 showed every ROI slice spans zero because
realised return carries enormous per-bet variance, whereas log-score is a continuous
per-match score with far better signal-to-noise and a real chance of resolving.

**Population.** All walk-forward out-of-fold scored rows that join to a corpus match
carrying a round and tier — the same rows the headline number is computed on. Rows that
fail to join are an explicit exclusion, counted and reported, never dropped silently.

**Strata, fixed now.**

- Round: `EARLY` (1st, 2nd Round) · `MIDDLE` (3rd, 4th Round, Quarterfinals) ·
  `LATE` (Semifinals, The Final) · `OTHER` (Round Robin and anything unmatched)
- Tier: `SLAM` (Grand Slam) · `MASTERS` (Masters 1000, Premier Mandatory) ·
  `MID` (ATP500, Premier) · `BASE` (ATP250, International) · `OTHER`

**Estimator.** Mean gain per stratum with a day-clustered bootstrap 95% interval
(2,000 draws, seed 20260730), matching every other interval in this project.

**Primary question — ONE, declared now.** Is the difference between the highest-mean and
lowest-mean *round* stratum non-zero at 95%, by a day-clustered bootstrap of the paired
difference? Tier is a secondary, descriptive read.

**Multiplicity.** This is one additional trial in the SPEC-091 ledger at alpha 0.05.
Per-stratum intervals are descriptive; only the declared contrast above is inferential.
Reporting many strata and then naming the best one is exactly the error this declaration
exists to prevent.

**What a positive result would and would not license.** It would be *evidence for a
governed decision* — a pre-registered prospective test of a context-restricted rule. It
would **not** license changing the served rule, adding a filter, or moving MIN_EDGE. The
frozen policy's own comment stands: a threshold is the classic place to launder an
overfit, and the best one is always found after the fact.

**Expected outcome.** Most likely no stratum contrast clears. The platform's standing
prior is that surprising results are bugs, and a null here is a useful, cheap answer.

## Status

PRE-REGISTERED, not yet run. The result will be recorded as TE-0039 whatever it says,
including a null.

---

## Amendment 1 — 2026-07-30, before any result was computed

**What changed.** The tier mapping gains the WTA's post-2021 tier names, which the
original declaration omitted: `WTA1000` → MASTERS, `WTA500` → MID, `WTA250` → BASE,
plus `Masters`, `Masters Cup` → MASTERS, `Premier 5` → MID and `International Gold`
→ BASE.

**What was seen before amending.** Only the *frequency table of round and tier labels*
(`Counter(x.round_name)`, `Counter(x.tier)`) — that is, which strings exist and how often.
No outcome, no probability, no gain, no result of any kind was computed or inspected.

**Why it is legitimate.** The original mapping already declared the *intent* — SLAM,
top-tier, mid-tier, base-tier — and WTA1000 is exactly the top non-slam tier after the
WTA renamed Premier Mandatory in 2021. Leaving it in OTHER would have silently dumped
3,448 WTA top-tier matches into a residual bucket and made the tier read less meaningful,
not more honest.

**Why it is recorded rather than quietly fixed.** An amendment made after seeing the data
is exactly the manoeuvre pre-registration exists to catch. The defence is not that this
one is harmless — it is that it is *written down*, with what was seen and when, so a
reader can judge it. The round strata, the metric, the estimator and the single
inferential contrast are untouched.
