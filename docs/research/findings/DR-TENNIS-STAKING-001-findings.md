# DR-TENNIS-STAKING-001 — staking, bankroll and ruin: what the literature actually supports

**Status:** ASSESSED. **Date:** 2026-07-30. **Blocking scope:** NONE.
**Authorisation:** founder directive, 2026-07-30 (`/deep-research`), which is the explicit
owner authorisation the routing protocol requires for a Claude-run workflow.

**Founder's question, verbatim:** *"what betting systems processes and features we could
and should add to make this more profitable … Are there better algorithms or systems to
use a certain amount of money or percentage of the pot per bet based on odds and what we
have so money slowly builds and is unlikely to zero completely."*

## What this changes: NOTHING, yet

`CLAUDE.md` states the v1 rule: **no Kelly staking; fixed minimum stake plus an absolute
loss budget.** SPEC-060 encodes it. Nothing below alters that, and nothing below authorises
spend. Research informs decisions; it never proves a gate (ADR 0013 / Amendment A §4).

There is a second reason to leave the rule alone, and it is the stronger one. **Every
staking scheme in this document is a function of the edge.** With no established edge, a
staking rule is a rule for sizing a number we do not have. TE-0020 supersedes TE-0019's
headline whenever the two are read together: the supported reading clears zero uncosted and
spans zero once the declared central execution-cost assumption is applied. Sizing that is
sizing noise, and the more sophisticated the sizing, the more confidently it will do so.

## Method and its limits

Fan-out web search, source fetch, then three-vote adversarial verification per claim, with
a claim killed on a majority refutation. 114 claims extracted; 19 reached the verification
stage before the run was salvaged (see *Provenance* below); **7 of those 19 were refuted.**

A 37% refutation rate on claims that had already passed extraction is the headline
methodological fact. Every refutation below was of an *overreach* — the underlying papers
are real and peer-reviewed, and the quotes were verbatim; what failed was the leap from
what a paper says to what it was being used to justify. That is the same failure mode as
TE-0038's anti-conservative declaration, arriving from a different direction.

## Verified — survived adversarial review

**1. Fractional Kelly is the standard response to not knowing your edge.**
Verified verbatim against MacLean, Thorp & Ziemba, *Good and bad properties of the Kelly
criterion*, Quantitative Finance 10(7):681–687 (2010). Half-Kelly is not merely a
risk-appetite preference; parameter uncertainty is the recognised academic justification,
citing MacLean, Thorp & Ziemba (2010). Four statisticians, peer-reviewed venue, not a
gambling outlet.

Read against this project: our edge estimate is a *distribution*, not a point (SPEC-034),
and its lower bound spans zero at declared costs. The literature's own logic therefore
points below fractional Kelly, not to it.

**2. Kelly's bad properties are as well documented as its good ones.**
Same source. In continuous-time approximations the growth rate goes to zero as the wager
approaches twice the Kelly fraction — i.e. overbetting relative to a *misestimated* edge
destroys the growth the criterion exists to maximise. Since our edge is uncertain, the
distance between "our Kelly" and "true 2×Kelly" is unknown, which is exactly the regime the
paper warns about.

**3. Ville's inequality gives exactly valid continuous monitoring — and it is the
gambler's-ruin theorem.**
For a test martingale starting at 1 under the null, P(it EVER reaches α) ≤ 1/α, uniformly
over all times and all stopping rules. Two consequences, and they are the same theorem:
- Statistically, this is the licence to watch a live P&L or evidence process continuously
  and stop whenever you like, with no alpha inflation from peeking.
- Financially, the same bound reads directly as risk of ruin: a gambler starting with unit
  capital has probability at most 1/α of ever multiplying it by α.

This is the single most directly usable result in the whole review, and it is **already in
the specification**: SPEC-096 (anytime-valid monitoring, `enforcement_state: planned`)
requires exactly this and explicitly forbids rolling fixed-window threshold alarms for
statistical halts. The literature confirms the spec was right; it does not activate it.

