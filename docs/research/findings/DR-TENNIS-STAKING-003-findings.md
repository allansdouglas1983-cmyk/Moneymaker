# DR-TENNIS-STAKING-003 — the completed deep research: do NOT adopt a Kelly rule

**Status:** ASSESSED. **Date:** 2026-07-30. **Blocking scope:** none, but it **overturns**
the recommendation in DR-TENNIS-STAKING-002.

The founder's `/deep-research` run, finished: **105 agents, 8.26M tokens, 1,290 tool calls,
2h 40m.** Raw verified report alongside this file as `DR-TENNIS-STAKING-003-RAW-report.json`.
Eleven findings survived three-vote adversarial verification.

**This supersedes DR-TENNIS-STAKING-002, which I wrote from a partial harvest of the same
run and got wrong.** 002 recommended risk-constrained Kelly. The completed research says
adopt no Kelly rule at all. The difference is not a refinement; it is a reversal, and 002
should be read only for the refuted-claims section.

---

## The recommendation: keep flat minimum stakes. Adopt nothing.

> retain flat minimum stakes plus the hard absolute loss budget, and adopt NO
> Kelly-proportional rule (full, half, quarter, or Bayesian-shrunk) while the edge interval
> spans zero.

The reasoning is one sentence and it is decisive:

> Every Kelly variant presupposes a positive, correctly-signed edge; when the sign itself is
> unproven, no shrinkage factor is protective, because a mis-signed f* scaled by 1/2 or 1/4
> is still a negative-expectation bet.

Shrinking a stake reduces the *size* of the mistake. It does not change its *sign*. Quarter
Kelly on an edge that is actually negative loses more slowly and just as certainly.

SPEC-060 and SPEC-061 — fixed minimum stake, absolute loss budget, skip when the minimum
exceeds permitted risk — are already exactly what this literature prescribes. **The correct
action is to leave them alone, not to "upgrade" them.**

---

## The arithmetic that settles it operationally

At the platform's own +2.3% ROI, full Kelly by price:

| odds | full Kelly |
|---|---|
| 1.2 | **11.7%** of bankroll |
| 1.5 | 4.69% |
| 2.0 | 2.35% |
| 3.0 | 1.17% |
| 6.0 | **0.47%** |

Two consequences, and they point in opposite directions:

1. **Kelly is unimplementable downward.** On a few-hundred-pound bank a GBP 1-2 exchange
   minimum is 0.3%-0.7% of bank — which **already equals or exceeds full Kelly at odds
   6.0 (0.47%)**. On the underdog bets where the measured edge is *strongest* (+4.3%), no
   fractional-Kelly rule can be expressed at all: the smallest bet you can place is already
   more than Kelly says to bet.
2. **Kelly is dangerous upward.** At odds 1.2 it demands 11.7% of bankroll per bet — in the
   favourites segment where the measured edge is *weakest* (+0.8%) and least distinguishable
   from zero.

So a Kelly rule on this operation would bet nothing where the edge is best and a tenth of
the bank where it is worst. That is the opposite of what it is for.

---

## Why over-betting is the specific danger

- **Plug-in Kelly systematically over-bets**, and the gap grows with the variance of the
  estimate *even when the estimate is unbiased*. There is an additional winner's-curse
  effect because bets are **filtered on estimated edge** — which is exactly what "flagged
  bets" means here.
- **The penalty is asymmetric.** Betting exactly twice Kelly reduces the growth rate to the
  risk-free rate. Since Kelly is linear in the edge, **a bettor whose true edge is half what
  they measured is betting exactly 2x Kelly while believing they are at full Kelly** —
  sitting precisely on the zero-growth point with full variance.
- **Kelly is the most estimation-sensitive objective in the allocation literature.** Errors
  in means dominate errors in variances by ~20:2:1, and for a log/Kelly bettor (risk
  aversion ≈ 0) it reaches **~100:3:1**. The edge is the mean, and the mean is the one thing
  this operation has not established.
- **"Kelly never risks ruin" is a theorem about infinite divisibility, not an operational
  guarantee.** Over 700 bets each with a genuine, correctly-known 14% edge, full Kelly can
  turn $1,000 into $18; half-Kelly only reaches $145. A minimum exchange stake breaks
  divisibility outright, so the theorem does not apply here at all.
- Measured cost of the estimation tax: betting on estimated rather than true probabilities
  captured only **66% of achievable log growth** (18.134 vs 27.463 over four 2,500-trial
  experiments).
- Full Kelly breached a **30% drawdown 39.7% of the time** in 10,000-path Monte Carlo
  (56.9% under lognormal returns).

---

## The one constructive, immediately usable result

For **flat staking** — an additive random walk, which is exactly this operation's regime —
expected maximum drawdown has an exact closed form (Magdon-Ismail et al., *J. Applied
Probability* 41(1), 2004):

```
zero drift:      E[MDD] = 2*sqrt(pi/8)*sigma*sqrt(T) = 1.2533 * sigma * sqrt(T)
positive drift:  E[MDD] = (2*sigma^2/mu) * Q(alpha^2),  Q_p(x) -> 0.25*log(x) + 0.49088
```

Two things fall out that are directly actionable **without needing a proven edge**:

- The drawdown scale is proportional to **variance over edge** (σ²/μ).
- **Doubling the stake exactly doubles the expected maximum drawdown.**

That last line is the honest version of what the founder asked for. It gives a principled
way to choose the flat stake from a stated drawdown tolerance — *"I am willing to see the
bank fall by at most X over N bets"* solves directly for the stake — with no assumption that
the edge is positive. It is bankroll management that survives the edge being zero.

---

## NEGATIVE FINDING: most of what was asked came back empty

Of the five research angles requested, **only angles 1 (Kelly variants) and 2 (ruin and
drawdown mathematics) produced anything that survived verification.**

Nothing survived on:
- **Angle 3** — what professional syndicates actually do: bankroll fractions, stop-losses,
  scaling rules, CLV as a leading indicator, line shopping, why martingale/Fibonacci/
  d'Alembert fail.
- **Angle 4 beyond Kelly** — volatility targeting, risk parity, correlation limits,
  anytime-valid monitoring for edge decay.
- **Angle 5** — what actually kills small-edge operations: execution costs, account
  restriction, model decay, variance-driven abandonment.

All fifteen surviving claims trace to seven papers, every one a Kelly-sizing or
drawdown-mathematics source. The stated reason: the practitioner-facing material in this
space is dominated by gambling-affiliate content, which the brief instructed the agents to
distrust — and once that is excluded, **there is very little verifiable evidence left.**

This matters more than it looks. The founder's central question — *what do the best systems
out there actually do, and what should we add to be the complete package?* — **could not be
answered to this evidential standard from public sources.** That is a finding about the
field, not a failure to look. Anyone claiming to know what syndicates do is, on this
evidence, mostly repeating marketing.

---

## What changes

Nothing in the code. `allocator.py` ships with `kelly_fraction = 0`, which reproduces the
flat rule, and on this evidence it should stay there. The module's invented caps (2% single,
5% daily, 20% reserve, 80% brake) remain unsourced and should be replaced by the
drawdown-closed-form sizing above if the module is ever activated.

## Ledger

No SPEC-ID changes. No gate evaluated. No spend authorised. SPEC-060 and SPEC-061 stand,
now with a citation trail behind them rather than an assumption.
