## Provenance of every number below

There is no surviving external evidence for this task. The adversarial verification pass returned an **empty** permitted-evidence list, and refuted the entire Kelly-shrinkage literature that was proposed for it. So nothing here rests on a cited paper. Every figure is tagged:

- **[BRIEF]** — an input you gave (bank £100, £2 minimum, whole pounds, commission 2–5%, +0.001 nats/match, ROI CI spans zero).
- **[SPEC]** — this repository's own governing text (`docs/spec-manifest.yaml`, `CLAUDE.md`, ADR 0020).
- **[COMP]** — arithmetic I performed for this answer. Method named at the point of use; scripts in `/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/alloc/` (`core2.py`, `ruin.py`, `tranche.py`, `gran.py`, `calib.py`, `vbudget.py`, `capacity.py`, `summary.py`).

Ruin figures are **exact** absorbing-lattice dynamic programming over integer pence, not simulation. Where I use a closed form I show the DP agreeing with it.

---

# 1. THE RULE

**Name:** `FLAT-UNIT-WITH-FLOOR-AND-VARIANCE-BUDGET (FUFV-1)`

**Output domain:** `{REFUSE(reason)} ∪ {£2}`. Nothing else. There is no third stake. Consequently **there is no rounding step and no rounding bias** — the rule never computes a real-valued stake that then has to be quantised.

### 1.1 Inputs (all exact; no float ever touches money, price or probability)

| Symbol | Definition | Type |
|---|---|---|
| `B` | Bank, integer pence, taken from the **reconciled account statement**, never a local estimate [SPEC-081] | int |
| `F` | Hard floor, integer pence. Founder-set, pre-registered, immutable downward-only-by-approval [SPEC-103, ADR 0020]. **Recommended `F = 6000` (£60)** | int |
| `u` | Unit stake = `200` pence (£2.00) [BRIEF]. A frozen constant of the rule, not a function of bank, odds or edge | int |
| `L` | Experiment-loss budget remaining, integer pence. Monotone non-increasing [SPEC-060, SPEC-065]. Initial `L₀ = B₀ − F = 4000` (£40) | int |
| `V` | Variance budget remaining, exact Decimal, in units². Monotone non-increasing. **`V₀ = 134`** (derivation §1.4) | Decimal |
| `k` | Integer tick index into the canonical Betfair ladder; `O = ladder(k)` [SPEC-053]. Price is **never** a float | int |
| `c` | Commission rate on net market winnings, exact Decimal. If the account's applicable rate is not known with certainty, **use `c = 0.05`** (fail closed) [BRIEF] | Decimal |
| `p_lo` | The typed `WinProbabilityLowerBound` for the backed selection — `sigmoid(δ − 1.644854·s)` under `ANALYTIC_PROPAGATION` [SPEC-034, SPEC-106]. **Never** the central estimate | typed |
| `d` | UTC calendar date of the match — the tennis correlation-cluster key [SPEC-031, SPEC-090] | date |
| `S_d` | Σ of per-bet σ already committed on cluster `d` (including any still-unsettled position) | Decimal |
| guards | market-state validity, staleness, identity resolution, data-quality status, market version [SPEC-112, SPEC-072] | flags |

### 1.2 Derived quantities

```
b      = (O − 1) · (1 − c)                        net decimal odds after commission
p_be   = 1 / (1 + b)                              commission-aware break-even  [SPEC-110]
σ(k,c) = sqrt( p_be · (1 − p_be) ) · (b + 1)      per-bet SD in units of one stake
ΔV     = (S_d + σ)² − S_d²                        variance this bet adds to its day-cluster
```

`σ` is evaluated **at `p_be`, not at the model's probability** — the variance control must not depend on the unverified edge. `σ` is a **frozen precomputed table** indexed by `(tick_index, commission_rate)`, so no square root is taken at decision time and the rule is byte-deterministic and replayable [SPEC-010/011].