**4. Log-score edge converts directly into evidence accumulation rate.**
Log-optimal growth is the correct objective for accumulating sequential evidence, and the
likelihood ratio is growth-rate optimal. Expected log-score improvement per observation
*is* the exponential growth rate of evidence, so a measured per-match log-score edge
converts directly into the number of matches an anytime-valid process needs to cross a
chosen threshold.

This matters more than the staking question. The project's standing power arithmetic is
n* ≈ 31,000 bets (TE-0012), derived from **P&L** variance. But the platform's measured
quantity is a **log-score** edge of +0.001064 nats, and TE-0036 already established that a
small real-money trial cannot settle whether the edge exists (29% ruin if real, 76% if not,
at 50 units). A log-score-based evidence process is a different and far cheaper instrument
than a P&L-based one, on data we already collect, with no money at risk.

**5. CLV is informative as a ranking signal even where it is miscalibrated in level.**
In one 3,000-bet ATP sample, sorting by closing-line value gave a monotone relationship with
realised yield across quartiles. Note the direction of this finding carefully: it supports
CLV as an *ordering*, not as a calibrated forecast of return. Our `/clv` endpoint reports a
mean and an interval, which is a level claim; this says the ranking is the more robust read.

## Refuted — 7 of 19, all overreach

- **Baker & McHale (2013) shrinkage magnitudes.** The paper is genuine and peer-reviewed
  (*Optimal Betting Under Parameter Uncertainty: Improving the Kelly Criterion*, Decision
  Analysis 10(3):189–199, DOI 10.1287/deca.2013.0271) and its empirical application is
  **tennis betting**, so it is squarely on point. But specific claimed shrinkage factors and
  their transferability were refuted: the magnitudes were unverified, and **the authors'
  own 2016 follow-up** (*Making Better Decisions: Can Minimizing Frequentist Risk…*)
  contradicts part of what the 2013 paper was being used to assert.
- **A 3,000-bet self-reported record showing +8.9% ROI against a −0.2% closing-line
  expectation**, presented as proof that CLV is not necessary for edge. Refuted as evidence:
  self-reported, and the author's own significance claim carries no test statistic, standard
  error, confidence interval or variance model anywhere in the article.

The pattern is worth stating plainly: **the sources are real; the inferences drawn from them
in secondary writing are not.** A staking rule adopted from a blog citing Baker & McHale
would have imported a magnitude the authors never established and later partly retracted.

## What follows for this platform

**Do not change the staking rule.** Fixed minimum stake and an absolute loss budget remain
correct, and are *more* clearly correct after this review, not less: fractional Kelly is
justified by parameter uncertainty, our parameter uncertainty currently spans zero, and the
honest fraction of Kelly for an edge that may be zero is zero.

**The genuinely actionable item is not a staking rule at all.** It is item 4: build the
evidence process on log score rather than P&L, under Ville's inequality, as SPEC-096 already
specifies. That is measurement, costs nothing, risks nothing, and answers the question the
trial cannot afford to answer with money. It remains `planned` and its activation is a
human-controlled specification change.

**On "money slowly builds and is unlikely to zero completely":** the second half is already
handled — the absolute loss budget is a hard floor on damage and SPEC-065 makes it
monotonically non-increasing. The first half is not a staking problem. Compounding requires
a positive edge to compound; no sizing rule creates one. The order of operations is
established the edge first, then the sizing, and the literature reviewed here does not
change that order.

## Provenance and a caveat about this document

Both workflow runs recorded `null` for every agent result — 48 of 48 in this run — while the
agents' transcripts contained full structured output. The findings above were **salvaged
from the transcripts**, not read from the workflow's return value. Consequences to be
honest about:

- The synthesis stage never ran. This is an assessment written from verified claim
  fragments, not a returned report saved verbatim as the protocol prefers.
- 114 claims were extracted but only 19 reached three-vote verification. **The unverified 95
  are not recorded here as findings** — an extracted claim that has not survived refutation
  is not evidence, and this document would be worth less if it pretended otherwise.
- Anything above that a future decision leans on should be re-verified against the primary
  source before it does.

## Ledger

No SPEC-ID changes. No gate evaluated. No spend authorised. No change to `CLAUDE.md`'s
staking prohibition, SPEC-060, or SPEC-061.
