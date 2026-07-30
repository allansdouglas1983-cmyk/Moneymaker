# TE-0046 — the staking head-to-head: the pre-declared null, delivered with its matrix

**Date:** 2026-07-30. **Type:** pre-registered empirical study (STK-HARNESS-V1; config
frozen and committed before the run, sha256 `9e191702f925…`). **Ledger:** the current
policy's fired set — 9,793 SUPPORTED-fill bets over 2,763 days (2015–2026), model source,
min_edge 0.02, commission 0.02, ledger sha256 `fd0e1d18c6e0ef54…`. **Raw output:**
`tennis-edge/docs/evidence/staking/stk-harness-v1/` (full matrix + per-draw finals).
Measured per-unit mean of the ledger: **+4.11%**. 12 arms × 4 scenarios × 1,000 paired
stationary-bootstrap draws over whole UTC days.

## The verdict, per the frozen selection rule

**No arm passes the admissibility gates. The incumbent — flat £1 — is retained**, per
§6.6 of the protocol, which declared this outcome in advance so it could not be respun.

The gates failed in two opposite, equally instructive ways:

1. **Every growing rule breaches the founder floor under the zero-edge scenario** (G1
   demands ≤ 5%): flat £1 hits the £70 floor in 86.7% of zero-edge draws; flat £2 in
   91.3%; proportional 5% in 100%. This is TE-0036's closed form arriving on schedule —
   expected max drawdown at zero edge is ~30.7 units per 600 bets, and this ledger is
   9,793 bets long. **A £30 loss budget cannot fund an eleven-year exposure at any
   staking rule.** The gate result is about the budget-to-horizon ratio, not about any
   rule's cleverness.
2. **Every rule that protects the floor switches itself off** (G3 demands silent-death
   ≤ 10%): CPPI m=0.05 goes silent in 92–100% of draws, TIPP in 100%, the HB-cap
   variant in 73–82%. On a £100 bank the cushion above a £70 floor is £30; a 5%
   multiplier stakes £1.50, and the first modest dip takes the demand under the £1
   exchange minimum — permanently, for the ratcheting rules. The matrix predicted this
   ("bank-size infeasibility is pervasive"); it is now measured.

The floor rules did exactly what their mathematics promises — **P(floor breach) = 0.000
across all four scenarios, including sign-reversed edge** — the almost-sure guarantee
demonstrated on 48,000 replayed histories. They kept the £30 by not betting. That is the
whole trade at this bank size, stated by the data.

## What the matrix says when the edge is as measured

| arm | median final (£) | q05 (£) | P(floor) | P(silent) |
|---|---|---|---|---|
| flat £1 (incumbent) | **456** | 68 | 0.203 | 0 |
| flat £2 | 682 | 65 | 0.407 | 0 |
| sqrt-profit | **981** | 68 | 0.266 | 0 |
| fixed-profit-net | 362 | 67 | 0.252 | 0 |
| variance ladder | 237 | 68 | 0.196 | 0 |
| proportional 2% | 70 | 66 | 0.520 | 0 |
| TIPP 0.8 | 99 | 96 | **0.000** | 1.00 |
| CPPI m=0.05 | 89 | 86 | **0.000** | 0.92 |
| all-in control | 0 | 0 | 1.000 | 0 |

Three structural readings, none of which required the edge to be proven:

- **The proportional family is dominated at this bank size.** PROP_2% ends near break-even
  in median *even at the measured +4.1% edge* — the £2 stakes it wants are consumed by
  the same drawdowns as flat £2, but its compounding never gets started before the floor
  interrupts it. The multiplicative advantage needs room the bank does not have.
- **sqrt-profit is the quiet standout shape**: escalation funded only from banked profit
  gives the highest median (£981) at a floor risk (26.6%) close to flat £1's, and it
  collapses to exactly flat when there is no profit — so it costs nothing when wrong.
  NOT adopted (it passed no gate; nothing did); recorded as the leading candidate for a
  re-run under a horizon-scoped budget.
- **The all-in control died with probability 1 in every scenario** — the harness's
  pathology detector working, and a bound on what any result here can be worth.

## What this decides, and what it defers

**Decided:** flat £1 stands, now backed by 48,000 replayed histories rather than by
default. The floor-rule guarantees are real but inexpressible at £100/£70/£1; anyone
proposing CPPI-style protection on this bank is proposing not betting.

**Deferred, with the reason recorded:** the gates were evaluated over the full
eleven-year ledger horizon because that is the sequence that exists. A live trial is
40–60 bets a month, not 9,793 — over a 1,000-bet horizon the same G1 numbers would be
far lower. Re-running this frozen harness on horizon-sliced ledgers (the seed and config
permit it without re-picking anything) is the registered follow-up, and the bank-size
arithmetic it will produce — "to run rule R for a year at zero edge with ≤5% floor risk
you need £X" — is the study's practical payoff for funding decisions.

## Ledger

No SPEC-ID changes. SPEC-060/061 stand, now empirically supported. No staking rule
adopted or changed; no stake authorised. The §6.3 winner analysis was not reached (no
admissible arm), exactly as the pre-registration anticipated in §7.

## Addendum 2026-07-30 — the budget arithmetic, corrected twice by founder challenge

Two founder challenges corrected this document's framing, and both were right:

**"Where did the £30 budget come from?"** — from the protocol synthesis's default
proposal, adopted as a frozen STUDY parameter. The founder never set it. It was labelled
an input throughout, but a session summary called it "your £30 budget", which it never
was. The real loss budget is whatever the founder sets in the app, and none is set yet.

**"Earnings stay in the bank — is that considered?"** — it was not, properly. The
original gate arithmetic used peak-to-trough drawdown, which counts a dip from £150 to
£80 as a £70 event even though the bank never went below its starting £100. With
winnings retained, the funding statistic is the DEEPEST DIP BELOW STARTING MONEY.
Recomputed at the realised cadence (~890 bets/yr, 1,000 resampled histories per cell;
raw output `tennis-edge/docs/evidence/staking/stk-harness-v1/dip-below-start-by-horizon.txt`):

| flat £1 | zero edge p95/p99 | measured edge p95/p99 | median P&L (measured) |
|---|---|---|---|
| 1 year | £72 / £93 | £46 / £64 | +£34 |
| 2 years | £101 / £133 | £54 / £77 | +£69 |
| 5 years | £171 / £220 | **£56 / £88** | +£169 |

(£2 stakes: double every figure; median P&L +£71/yr.)

**The finding the correction exposed:** at the measured edge the dip-below-start
SATURATES — £46 → £54 → £56 across one to five years — because retained winnings absorb
later drawdowns. The risk of touching one's own starting money is front-loaded in year
one; if the edge is real, surviving the first year buys nearly all the safety thereafter.
At zero edge nothing accumulates and the dip grows without bound (√time). The two
columns together are the funding decision: the zero-edge column is the burn rate of
finding out; the measured column is what happens if the record is right.

Practical reading at the current firing rule: a £100 bank at £1 flat, with the whole
bank as the stop, carries ~7% zero-edge annual exhaustion risk and ~1% annual risk of
ever being £64 down at the measured edge. £2 stakes want a £200 bank for the same
safety. No number in this addendum is a recommendation; the budget is the founder's to
set, now with both columns visible.