`ΔV` charges the day-cluster as if same-day bets were **perfectly correlated**. This is deliberate: `ρ` within a UTC day is unmeasured, and SPEC-090 forbids selection-level independence assumptions. Worst-case correlation is the only fail-closed choice. It is also why no arbitrary "max bets per day" constant is needed — the cost of a second bet on the same day is `(2σ)² − σ² = 3σ²`, four times the first, so the budget throttles clustering by itself.

### 1.3 The decision procedure (ordered; first match returns; no judgement calls)

```
G1  any guard false, price stale beyond the frozen staleness bound, market version
    changed since the quote, in-play or past scheduled start, identity unresolved,
    data-quality status not OK, or p_lo unavailable        → REFUSE(STATE)
G2  a position already exists in this market               → REFUSE(ONE_PER_MARKET)   [SPEC-054]
G3  B − u < F                                              → REFUSE(FLOOR)
G4  L < u                                                  → REFUSE(BUDGET_EXHAUSTED) [SPEC-060]
G5  u > min(L, B − F)                                      → REFUSE(MIN_EXCEEDS_RISK)  [SPEC-061]
G6  ΔV > V                                                 → REFUSE(VARIANCE_BUDGET)
G7  p_lo ≤ p_be                                            → REFUSE(NO_CONSERVATIVE_EDGE)
else                                                       → STAKE = u = £2 exactly
```

**On settlement** (never before):

```
V := V − ΔV                              monotone non-increasing
if outcome is a loss:  L := L − u         monotone non-increasing, gross losses only
B := reconciled statement balance         never the local hypothesis   [SPEC-081]
```

`L` and `V` may be increased **only** by an explicit, logged, human-approved top-up event [SPEC-065]. No top-up may lower `F`. If any order is in an unknown state, all placement is blocked until reconciled [SPEC-062].

### 1.4 Where the two budget constants come from (derived, not borrowed)

`SPEC-094` forbids borrowed constants as gates. Both budgets are derived from **one** founder judgement — the tolerable probability of the programme ending at the floor — and nothing else.

- Drawdown tolerance in units: `D = (B₀ − F)/u = (10000 − 6000)/200 = 20 units`.
- For a flat-stake walk, `P(max drawdown ≥ D within N bets) ≈ 2·Φ(−D/(σ√N))` (reflection principle). Setting that to a tolerance `τ` gives a **price-independent variance budget** `V = (D/z_τ)²` where `z_τ = Φ⁻¹(1 − τ/2)`.
- At `τ = 0.10`: `V = (20/1.644854)² = 147.8` units². **[COMP]**
- I did not trust the approximation. I bisected the **exact** DP for the largest `N` satisfying `P(hit £60) ≤ 0.10` at zero edge, at every price, and took the minimum implied `V`: **[COMP, `calib.py`]**

| O | σ² (units²) | exact N_max at τ=0.10 | implied V |
|---|---|---|---|
| 1.30 | 0.2850 | 471 | 134.24 |
| 1.50 | 0.4750 | 285 | 135.38 |
| 2.00 | 0.9500 | 145 | 137.75 |
| 3.00 | 1.9000 | 77 | 146.30 |
| 5.00 | 3.8000 | 43 | 163.40 |

**`V₀ = 134`** (the minimum, floored) is conservative at every price. Verified: with `V = 134` the realised floor-hit probability at zero edge is 0.072–0.100 across O ∈ [1.30, 5.00], and 0.039–0.065 if the edge is real. **[COMP, `calib.py`]** The only free parameter in the whole rule is `τ`, and it is stated, not hidden.

**Consequence, stated plainly:** at O = 2.00 the £100 bank has capacity for **141 bets** at one per day, or **35 days ≈ 70 bets** at two per day (because the second same-day bet costs 4× the first). Then `G6` refuses permanently until a human approves more budget. This is the honest capacity of £100 with a £2 chip.

### 1.5 Safety conditions of the rule itself

The rule is void — do not run it — if any of these fail:

