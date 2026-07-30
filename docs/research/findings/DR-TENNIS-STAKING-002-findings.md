# DR-TENNIS-STAKING-002 — the staking algorithms, named, with their numbers

**Status:** ASSESSED. **Date:** 2026-07-30. **Blocking scope:** none — nothing here is
implemented yet, deliberately.

Supersedes the partial `DR-TENNIS-STAKING-001`, which reported only 19 verified claims
because the run had not finished. This is the same run at 95 agents: **114 claims, 61
reaching adversarial verification, 25 refuted (41%).**

**Why this document exists at all.** A previous attempt at this went straight to code and
invented its own risk parameters — a 2% single-bet cap, a 5% daily cap, a 20% reserve, an
80% drawdown brake. None of those came from any source. They were plausible-looking numbers
wearing citations that belonged to other claims. That is the failure this file replaces:
below, every parameter has a name, a paper and a measured consequence.

---

## The recommended algorithm: RISK-CONSTRAINED KELLY

Not fractional Kelly. The research is explicit that fractional Kelly is **an ad hoc
drawdown fix that is Pareto-dominated**:

> at a matched drawdown risk of 0.1, fractional Kelly delivered growth rate ~0.035 versus
> **0.047 for risk-constrained Kelly** — roughly a third less growth for identical risk.

The formulation (Busseti, Ryu & Boyd) maximises expected log growth **subject to an
explicit bound on the probability of drawdown**. It is convex, always feasible, and has a
closed-form survival constraint:

```
if   E(rᵀb)^(−λ) ≤ 1        with  λ = log β / log α
then Prob(W_min < α) < α^λ
```

One λ bounds the **entire CDF of minimum wealth** simultaneously — pick "10% chance of a
30% drawdown" and every other drawdown level is bounded too. This is the thing to build.

Two properties that matter operationally:

- **Hard no-bet property.** Holding 100% cash is optimal if and only if no available bet
  has expected return above 1. The framework *refuses* to size a non-positive-expectation
  bet — it cannot be coaxed into betting a zero edge, which is exactly our current state.
- **It reduces to familiar things.** In the low-risk-aversion limit the drawdown constraint
  collapses to `(λ/2)·var log(rᵀb) ≤ E log(rᵀb)` — formally the same shape as Markowitz
  mean-variance and the volatility-targeting used in quantitative finance. That is the
  cross-market connection: this *is* the stock/crypto sizing method, specialised.

---

## Why full Kelly must never be used here

Not caution — measurement.

> unmodified full Kelly and unmodified maximum-Sharpe produced a **100% ruin rate** on both
> the basketball (7,200 games) and football (14,400 matches) datasets when driven by
> realistic, imperfect probability estimates.

The mechanism is selection, not bad luck. Kelly sizes on the *estimate*, so selections whose
probability happens to be overestimated are simultaneously the ones that look most
attractive. Errors do not cancel:

> plug-in Kelly using estimated rather than true probabilities systematically OVER-bets, and
> this bias does not wash out with unbiased estimation error.

And over-betting is strictly dominated: at exactly twice Kelly the growth rate falls to the
risk-free rate, and above Kelly both growth *and* the probability of doubling before halving
decline together.

A tennis-specific corroboration: one published study had to **hard-cap its Kelly rule at 1%
of bankroll to prevent early near-bankruptcy** on estimated tennis edges.

---

## How much the safety actually costs: very little

Buchdahl's 10,000-run Monte Carlo, 250 even-money bets at a genuine 4% edge:

| fraction | P(drawdown > 20%) | median terminal bank |
|---|---|---|
| full Kelly | 25% | 122 |
| half Kelly | 12% | 116 |
| quarter Kelly | **2%** | 109 |

**Quarter-Kelly removes 92% of the drawdown risk and costs 13 points of median terminal
bank.** That is the "keep it trending up safely" trade, quantified — and it is a bargain.

Corroborated at a 2% advantage: full Kelly gives a 0.67 probability of doubling before
halving; half Kelly raises it to **0.89 while retaining 0.75 of the growth rate**.

---

## Stake must FALL as the odds lengthen — this is the answer to "£13 on A, £9 on B"

The Kelly fraction is `μ/K` where μ is expected return and K the fractional odds. So a flat
percentage that is correct at even money becomes progressive over-betting as prices lengthen:

> a flat 1% stake at K=20 with μ=0.01 is **20× the Kelly fraction**.

Ruin probability at a constant +1% edge and 1% stake:

