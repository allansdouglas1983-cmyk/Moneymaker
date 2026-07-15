---
paths:
  - "l3_features/**"
  - "l4_pricing/**"
  - "l8_evidence/**"
---
# Evidence integrity rules

You are editing code that determines whether conclusions are valid.

## The race is the unit of analysis
Runners in a race are one mutually exclusive choice set. Races at a meeting share
going, weather, jockeys, liquidity, participants. Runner-level independence is wrong
and produces standard errors that are far too small.

- Paired race-level log score: `d_r = L_r(market) - L_r(combined)`
- Block bootstrap clustered by meeting-day
- Sample size DERIVED: `N ~ (z_a + z_b)^2 * sigma_d^2 / delta^2`

## No borrowed thresholds
These are explicitly rejected as gates: `dR2 >= 0.01`, `t >= 3`, `ECE <= 0.02`,
"2,000 bets". Every experiment declares its own minimum economically meaningful
effect, power assumption, primary endpoint, and stopping rule BEFORE observation.

## Leakage
- Reconciled BSP: grading only, never a feature
- Actual-off time: post-hoc only. Live knows scheduled start.
- Backfill does not confer historical validity. Declare true publication time.
- Cross-fitting must be time-respecting AND strictly out-of-fold, or alpha is
  spuriously inflated and the whole result is worthless.

## CLV is a diagnostic family, not a training target
Signal CLV / intended-order CLV / realised-fill CLV / execution-policy value.
Realised-fill CLV does not exist for unfilled orders — never assign hypothetical
taken prices.

## The universe is frozen before outcomes are known
Every eligible market accounted for. Missing data -> explicit exclusion with a
knowledge-time, never a disappearance. Exclusions rest on facts knowable at decision time.
Every lockbox report includes the full exclusion funnel. No-bet races stay in policy
evaluation.

Sporting result != contractual settlement. The model learns from the sporting result;
P&L is measured from Betfair's settlement.

## Gates have FOUR outcomes
PASS | CONTINUE | FAIL_HARM | FAIL_FUTILITY. Never a boolean. "Not passed" is not
"disproved" — early lower bounds sit below zero even when the true value is positive.

## Trial ledger
Every experiment recorded, including number_of_prior_trials. The lockbox is never
inspected during development. If you look at it, it is burned.
