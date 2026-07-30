# EMPIRICAL STAKING-RULE TRADE-OFF STUDY — IMPLEMENTATION SPECIFICATION (STK-HARNESS-V1)

Status: research-only. Lives under `research/`; no import path into `l5_decision/`, `l5b_risk/`, `l6_broker/` (SPEC-100 discipline applies). Nothing here places, prices, or sizes a live bet. All money in integer pence or `Decimal` with an explicit context (§8.2). No floats in any money or probability-of-money computation. No LLM produces any number consumed by the harness (Rule 3).

---

## 0. INPUT DATA CONTRACT

0.1 The input is the frozen settled-bet ledger: for each bet `i`: `market_id`, `utc_day d(i)` (UTC calendar day of settlement eligibility — the day the bet's market settled), `scheduled_start_utc`, `odds_tick_index O_i` (integer index into the canonical Betfair ladder, SPEC-053; decimal odds derived, never stored as float), `outcome y_i ∈ {0,1}`, `fill_flag ∈ {ALL_FILLS, VOLUME_SUPPORTED}`, and — for edge-consuming rules only — the archived, knowledge-time-frozen model probability `p̂_i` and archived conservative lower bound `p̂_lo,i` exactly as recorded at prediction time. No probability is recomputed, refit, or repaired inside the harness.

0.2 The ledger is hashed (`sha256` of the canonical serialisation) and the hash is recorded in every output artefact. Two runs on the same hash and same config hash MUST be byte-identical.

0.3 Commission `c ∈ {0.05, 0.02}` is a global run parameter. Every scenario × rule cell is computed at both values; `c = 0.05` is the primary reporting column (it is the account's current state).

0.4 Canonical intra-day order: bets within a UTC day are sorted by `(scheduled_start_utc, market_id)`. This order is used ONLY for deterministic stake reservation (§1.6); it never drives compounding (§1.2).

---

## 1. THE HARNESS

### 1.1 Per-rule state
Each rule instance carries, between days (never between bets within a day):

- `W` — bank, integer pence. Initial `W_0 = 10000`.
- `M` — end-of-day high-water mark of `W` (pence).
- `T` — end-of-day trough since last HWM (for throttle rules).
- `L_ledger` — cumulative settled losses (pence), monotone non-decreasing (SPEC-065 semantics; wins never restore it).
- `hist` — the end-of-day wealth series and per-day P&L series up to and including day `d−1` only (for trailing-statistic rules: DD-10, DD-11, CVAR_TARGET_SCALING, SQUARE_ROOT_STAKING's `P_t`, ES/VaR conditional multiples). Knowledge-time rule: nothing from day `d` or later is visible when sizing day `d`.
- `alive ∈ {ALIVE, DEAD_HARD, DEAD_FLOOR}` (§5).
- `params` — the rule's frozen parameter vector, set in config before the run, hashed. No parameter is ever fitted, tuned, or updated from the replay it is being scored on.

### 1.2 Same-day handling — morning-bank sizing, day-end settlement
All bets of day `d` are sized from the single settled bank `W_{d−1}` (state as of end of day `d−1`). All of day `d`'s bets then settle simultaneously; `W_d = W_{d−1} + Σ_{i∈d} π_i`.

This is the ONLY honest choice, for three reasons, and the spec forbids any intraday-compounding variant:

1. **Knowledge time.** Live, the bets are placed pre-off before any of the day's outcomes exist. A replay that lets bet 2 see bet 1's settlement grants the rule information the live operation could never have (SPEC-020 semantics transposed to staking).
2. **Ordering artefact.** The settled ledger does not carry a reliable intraday settlement order; any chosen order is arbitrary, and intraday compounding makes every path metric a function of that arbitrary choice — a nondeterminism dressed as a result.
3. **Unit of analysis.** The declared correlation cluster is the UTC day (CLAUDE.md; SPEC-090). Sizing and settling at day granularity makes the harness's compounding unit coincide with the inference unit, so the bootstrap (§3) resamples exactly the object the wealth process is built from.

### 1.3 Quantisation and the £1 floor — round DOWN, then SKIP
For every demanded stake `s_dem` (a `Decimal` in pounds):

```
s_q = floor_to_pence(s_dem)          # ROUND_DOWN to £0.01
if s_q < 100p:  SKIP the bet (stake = 0), record reason SKIP_MIN
else:           stake = s_q
```

Rounding is ALWAYS down and the sub-minimum branch is ALWAYS skip, never round-up to £1. Rationale, pre-registered: every floor/cushion guarantee in the candidate set (CPPI m≤1, HARA subsistence, DD-03, loss-budget fraction) is proved under `stake ≤ cushion`; rounding up can cross the cushion and silently converts a probability-one floor into a probability-<1 floor. Worse, round-up bites hardest exactly when the bank is low — it injects extra risk in the states where every rule in the set intends least, a bias correlated with drawdown. Rounding up is also how a "more conservative than expressible" rule (§1.4 of input A) is silently replaced by a different, more aggressive rule while keeping its name. SKIP events are first-class output (participation, §2.9), not noise.

### 1.4 Commission — net market winnings, exact arithmetic
One selection per market, so per-market = per-bet:

```
win:  gross = s * (O − 1)            # Decimal, exact
      comm  = gross * c              # Decimal, exact
      π     = quantize_pence(gross − comm, ROUND_DOWN)   # credited winnings, pence
lose: π     = −s                     # pence, exact
```

`ROUND_DOWN` on credited winnings is the conservative, deterministic convention; it is applied once per market at settlement, never per intermediate term. A losing market pays no commission. No per-order commission field exists (SPEC-080 semantics).

### 1.5 Over-bank demands — clamp, flag, never borrow
A back bet's maximum loss is its stake, so the feasibility bound is the unreserved bank, and there is no leverage:

```
s_dem := min(s_dem, available)       # available per §1.6
record CLAMP event if binding
```

Clamping is legitimate (it is the exchange's own constraint, not an edit of the rule) but every clamp is counted; a rule clamped on >5% of placed bets is flagged `CLAMP_DISTORTED` in the report because its measured behaviour is no longer the named rule's.

### 1.6 Day-level reservation
Each rule exposes a day budget `B_day` from morning state (`= W` for plain rules; `= cushion W − F` for floor rules; `= B − L_ledger` for loss-budget rules). Bets are processed in canonical order (§0.4): each bet's stake is computed from morning state, then `min(stake, remaining)`; `remaining` decrements by the granted stake; a grant `< 100p` → SKIP with reason `SKIP_RESERVE`. This preserves every floor guarantee under simultaneous same-day bets (worst case: all lose; total loss ≤ `B_day`), deterministically, without proportional rescaling (which would break §1.3).

### 1.7 Edge-consuming rules
Rules flagged `needsEdgeEstimate=true` consume only §0.1's archived `p̂_i` / `p̂_lo,i`, with `b_i = (O_i − 1)(1 − c)` folded in exactly as verified in input B. Rules whose own verified specification abstains when the conservative edge is non-positive (KELLY_LOWER_CONFIDENCE_BOUND, RCK at `E[r]≤1`) abstain; abstention is scored (§2.9), never treated as missing data.

---

## 2. OUTPUT METRICS (per rule × scenario × commission)

All path metrics on the **end-of-UTC-day** wealth series (frequency is a pre-registered parameter of the drawdown family; input A §2.7). Every metric gets: point value on the realised sequence, day-block bootstrap CI (§3), and paired beat-fraction vs incumbent (§3.4). Absorbed paths (§5): wealth frozen at absorption value; per-day log growth computed over alive days only, absorption reported separately.

2.1 **Terminal wealth**: `median(W_N)` across draws (headline); `Q_05(W_N)`, `Q_25(W_N)`; `mean(W_N)` reported DIAGNOSTIC-ONLY, labelled with its skew/kurtosis (the all-in pathology detector, never a ranking key).
2.2 **Survival-first composite (PRIMARY, Uhrín form, disambiguated)**: `med(W_N)` subject to `P(min_t W_t < 0.9·W_0) ≤ 0.05`, both computed across draws. The constraint is on the path minimum, explicitly (the source's ambiguity is resolved here, pre-registered).
2.3 **Ruin probabilities**: `P(DEAD_HARD)`, `P(DEAD_FLOOR)` (§5), and `P(min_t W_t < α·W_0)` for pre-registered `α ∈ {0.9, 0.7, 0.5}` — path-minimum sense, stated on every table (input B flagged final-bank vs path-min conflation; frozen here as path-min).
2.4 **P(ahead) curve**: `t ↦ P(W_t > W_0)` at all t; endpoint reported as one number.
2.5 **Growth**: `ĝ = (1/D_alive) Σ log(W_d/W_{d−1})` per day, and per-100-bets; never annualised.
2.6 **Drawdown family**: MDD (relative, end-of-day); CDaR_α for `α ∈ {0.90, 0.95}` via the Chekhlov LP / order-statistic mean of the worst `(1−α)` fraction of daily drawdowns; CED_0.90 = `E[MDD | MDD > Q_0.90(MDD)]` across draws; Ulcer Index `UI = sqrt(mean_t(100·(W_t/M_t − 1))²)`. Calmar: reported `UNAVAILABLE_UNTIL_36M`, never proxied.
2.7 **Time-to-target**: `τ_a` for `a ∈ {£120, £200}`; median and mean over draws WITH right-censoring explicit: paths not reaching `a` reported as censored count, never dropped.
2.8 **CRRA certainty equivalents**: `CE_γ = u^{-1}(mean_b u(max(W_N^{(b)},1)/W_0))` for `γ ∈ {0.5, 1, 2, 4, 8}`, exact binary-payoff arithmetic (no lognormal shortcut).
2.9 **Measurement-value metrics**: participation rate (placed / eligible); Kish `n_eff = (Σs_i)²/Σs_i²` and `deff = 1 + CV²(s)` on the realised replay; clamp count; SKIP-reason histogram; silent-death flag (§5 R3).
2.10 **Sharpe (diagnostic only, never a ranking key — input A C4)**: per-day Sharpe, plus the Deflated Sharpe of the eventual selected rule computed with the true trial count `N` (§6.4).
2.11 **Sortino**, MAR = 0, per-day, reported with the odds-mix caveat attached; stratified by odds band `{[1.20,1.50), [1.50,2.00), [2.00,3.00), [3.00,6.00]}` — as is metric 2.5 (input A §1.4: flat and proportional rules coincide/diverge by band; unstratified comparisons are price-mix artefacts).
2.12 **Loss-budget consumption**: distribution of `L_ledger` at horizon and P(exhaustion).

---

## 3. RESAMPLING — day-clustered, paired

3.1 **Unit**: whole UTC days. A day object = the full set of that day's bets (odds, outcomes, ordering metadata). Bets are NEVER resampled individually (measured ~0.7 correlation of drawdown estimators with the dependence parameter; input A §2.9/C12).

3.2 **Scheme**: stationary bootstrap (Politis–Romano) over the sequence of `D` realised betting days, expected block length `ℓ*` chosen by Politis–White (2004) on the day-P&L series of the flat-£1 incumbent replay; `ℓ*` recorded. Sensitivity reruns at fixed `ℓ ∈ {5, 20}` reported in an appendix. Each draw produces a synthetic sequence of `D` days (same length as realised).

3.3 **Draw count and seeding**: `B = 10,000` primary. RNG = PCG64, master seed pre-registered in config; draw `b`'s day-index sequence is generated ONCE and stored (or regenerated from `seed, b` deterministically).

3.4 **Pairing — the load-bearing requirement**: for each draw `b`, the SAME resampled day sequence is replayed through EVERY rule and every scenario. All cross-rule comparisons are within-draw:

```
D_b(r, r') = metric(r, path_b) − metric(r', path_b)
beat_fraction(r, r') = #{b : D_b > 0} / B
```

Because both rules face identical odds and outcomes in draw `b`, `D_b` isolates the staking policy. Unpaired (independent-draw) comparisons are forbidden; they throw away the common-shock variance and are exactly the mistake §0 of input A(2) warns the whole exercise is one algebraic step from.

3.5 Point estimates come from the single realised sequence; CIs are percentile intervals over the `B` draws; paired claims use `{D_b}` (§6).

---

## 4. STRESS SCENARIOS — counterfactual edges without invented outcomes

4.1 **Principle**: no outcome `y_i` is ever flipped, deleted-for-effect, or synthesised. The only honest lever that shifts the mean while touching nothing random is a deterministic price/cost haircut applied to winning payouts — interpretable as "same selections, worse execution," which is precisely the component of the measured edge that is unproven (the declared-execution-cost CI already spans zero).

4.2 **Measured baseline**: `μ̂ = (1/n) Σ r_i`, the equal-weight per-unit-stake mean return of the realised sequence at the run's commission rate, where `r_i = y_i b_i − (1−y_i)`, `b_i = (O_i−1)(1−c)`. Computed by the harness, recorded; not assumed to equal +0.07.

4.3 **Scenario set**, target mean shifts `Δ ∈ {0, −μ̂/2, −μ̂, −2μ̂}` (as-measured / half / zero / sign-reversed, same magnitude):

Winning payouts are scaled by a single haircut factor `h(Δ)` solving, in exact arithmetic, the equal-weight identity

```
(1/n) Σ_i [ y_i b_i (1−h) − (1−y_i) ] = μ̂ + Δ
⇒ h = −Δ · n / Σ_{i: y_i=1} b_i
```

Replay uses `b_i' = b_i(1−h)` on wins; losses unchanged at `−1` per unit stake. Implemented as an exact `Decimal` multiplier on credited winnings after §1.4, before pence quantisation.

4.4 **Why losses are untouched**: `r' = r − Δ` applied additively would make a losing bet lose more than its stake — a physically impossible cash flow that spuriously breaches every cushion/floor guarantee in the candidate set. The win-haircut preserves `max loss = stake`, so floor proofs remain valid in the counterfactual world.

4.5 **Honest limitation, stated in the report verbatim**: the haircut holds win indicators fixed, so the counterfactual has the true lower mean but the realised win pattern; a genuine lower-edge world would also have different higher moments. This construction therefore *understates* variance differences between scenarios. It is retained because it is the unique construction that invents no outcomes; scenario results are labelled "price-degradation counterfactual," never "simulated zero-edge world."

4.6 **Secondary stress (physical)**: one adverse tick — each `O_i` moved one index down the canonical ladder (SPEC-053 integer arithmetic) before computing `b_i`. Reported alongside `Δ` scenarios as the latency/queue interpretation of the same doubt.

4.7 **Per-rule realised shift**: because rules weight bets unequally, the stake-weighted realised mean under haircut `h` differs slightly from `μ̂+Δ`; the harness records each rule's realised stake-weighted mean per scenario so no table implies a precision the construction lacks.

4.8 Edge-consuming rules receive the SAME archived `p̂_i` in every scenario (their beliefs don't know the world got worse). That is deliberate: the stress question is "what happens to this rule when its edge belief is wrong," which is the Uhrín 0.6%-vs-100% axis (input A §1.3a), and it is the axis on which admissibility is gated (§6.2).

---

## 5. RUIN AND FLOOR DEFINITIONS (all three recorded; roles fixed)

- **R1 `DEAD_HARD`** — absorbing. End-of-day `W < 100p`: no legal bet can ever be placed again; wealth frozen. Reported as `P(DEAD_HARD)`.
- **R2 `DEAD_FLOOR`** — absorbing, PRIMARY ruin definition. End-of-day `W < FOUNDER_FLOOR = W_0 − LOSS_BUDGET`. `LOSS_BUDGET` is a founder-approved config constant fixed before the run (default proposal `£30 ⇒ floor £70`; the value is an input, not a finding). Breach = governance stop: wealth frozen at breach value. This is the SPEC-060-shaped definition and the one all survival gates use.
- **R3 `SILENT_DEATH`** — non-absorbing flag. Rule demands `< £1` (or abstains) on every eligible bet for 30 consecutive betting days while `ALIVE`: the rule has switched itself off (ratchet freeze, CPPI cash-lock, bank-divisor trap — the failure mode input B verified repeatedly). Reported as flag + onset day; a rule with `P(SILENT_DEATH) > 0.10` under the as-measured scenario is inadmissible (§6.2), because a rule that stops betting stops buying evidence, and evidence is what the bank is funding.

---

## 6. SELECTION RULE — pre-registered, frozen before any results are seen

6.1 **Trial count**: `N` = number of rule instances entering the harness (each parameterisation counts separately). `N` is written into the config and the trial ledger (SPEC-091 style) BEFORE the first replay; it may not be revised downward afterwards.

6.2 **Admissibility gates** (all must pass; evaluated per rule, `c = 0.05` column):
- G1: `P(DEAD_FLOOR) ≤ 0.05` under the ZERO-edge scenario (`Δ = −μ̂`).
- G2: `P(DEAD_FLOOR) ≤ 0.10` under the NEGATIVE-edge scenario (`Δ = −2μ̂`).
- G3: `P(SILENT_DEATH) ≤ 0.10` and participation `≥ 0.70` under the as-measured scenario.
- G4: `CLAMP_DISTORTED` flag not set.
Gates bind on stress scenarios, not the flattering one: a rule that survives only when the edge is real is not a safe rule, and the edge is not established.

6.3 **Winner among admissible rules**: highest `median(W_N)` under the as-measured scenario, PROVIDED it beats the incumbent (`LEVEL_STAKES` flat £1, the pre-declared status-quo default) in the paired sense with multiplicity control:

```
beat_fraction(r, incumbent) ≥ 1 − 0.05/N        (paired draws, §3.4, terminal wealth)
AND Q_{0.025/N}({D_b(r, inc)}) > 0              (Bonferroni-adjusted paired-difference quantile)
```

Both thresholds use the full pre-registered `N`, per the Deflated-Sharpe logic (input A §2.12): trying `N` rules and keeping the best is textbook selection bias unless the bar is raised by `N`.

6.4 The selected rule's Deflated Sharpe (per-day returns, `T = D`, actual `N`) is reported as a sanity check; if `DSR < 0.95` the adoption is downgraded to PROVISIONAL regardless of 6.3.

6.5 **Tie-breaks**, in order: (i) smaller `CDaR_0.95` under the zero-edge scenario; (ii) fewer free parameters; (iii) incumbent retained.

6.6 **Default**: if no rule passes 6.2 + 6.3, the incumbent flat £1 stake is retained. The default is part of the pre-registration; "nothing won" is a recorded outcome, not a trigger to relax thresholds. A separate, explicitly-labelled EXPLORATORY ranking (uncorrected) may be published to seed the next *prospective* phase, but it authorises no change of staking rule.

6.7 No threshold, gate, `α`, or scenario magnitude may be altered after any replay output has been observed. Config hash is committed before the run; results cite it.

---

## 7. THE NULL OUTCOME — stated in advance

7.1 **"None of these help" means**: no admissible rule satisfies §6.3 against flat £1. Given the governing algebraic result (input A(2) §0: for non-compounding rules, every pairwise staking contrast is the edge test rescaled downward, `|t_pair| ≤ t_edge`, and `t_edge` currently spans zero), **this is the expected outcome**, and the pre-registration says so explicitly so that a null cannot be spun as a failure of the study.

7.2 If the null occurs, the recorded conclusion is:
1. Flat £1 minimum stake is retained — not as timidity but as the estimator-optimal rule while the edge sign is unknown (`deff = 1`, `n_eff = n`; timid-play optimality of goal-before-ruin under `p > 1/2`; input A §2.21b/§4.5).
2. The staking-rule decision is DEFERRED behind the edge-sign decision; the next spend of the bank is on the §2.21a objective (decisive verdict at pre-set error rates), not on staking variety.
3. What the study still delivers — and this is estimable even at zero mean, because it depends on second-moment and path structure, not the mean's sign — is the measured trade-off matrix itself: each rule's drawdown, floor-breach, silent-death and participation behaviour under the four edge scenarios. That matrix is the founder's requested "whole matrix," and it remains valid input to the moment the edge sign resolves.

7.3 A secondary null is also pre-declared: if some rule wins §6.3 under as-measured but fails G1/G2, the recorded conclusion is "the winner is an edge amplifier, not a staking improvement" — it is not adopted, and the result is filed as a demonstration of C13 (same rule, opposite tail behaviour under opposite edge sign), not as a discovery.

---

## 8. DETERMINISM AND REPRODUCIBILITY

8.1 One config file, hashed, containing: ledger hash, `W_0`, `LOSS_BUDGET`, commission set, scenario set, `B`, seed, block-length rule + realised `ℓ*`, `N`, every rule's frozen params, every pre-registered constant in §§2–7.
8.2 `Decimal` context: precision 28, `ROUND_DOWN` for stake quantisation and credited winnings, no float intermediates in money paths; property test asserts replay determinism (same hashes → byte-identical outputs).
8.3 Output: one matrix artefact (rule × scenario × commission × metric) with the three-column contract per cell — point, CI, paired beat-fraction vs incumbent — plus the trial-ledger entry recording `N`, endpoints, and stopping rule before observation (SPEC-091/094 style).
8.4 Corrections from input B are binding on implementation: the FIXED_PROFIT_COMMISSION_NAIVE coverage identity is checked on the intersection population only (it keeps O=2.00 and drops 2.02/2.04); ODDS_BAND_UNIT_LADDER uses the closed form `sd = sqrt((O−1)(1−c))`; the three CVaR scenario-LPs use the `π_k`-weighted form `ζ + (1/(1−α))Σ_k π_k u_k`; `CVAR_TARGET_SCALING` gets an explicit refusal branch for `Ĉ_t ≤ 0`; the truncated entries (SQUARE_ROOT_STAKING source field, DR_KELLY_DIVERGENCE, DD-18, CPPP) must be re-emitted in full before their rules are coded, else they are excluded and the exclusion recorded.