| odds | P(ruin) |
|---|---|
| even money (K=1) | 13% |
| 2-to-1 (K=2) | 34% |
| 20-to-1 (K=20) | **64%** |

And the sharpest warning in the whole review — at K=20 a **+1% edge and a −1% edge produce
nearly indistinguishable outcomes** (ruin 0.64 vs 0.71). On longshots, outcome data cannot
tell a winning system from a losing one.

Closed form for ruin, directly computable: `P(ruin) = ((1−p)/p)^n` where `n = bankroll/stake`.

---

## Sizing on a posterior, not on the estimate

Under a Beta(a,b) prior the Bayes-optimal fraction is **exactly Kelly evaluated at the
posterior mean** `p̂ = (x+a)/(n+a+b)`, not at the raw sample frequency. That is a principled
replacement for picking a fraction by feel.

Worked example, with a market-efficiency prior Beta(50,50) and a 100/180 record at 1.952:
plug-in Kelly says **8.9%**; the uncertainty-adjusted fractions say **3.4%–5.6%**, landing
near half-Kelly.

It is violently sensitive to how sceptical the prior is: tightening prior SD from 0.05 to
0.035 leaves plug-in Kelly at 6.7% but **collapses the Bayes fraction from 2.5% to 0.5%** —
a 13× cut. Given our edge interval spans zero, a sceptical prior is the honest one, and it
implies a very small fraction.

**Distributionally robust Kelly** (worst-case over a box around your own estimates) was the
safest strategy in every experiment — highest minimum wealth, 0.23 vs 0.11 for fractional
Kelly — at the cost of the lowest final wealth (1.39 vs 2.4).

---

## The sample sizes, which govern everything

- **~1,675 bets** at odds 1.95 for decisive evidence (Bayes factor 100) of a +5% edge.
- **~3,500** at odds 5.00; **~10,400** at odds 7.00.
- Telling a 1.0% edge from a 1.1% edge: **two million trials.**
- Bayes factors are systematically more conservative than p-values on betting records — a
  +5% yield over 1,000 bets at 1.95 gives BF 13.7 against a p-value of 0.75%.

Expected maximum drawdown has a closed form. Zero drift: `E[MDD] = 2γσ√T`, γ = √(π/8) ≈
0.6267. Positive drift makes it grow only logarithmically in T; negative drift makes it grow
linearly and converge on losing everything — so **no drawdown-based stop can save a negative
edge**.

---

## Refuted — 25 of 61, and the pattern matters

Sources real, quotes verbatim, **inferences overreached**. The one that most directly
contradicts a popular belief:

> a 50% fractional (half) Kelly strategy produced LOWER expected log growth than naive
> plug-in Kelly in **every one of four experiments** — 13.268 versus 18.134, ~27% below.

So "just use half Kelly" is not universally right either. Explicitly modelling the
uncertainty beat plug-in Kelly, but only marginally (18.484 vs 18.134), and **tightening the
risk constraint too far is actively counterproductive** — chance-constrained scores fell
18.253 → 16.454 → 12.15 as the constraint tightened from a=0.40 to 0.25 to 0.10. The
constraint must be calibrated, not set conservatively by reflex.

Also refuted: Martingale in every form. It does not change expected value (enumeration over
all 8 three-spin permutations sums to exactly zero); its progression multiplier is
`odds/(odds−1)`, so eleven even-money losses need a 1,024-unit stake to win 1; simulated
bankruptcy probability is 53% at fair odds and 78% at a 10% margin, against ~0% for level
staking. It converts many small wins into one rare catastrophe.

---

## What this means for the platform

1. **Build risk-constrained Kelly**, not fractional Kelly — a third more growth at matched
   risk, and it refuses zero-edge bets by construction.
2. **Size on a posterior mean under a sceptical prior**, never the plug-in estimate.
3. **The drawdown bound is the parameter to choose**, and it is chooseable in plain language
   ("10% chance of a 30% drawdown") rather than by picking a fraction by feel.
4. **Stake must fall with lengthening odds** — `μ/K`, not a flat percentage.
5. **None of it creates an edge.** With a zero edge, risk-constrained Kelly stakes zero;
   with a negative one, no drawdown rule prevents the loss.

## Unknowns

The λ calibration for our specific edge distribution is not established. Neither is whether
our edge is positive at all — which is upstream of every number here. The sample-size results
above say a single-person operation cannot resolve a sub-1% edge from settled P&L on any
human timescale, which is the standing argument for CLV as the evidence route.