1. `p_lo` is not genuinely out-of-fold and leakage-free [SPEC-031, SPEC-107]. A contaminated lower bound makes `G7` a rubber stamp.
2. Bets are not settled sequentially with `B` refreshed from the statement before the next decision. The floor arithmetic assumes it. Concurrent unsettled positions must be charged to the same cluster in `ΔV`.
3. The applicable commission rate is misstated. `p_be` moves 1.28 pp between `c = 2%` and `c = 5%` at O = 2.00 — larger than the entire measured edge. **[COMP, `core.py`]**
4. The exchange minimum changes from £2, or the whole-pound constraint changes. `D`, `V` and the σ table must be recalibrated.
5. **Any of SPEC-108, SPEC-109, SPEC-110, SPEC-111, SPEC-112 is still `planned`.** As of 2026-07-30 all five are. `SPEC-109` makes `BET_CANDIDATE` *structurally* unreachable until gates P1, P2 and T1 pass and the founder activates T2. **Nothing in this repository may place, cancel or amend an order** [CLAUDE.md]. This rule is a specification of what would be permitted; in the interim the only lawful instantiation is the founder-manual, flat-stake, pre-set-loss-budget protocol of ADR 0020 — which is what this rule formalises.

---

# 2. WHY THIS ONE, AGAINST THE ALTERNATIVES

**No alternative survived.** The verification pass returned an empty permitted-evidence set. All seven candidate rules were refuted. I name them as refuted and build on none of them:

| Refuted candidate | Why it is unusable here |
|---|---|
| **Baker & McHale shrinkage** — `λ = δ²/(δ² + σ_δ²) = t²/(t²+1)` | REFUTED. The 2016 paper is itself the walk-back: the authors tested it on 31,530 ATP matches and found "any shrinkage only decreased expected utility"; their conclusion rejects routine use in favour of using λ as a model-adequacy diagnostic. Its σ² is *sampling* variance, which decays like 1/n — so λ → 1 exactly when you have data but no established edge. It has no refusal branch. And on this lattice the whole continuous range λ ∈ (0,1] maps onto at most five executable stakes, two at a £60 bank. |
| **The λ t-schedule (λ(1) = 0.5 = "half-Kelly")** | REFUTED with the parent. Also arithmetically wrong at the stated boundary (λ(1.96) = 0.7935, not "< 0.79"). |
| **Chu/Wu/Swartz `f₀`** — Kelly at the Beta posterior mean | REFUTED. Its inputs are `(x, n, a, b, θ)` — a strike-rate count at **one fixed price**. There is no channel for a per-match probability with per-match uncertainty at a per-match price; the authors' own Discussion calls that case a "stumbling block" and offers only "perhaps x = n = 0 is convenient". Its refusal branch fires at a **54% posterior chance the edge exists at all**. No commission. |
| **`f₀` "derives half-Kelly"** | REFUTED. The f₀/Kelly ratio across the paper's own five examples spans 0.08–0.72 and → 1 as n → ∞. Adding 5% commission to their headline example moves it from 0.54 to 0.25. |
| **The sceptical-prior collapse to 7.5% of Kelly** | REFUTED. That is a prior-sensitivity row promoted to a recommendation, and it is a knife edge: tightening the prior from Beta(100,100) to Beta(120,120) sends it to exactly zero. |
| **Metel lower-bound / chance-constrained Kelly** | REFUTED. Requires a multinomial-logit coefficient vector and sandwich covariance; DP1 is Glicko-2 [SPEC-105] and has no such object. For a back-only single selection the residual-outcome apparatus is a mathematical no-op. Its own Table 2 shows two of three tested α values **lose to not betting**. |
| **Busseti/Ryu/Boyd drawdown-constrained Kelly** | REFUTED. Its stated two-outcome bisection recipe **does not work** — `g(0) = 1` exactly and `g` is convex, so f = 0 is always a root and naive bisection returns zero or fails to bracket. The proof needs IID repeated bets at a *constant fraction* with a *known* distribution. Boyd's own later work concedes the known-distribution assumption. At λ = 6.46 the feasible set on a £100 bank at zero edge **contains no executable stake at all**. |

So the rule had to be derived from first principles. It is:

