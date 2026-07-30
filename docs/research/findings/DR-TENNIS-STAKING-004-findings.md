# DR-TENNIS-STAKING-004 — full Kelly on £100 is £1.96. The chip is £2.

**Status:** ASSESSED. **Date:** 2026-07-30. Full derivation:
`DR-TENNIS-STAKING-004-RAW-report.md`. 17 agents, 2.41M tokens, 595 tool calls.

**166 claims extracted, 10 reached verification, and ZERO survived.** Every candidate
algorithm was refuted. The rule below therefore rests on the brief, this repository's own
governing specs, and arithmetic performed for the answer — each tagged in the raw report.
Ruin figures are **exact absorbing-lattice dynamic programming over integer pence**, not
simulation.

## The number that ends the argument

Translate the measured +0.001 nats into a probability displacement via `KL(q+δ‖q) = 0.001`:
δ = 2.236 pp at q = 0.50. Net of 5% commission at O = 2.00 that is an edge of 0.954 pp and
an ROI of +1.86%. Full Kelly is `EV/b`:

| | stake on £100 | bank where it first reaches £2 |
|---|---|---|
| **full Kelly** | **£1.96** | £102.17 |
| half Kelly | £0.98 | £204.34 |
| quarter Kelly | £0.49 | £408.69 |

**On the most generous reading of the evidence, full Kelly is smaller than the smallest
chip you can buy.** Kelly's own answer on a £100 bank is *don't bet — you have no small
enough stake*. Every fractional variant is smaller still.

And the flat £2 you *can* place is **102% of full Kelly** at O = 2.00 — a 2% overbet — rising
to **162% of full Kelly at O = 5.00**. The flat minimum is not a placeholder standing in for
a real rule. It is already slightly more than Kelly recommends.

## A staking plan is arithmetically identical to flat staking here

| rule | stakes exactly £2 for bank in | refuses below |
|---|---|---|
| full Kelly | **[£102.17, £153.26)** | £102.17 |
| half Kelly | [£204.34, £306.52) | £204.34 |
| quarter Kelly | [£408.69, £613.03) | £408.69 |

Inside £102.17–£153.26, **full Kelly and flat £2 are the same rule** — identical stake, every
bet. Reaching £153.26 takes 1,432 bets by drift or 747 by noise; the variance budget stops
the programme at 141. So across this bank's entire life a staking plan either never differs
from flat staking or never bets at all.

Verified by simulation: 400,000 paths × 730 bets, full-Kelly and half-Kelly **rounded down
placed zero bets in 100% of runs**.

**The staking-rule question is empty at £100.** The questions that are not empty are: when to
refuse, when to stop, and where the floor sits.

## Every candidate refuted, including the one I recommended

- **Busseti/Ryu/Boyd risk-constrained Kelly** — which DR-TENNIS-STAKING-002 recommended.
  Its two-outcome bisection recipe does not work: `g(0) = 1` exactly and `g` is convex, so
  f = 0 is always a root. At λ = 6.46 the feasible set on a £100 bank at zero edge **contains
  no executable stake at all**.
- **Baker & McHale shrinkage** — the authors' own 2016 follow-up tested it on 31,530 ATP
  matches and found *"any shrinkage only decreased expected utility"*. Its σ² is sampling
  variance, decaying like 1/n, so λ → 1 exactly when you have data but no established edge.
- **Chu/Wu/Swartz f₀** — needs a strike-rate count at one fixed price; no channel for a
  per-match probability at a per-match price. The authors call that case a "stumbling block".
- **Metel chance-constrained** — needs a multinomial-logit coefficient vector; DP1 is
  Glicko-2 and has no such object. Two of its three tested α values lose to not betting.

## What £100 actually buys, in evidence

| O | capacity | E[profit] | SD | **t** |
|---|---|---|---|---|
| 1.30 | 470 bets | £11.69 | £22.78 | **0.513** |
| 2.00 | 141 bets | £5.24 | £23.13 | 0.227 |
| 3.00 | 70 bets | £3.94 | £23.21 | 0.170 |

You need t = 1.96. **You cannot buy a statistically meaningful P&L result with £100 — at any
staking rule, at any price, ever.** That needs a bank of £369 (O = 1.30), £823 (O = 2.00) or
£1,089 (O = 3.00), and that is for one pre-registered test before SPEC-091 multiplicity.

Sharpest single line: **assuming the edge is real, the median outcome of a full 42-bet
tranche is a bank of £99.90 — down ten pence.** Expected gain £1.56 against SD £12.86;
signal-to-noise 0.12.

## The rule it derives instead: FUFV-1

Flat £2, with a hard floor and a **variance budget**. Output domain is
`{REFUSE(reason)} ∪ {£2}` — no third stake, so no rounding step and no rounding bias.

- **P(wipe-out) = 0 by construction.** The floor guard refuses whenever `B − u < F`, so from
  any bettable state one loss lands at ≥ £60. Structural, not probabilistic — it holds under
  any sequence of outcomes including the model being catastrophically wrong.
- **The variance budget is derived from one stated judgement**, τ, the tolerable probability
  of stopping at the floor — not borrowed (SPEC-094). V₀ = 134 units² by exact DP. At
  O = 2.00 that is a capacity of **141 bets**, with floor-hit probability 6.2% if the edge is
  real and 9.3% if it is exactly zero.
- Without the cap, a year at 2 bets/day hits the floor with probability **0.46 even at
  exactly zero EV**, and an edgeless three-year run destroys an unfloored bank with
  probability **0.83**.
- Same-day bets are charged as **perfectly correlated** (`(2σ)² − σ² = 3σ²`, four times the
  first), because within-day ρ is unmeasured and SPEC-090 forbids independence assumptions.
  That throttles clustering without any invented "max bets per day" constant.
- σ is evaluated at `p_be`, **not** at the model's probability, so variance control never
  depends on the unverified edge. No edge estimate enters the stake — only the refusal test.

## What this means

The bank, not the algorithm, is the binding constraint. Below roughly **£400** no allocation
rule can express itself; below roughly **£800** no P&L test can resolve anything. The honest
sequence is: keep flat stakes, use the floor and variance budget to bound the damage, and
judge the edge on CLV rather than P&L — because at this size P&L cannot answer.

## Ledger

No SPEC-ID changes. No gate evaluated. SPEC-060/061 stand, now with derived arithmetic
behind them. `allocator.py` remains inert at `kelly_fraction = 0`; its invented caps are
superseded by this and should not be activated.