**(a) The only rule the lattice can express.** At the most generous defensible reading of the measured edge (§3), full Kelly on £100 at O = 2.00 is **£1.96** — *below the £2 minimum*. **[COMP, `core2.py`]** A rounding-down Kelly rule therefore stakes £0, the bank never moves, and it stakes £0 forever. I ran it: over 730 bets, full-Kelly-rounded-down and half-Kelly-rounded-down each placed **zero bets in 100% of 400,000 paths**, final bank £100.00 at every percentile. **[COMP, `gran.py`]** The executable choice is literally: flat £2, or never bet.

**(b) It is the platform's own active governance.** SPEC-060: "v1 stake is a fixed minimum. NOT Kelly, NOT fractional Kelly. An absolute experiment-loss budget… decrements on every settled loss." ADR 0020: real-stake activity is "founder-manual only, flat-stake, behind a hard pre-set loss budget." FUFV-1 is the arithmetic instantiation of text that is already binding.

**(c) It reframes the bet correctly.** Under this rule the stake is not an investment sized to an edge; it is a **fixed-cost measurement** of execution reality — the thing shadow mode structurally cannot produce, because paper trading routes to simulated execution, not Betfair's matching engine [CLAUDE.md]. Its size is set by the measurement budget, not by a probability. That is why no edge estimate appears anywhere in the stake computation, only in the *refusal* test.

**(d) `G7` uses the conservative lower bound with a margin of exactly zero.** The conservatism lives entirely in `p_lo` being the 1.645-σ lower bound [SPEC-106], not in an added threshold. Adding a further "minimum edge" constant would be precisely the borrowed constant SPEC-094 prohibits, and there is no evidence from which to derive one.

---

# 3. THE FRACTION

**Zero. There is no Kelly component. Bet a flat minimum, or nothing.**

That is not a hedge; it is forced by arithmetic. Here is the whole chain. **[COMP, `core2.py`]**

**Step 1 — translate the log-score gain.** For a binary market where the market's probability is `q` and the model is displaced to `p = q + δ` and is *correct*, the expected per-match log-score gain is exactly `KL(p‖q)`. Solving `KL(q+δ‖q) = 0.001` numerically:

| market q | δ | model p |
|---|---|---|
| 0.30 | 1.866 pp | 0.7879 (backing the dog side) |
| 0.50 | **2.236 pp** | 0.5224 |
| 0.70 | 2.036 pp | 0.7204 |

Small-δ check: `KL ≈ 2δ²` ⟹ `δ = √0.0005 = 0.02236`. ✓

**This translation is generous in four separate ways**, and I flag all four: it assumes (i) the *entire* average log-score gain converts to a same-direction displacement at the price you actually back, (ii) zero overround — that the fair probability equals `1/O` at the *back* price, (iii) no adverse selection, i.e. the matches where you disagree most with the market are not the matches where the market knows something you don't, (iv) no slippage between quote and execution. Every one of these can only make the real edge smaller.

**Step 2 — net it against commission.** `p_be = 1/(1 + (O−1)(1−c))`. At O = 2.00, c = 5%: `p_be = 0.512821`. Model `p = 0.522357`. Net edge = **0.954 pp**. EV per unit stake = `p·b − (1−p) = 0.522357 × 0.95 − 0.477643 = +0.018596` → **ROI +1.86%**. Consistent with a CI that spans zero [BRIEF].

**Step 3 — full Kelly.** `f* = EV/b = 0.018596/0.95 = 1.9575%` of bank = **£1.96 on £100.**

| | stake on £100 | bank at which it reaches £2 |
|---|---|---|
| full Kelly | £1.96 | £102.17 |
| half Kelly | £0.98 | £204.34 |
| quarter Kelly | £0.49 | £408.69 |

**Full Kelly, on the most generous reading of the evidence, is smaller than the smallest chip you can buy.** Kelly's own answer on this bank is *don't bet, you have no small enough stake*. Every fractional variant is smaller still. Meanwhile the flat £2 you *can* place is **102% of full Kelly** — a 2% overbet at O = 2.00, and a much larger one at longer prices (at O = 5.00 full Kelly is £1.23, so £2 is 162% of full Kelly). **[COMP]**

So the defensible multiplier on full Kelly is not 0.5, or 0.25, or `t²/(t²+1)`. The fractional-Kelly question **does not have an executable answer at this bank size**, and any number offered for it would be decoration. The honest rule is: one chip or none, and the entire remaining design effort goes into the *refusal* conditions and the *stopping* conditions, which is where FUFV-1 puts it.

The correct trigger for revisiting this is **not** bank growth. It is: an edge established at a gate (§7), *and* a bank at which a fraction is expressible (≈ £200 for half-Kelly at even money, ≈ £400 for quarter-Kelly). Raising the unit because the bank grew, with the edge still unestablished, converts a bounded experiment into an unbounded one and must be refused.

---

# 4. RUIN

Three regimes throughout, all at c = 5%. **[COMP, `core.py`, `ruin.py`]**

| Regime | Description | p | win | loss | ROI |
|---|---|---|---|---|---|
| **A** | Measured edge real (generous translation, §3), back at O = 2.00 | 0.522357 | +£1.90 | −£2.00 | **+1.86%** |
| **B** | EV exactly zero (edge exactly cancels commission) | 0.512821 | +£1.90 | −£2.00 | **0.00%** |
| **C** | No edge at all; fair price 2.00, you cross two ticks to back at 1.98 | 0.500000 | +£1.86 | −£2.00 | **−3.45%** |

For calibration: with **no** edge and paying **no** spread, commission alone gives −2.50%; one tick of spread gives −2.98%; two ticks −3.45%. Regime C is the default expectation under `CLAUDE.md` ("Most likely there is no exploitable edge").

### 4.1 Wipe-out risk: exactly zero, by construction

`G3` refuses whenever `B − u < F`. From any bettable state `B ≥ F + u = £62`, one losing bet lands at `≥ £60`. So **the bank can never go below £60. P(wipe-out) = 0** — not small, not bounded, zero. That is a structural property of the guard, not a probabilistic claim, and it holds under *any* sequence of outcomes, including the model being catastrophically wrong. It is the single most important line in the rule.

The meaningful question is therefore **P(the programme stops at the floor)**, i.e. P(the bank ever reaches £60–£61 and the rule refuses forever). Computed by exact absorbing-lattice DP in integer pence (win +190p / loss −200p on a gcd-10 lattice, absorbing below 620 units):

**P(programme stops at the £60 floor), flat £2, B₀ = £100, O = 2.00**

| bets N | A: edge real | B: edge zero | C: no edge, −3.45% |
|---|---|---|---|
| 42 | 0.0012 | 0.0018 | 0.0029 |
| 100 | 0.0306 | 0.0455 | — |
| 141 (**FUFV-1 capacity**) | **0.062** | **0.093** | ~0.19 |
| 200 | 0.1053 | 0.1578 | 0.2949 |
| 730 (1 yr at 2/day) | 0.2967 | 0.4598 | 0.7745 |
| 2190 (3 yr) | 0.4102 | 0.6694 | 0.9692 |

The closed form matches the DP almost exactly — `2Φ(−D/√N)` with D = 20 units gives 0.0455 (N=100), 0.1573 (N=200), 0.4592 (N=730) against DP values 0.0455, 0.1578, 0.4598. **[COMP, `capacity.py`]** So you can reason about this in your head: *a £40 drawdown allowance is 20 units, and a driftless walk of N bets wanders about √N units, so the floor is likely once N exceeds ~400.*

**This is why `G6` exists.** Uncapped, a year of betting hits the floor with probability 0.46 even when EV is exactly zero. Capped at V = 134 (141 bets at O = 2.00), the floor-hit probability is **6.2% if the edge is real and 9.3% if it is exactly zero** — the tolerance you asked for, delivered.

### 4.2 What happens without the floor

If `G3` is removed and you bet until you cannot afford £2:

| | N = 200 | N = 730 | N = 2190 |
|---|---|---|---|
| A: edge real | 0.00012 | 0.0209 | 0.0850 |
| B: edge zero | 0.00031 | 0.0606 | **0.2780** |
| C: no edge | 0.00167 | 0.2622 | **0.8343** |

5th-percentile bank at N = 730: £40.10 (A), £1.70 (B), £0.46 (C). **[COMP, `ruin.py`]** Without the floor, a genuinely edgeless three-year programme destroys the bank with probability 0.83. The floor is not a nicety.

### 4.3 The loss-budget tranche, exactly

`L₀ = £40 = 20 losing bets`. Since the stake is flat, the tranche ends at the 20th loss and the number of wins before it is Negative-Binomial(20, p) — closed form, no simulation. **[COMP, `tranche.py`]**

| Regime | E[bets in tranche] | E[bank at tranche end] | SD | P(down) | P(floor within tranche) |
|---|---|---|---|---|---|
| A | 41.9 | **£101.56** | £12.86 | 0.509 | 3.8 × 10⁻⁷ |
| B | 41.1 | £100.00 | £12.49 | 0.558 | 5.7 × 10⁻⁷ |
| C | 40.0 | £97.20 | £11.76 | 0.622 | 9.5 × 10⁻⁷ |

Regime A quantiles at tranche end: 5% £82.80, 25% £92.30, **50% £99.90**, 75% £109.40, 95% £124.60.

Read that median. **Under the generous reading of a real edge, the median outcome of a full 42-bet tranche is a bank of £99.90 — you are down ten pence.** The expected gain is £1.56 against a standard deviation of £12.86: a signal-to-noise ratio of 0.12.

### 4.4 What the whole £100 bank buys, in evidence

Expected profit and the P&L t-statistic at the capacity limit `N_max = ⌊V/σ²⌋`, regime A: **[COMP, `summary.py`]**

| O | N_max | E[profit] | SD[profit] | **t** |
|---|---|---|---|---|
| 1.30 | 470 | £11.69 | £22.78 | **0.513** |
| 2.00 | 141 | £5.24 | £23.13 | 0.227 |
| 3.00 | 70 | £3.94 | £23.21 | 0.170 |
| 5.00 | 35 | £3.28 | £23.45 | 0.140 |

The SD column is flat by design — that is exactly what a variance budget does. The best P&L t-statistic reachable from a £100 bank under a 40% drawdown tolerance is **0.51**, at the shortest prices. You need 1.96. **You cannot buy a statistically meaningful P&L result with £100, at any staking rule, at any price, ever.** To get t = 1.96 on the same 40%-drawdown terms you would need a bank of **£369** (O = 1.30), **£823** (O = 2.00), or **£1,089** (O = 3.00) — and that is for a *single* pre-registered test, before the multiplicity accounting SPEC-091 requires.

---

# 5. THE GRANULARITY PROBLEM

### 5.1 The £2 floor is the entire problem; whole-pound rounding is nearly irrelevant

On a £100 bank the executable stake set is `{0} ∪ {£2, £3, £4, …}` — 2% steps with a hard 2% floor. If Betfair allowed penny stakes *above* £2, the set would be `{0} ∪ [£2, ∞)` and every number in §3 would be unchanged, because every fraction we care about lies **below** £2. The binding constraint is the floor, not the quantisation.

The floor also **ratchets against you in drawdown**: one chip is 2.00% of bank at £100, 3.33% at £60, 5.00% at £40, 10% at £20. The forced minimum stake grows as a fraction of capital precisely when preservation matters most. This is the mechanism that makes uncapped flat staking end at the floor with probability 0.46 at zero edge (§4.2), and the reason `G3` sets an absolute floor rather than trusting proportionality.

### 5.2 When does the rule round? Never. When does it skip?

FUFV-1 never rounds — its output set has two elements. It skips on `G1`–`G7`. In practice, at the measured edge, `G7` is the one that fires most: `p_lo ≤ p_be` requires the *1.645-σ lower bound* to clear the commission-adjusted break-even, which a Glicko-2-derived distribution with realistic rating deviations will rarely do.

The alternative — a fractional rule that rounds — has two options and both fail:
- **Round down.** Recommended stake £1.96 → £1 → below minimum → £0. The bank never moves, so it never escapes. Verified: 400,000 paths × 730 bets, full-Kelly and half-Kelly rounded down each placed **zero bets in 100% of runs**. **[COMP, `gran.py`]**
- **Round up to £2.** A 2% overbet of full Kelly at O = 2.00 (162% at O = 5.00) — and the resulting rule is *literally identical to flat £2* over the bank range where it operates.

### 5.3 Is a staking plan even distinguishable from flat staking here? No.

Deterministic band arithmetic, O = 2.00, c = 5%: **[COMP, `gran.py`]**

| rule | fraction | stakes exactly £2 for bank in | refuses below | first reaches £3 at |
|---|---|---|---|---|
| full Kelly | 1.9575% | **[£102.17, £153.26)** | £102.17 | £153.26 |
| half Kelly | 0.9787% | [£204.34, £306.52) | £204.34 | £306.52 |
| quarter Kelly | 0.4894% | [£408.69, £613.03) | £408.69 | £613.03 |

Inside `[£102.17, £153.26)` **full Kelly and flat £2 are the same rule** — identical stake, every bet. Below £102.17 Kelly refuses (a refusal driven entirely by an unverified point estimate, which is why FUFV-1 does not adopt it). Half- and quarter-Kelly do not become expressible at all until the bank is roughly 2× and 4× its current size.

**Number of bets needed before the two rules can differ even once** (regime A, O = 2.00, drift +£0.03719/bet, SD £1.948/bet): **[COMP]**

- by drift alone, £100 → £153.26: **1,432 bets** ≈ 2.0 years at 2/day
- by random-walk noise reaching ±£53.26: **747 bets** ≈ 1.0 year at 2/day

And FUFV-1's own variance budget stops the programme at **141 bets** long before either. So over the entire life of this bank, **a staking plan is not merely indistinguishable from flat staking — it is arithmetically identical to it, or it never bets at all.** The staking-rule question is empty at £100. The questions that are not empty are: when to refuse, when to stop, and where the floor is.

---

# 6. WHAT IT CANNOT DO

**No staking rule creates an edge.** Stake sizing is a monotone transformation of a wager whose sign is fixed by `p` and `O`. Every bet placed at negative EV has negative expected log-growth and negative expected wealth simultaneously; no fraction, shrinkage factor, chance constraint or drawdown bound changes that sign. Sizing controls *how fast* you find out, never *what* you find out. FUFV-1 is a loss-rate governor and an evidence-generation budget. It is not, and cannot be, a source of return.

**If the edge is exactly zero (regime B):** expected profit is exactly £0 at every horizon. Median bank after 730 bets is £83.00; P(floor) 0.46; P(bank below £80) 0.49. **[COMP, `ruin.py`]** The floor caps the loss at £40 and the variance budget caps the horizon at 141 bets, so the realistic outcome is: after ~10 weeks you are somewhere in £60–£125, you have learned nothing about the edge from P&L (t ≈ 0.23), and the £40 was spent on execution evidence.

**If the edge is negative (regime C, −3.45% — the default expectation):** expected loss £0.069/bet. E[bank] after 730 bets = £72.50, median £61.42, P(floor) **0.77**. **[COMP]** With the variance budget the programme stops after ~70–141 bets with an expected loss of about £5–£10. Without the floor, P(cannot bet at all) after three years is **0.83**.

**What the rule specifically cannot deliver, against your stated objective:** "trending up safely" is *not* what this produces. Under the most generous reading of a real edge, at the capacity limit, expected profit is **£5.24 with SD £23.13** — the bank does not visibly trend at all; it random-walks with a drift you cannot see. Extrapolating past the capacity cap (which the rule forbids) a full year at 2/day yields **+£27.15 ± £52.63** if the edge is real, **£0 ± £52.63** if zero, and **−£50.37** if the model is edgeless and pays two ticks. **[COMP, `summary.py`]** The rule guarantees preservation (max loss £40, wipe-out probability exactly 0) and it guarantees the loss rate is bounded. It guarantees nothing about growth, and it must not be sold as if it did.

**The rule also cannot:** detect that its own `p_lo` is contaminated; detect adverse selection (that you bet exactly when the market knows more); compensate for a mis-stated commission rate; survive concurrent unsettled positions that are not charged to the cluster; or bound anything if the executed price differs from the quoted price it was given.

---

# 7. UNKNOWNS — what must be established before the fraction could responsibly be raised above zero

Nothing below is a finding. Each is a gap that must be closed by evidence, and the fraction stays at zero — flat £2 — until it is.

1. **The sign of the edge.** +0.001 nats/match with an ROI CI spanning zero does not identify the sign of EV, let alone its size. Required: the paired, day-clustered log-score test of SPEC-090 with a pre-registered endpoint (SPEC-094). Power: with per-match `d = log p_model(w) − log p_market(w)` having mean 0.001 and SD ≈ 2δ = 0.0447, `n = 7.8489 × 0.001998 / 10⁻⁶ = **15,682 matches** (iid)`, rising to 18,818 (ρ=0.05), 21,955 (ρ=0.10) or 28,228 (ρ=0.20) under a 5-match/day design effect. **[COMP, `tranche.py`]** At ATP+WTA tour-level volume this is a small number of years of *observation*, requiring **no money at risk** — versus 21,533 *bets* ≈ **29.5 years at 2/day** to establish the same edge from P&L. **[COMP]** Establish the edge from prediction quality; never from your own betting record.
2. **The within-UTC-day correlation ρ.** Unmeasured. `ΔV` currently assumes ρ = 1 (fail-closed), which costs you half your bet capacity at 2 bets/day. Measuring ρ properly would raise capacity — and is a prerequisite for any honest confidence interval on any of these figures (SPEC-090's block bootstrap will *increase*, not decrease, every sample size above).
3. **The realised execution cost.** The −3.45% figure assumes two ticks of concession at O = 2.00. The real distribution of (quoted price → executed price → settled net) is unmeasured, and this is the one quantity the flat-£2 programme is actually designed to measure. Historical displayed prices are not executions [CLAUDE.md]; shadow mode cannot produce fills.
4. **The true applicable commission rate,** including any market base rate variation. Currently failed closed at 5%; the 2%↔5% difference (1.28 pp of break-even at O = 2.00) exceeds the entire measured edge.
5. **Adverse selection.** Whether the matches on which the model most disagrees with the market are the matches where the model is *better* or *worse*. The +0.001 nats is an average over all matches; the bet subset is not a random subset. If disagreement correlates with model error, every number in §3 is optimistic by an unknown factor and could invert the sign.
6. **The overround at the back price.** §3 assumes `q = 1/O` with zero overround, which is generous. The true fair probability at the best back price is above `1/O_back`; the correction is unmeasured and reduces the edge.
7. **Whether δ is stable across price bands, tours and surfaces.** The translation in §3 was applied uniformly. It is not known whether the +0.001 nats concentrates in a band you can transact in or a band you cannot.
8. **The settlement-policy matrix for tennis** (retirement, walkover, partial completion). SPEC-084 refuses every tennis settlement request with `SettlementPolicyPendingError` until DR-TENNIS-SETTLEMENT-001 is verified. A rule whose settlement semantics are undefined cannot be run for real money.
9. **Gate status.** SPEC-108/109/110/111/112/113 are all `planned`. `BET_CANDIDATE` is structurally unreachable until P1, P2 and T1 pass and the founder activates T2 [SPEC-109]. Until then this rule cannot fire inside the platform at all, and the only lawful path is ADR 0020's manual protocol.
10. **The floor-hit tolerance τ = 0.10.** This is the one founder judgement in the rule. It is stated, not derived. Changing it rescales `V` as `(D/z_τ)²` and nothing else.

**When could the fraction be raised?** Only when (1), (3), (4) and (5) are closed, a gate has passed on pre-registered endpoints with the multiplicity accounting of SPEC-091, *and* the bank exceeds roughly £200 (half-Kelly expressible at even money) or £400 (quarter-Kelly). Until all of those hold simultaneously, the answer to "what multiplier on Kelly" is **zero**, and the stake is one chip.