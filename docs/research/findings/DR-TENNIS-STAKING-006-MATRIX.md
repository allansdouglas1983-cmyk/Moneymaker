# STAKING-RULE CANDIDATE SET — RANKED COMPARISON FOR HEAD-TO-HEAD MEASUREMENT

**Status of this document.** Consolidation of six verified rule-family surveys against the objective taxonomy. Every rule below survived adversarial verification (CONFIRMED or CORRECTED). Nothing here is a staking recommendation; all stakes are computed by deterministic code; the winner is decided by the pre-registered measurement protocol.

**The governing fact, stated first because it ranks everything else.** For non-compounding rules on one settled sequence, the head-to-head IS the edge test rescaled downward: t(A beats B) = t(edge≠0) × (mean ΔS / rms ΔS), bounded by 1 (Cauchy–Schwarz), with effective sample sizes measured at 27–4,068 of the 4,153 bets depending on rule pair. The day-clustered edge CI currently spans zero. Therefore: **no reward-metric ranking (growth, median, terminal wealth) between rules is establishable today at any confidence the edge test itself fails.** What is estimable now is the risk-shape column set (drawdown, floor behaviour, coverage, n_eff), and that is what the ranking below prioritises.

---

## 1. CONSOLIDATED CANDIDATE LIST (de-duplicated)

74 family entries collapse to **45 candidates + 7 retained controls + 5 exclusions**. Kelly appeared in three families (KELLY_FULL_BINARY_EXCHANGE = KELLY_LOG_UTILITY_GAMMA_1 = the γ=1 CRRA member); flat staking appeared in five disguises.

### Group A — flat and stake-shape rules (all edge-free)

| ID | Rule | Absorbs (verified identities) |
|---|---|---|
| A1 FLAT | Level stakes, fixed unit u | LEVEL_STAKES_AS_FRACTION_OF_INITIAL_BANK (u=fW₀); FIXED_LIABILITY (back-bet max loss = stake); OBPI_STATIC_BUDGET (s=B/N); DD-07 / LOSS_BUDGET_LEVEL_STAKE (u=B/K, Lundberg table kept as diagnostic); CVAR_SINGLE_BET_ANALYTIC (per-bet CVaR budget ≡ flat cap for every conventional α, since α > p across the whole 1.20–6.00 odds range) |
| A2 FP-NET | Stake to win T net: s=T/((O−1)(1−c)) | — (coverage: unplaceable above O = 1+T/(1−c) = 2.0526 at T=1) |
| A3 FP-NAIVE | Commission-blind control s=T/(O−1) | CORRECTED: places iff O ≤ 1+T (keeps 2.00; additionally drops ticks 2.02, 2.04). NOT a pure (1−c) rescaling of A2 — identity check valid only on the intersection population |
| A4 FR-PAY | Fixed total return s=R/(1+(O−1)(1−c)) (+ naive variant) | Same coverage threshold as A2 at R=T+s |
| A5 FP-PROP | Proportional profit target g·W_t | Full coverage to 6.00 needs g ≥ 0.0475 on £100 |
| A6 VE-LADDER | Variance-equalising odds-band units, k(O) ∝ 1/√((O−1)(1−c)) | CORRECTED: use closed form sd = √((O−1)(1−c)); at O=1.20 sd = 0.4359 (not 0.42). Short:long unit ratio 5.00 |
| A7 SQRT | s = u₀ + √(max(P_t,0)), escalation funded only from profit | Settlement-vs-placement update timing must be frozen |
| A8 STEP | Bank-band step ladder k=clip(floor(W/50),1,K) | — |
| A9 REBASE | Periodically rebased unit (bounds: period 1 = B1; ∞ = A1) | — |
| A10 BANKDIV | u = W/N floored | N = W₀/u is a self-switch-off trap (median finals 99.2–99.4); config banned, family kept |

### Group B — floor / portfolio-insurance rules (all edge-free)

| ID | Rule | Notes |
|---|---|---|
| B1 PROP-F | Fixed fraction f of current bank | = CONSTANT_MIX = CPPI at F=0 |
| B2 CPPI | s = m(W−F), fixed floor F | Absorbs 4 entries. Variants: m=1 gapless; m≤1 gap-safe (X_min=−1 forces m≤1 for an absolute per-epoch guarantee); capped e=min(mC,W). Floor a.s. for back bets with day-reservation (P(bank<50)=0.0% in every simulated regime) |
| B3 LB-FRAC | Fraction of remaining loss budget | Strictly more conservative than B2 twin (B−L_t ≤ W_t−F always); its final-bank distribution is worse — never quote the twin's medians for it |
| B4 TIPP | Ratcheting high-water-mark floor CPPI | Variants: RATCHET-CLICK (Khuman discrete clicks, gap-risk-neutral: 0.013% vs 0.013%); ABS-DD-FLOOR (additive: F=max(F₀, W_max−D_abs), bounds absolute drawdown by D_abs a.s.) |
| B5 HB-CAP | Hsieh–Barmish drawdown modulation cap: stake ≤ W−(1−d_max)·HWM | = DD-03. Probability-one max-drawdown bound, distribution-free, no i.i.d. needed. Identity: = TIPP(φ=1−d_max, m=1). Cap thresholds on £100, d_max=0.30: £30 at HWM, £1 at W=71, sub-minimum below |
| B6 MARGIN-FLOOR | Conditional (non-ratchet) margin floor | UNSOURCED spec of a real mechanism (Ben Ameur–Prigent); rolling stop, no hard guarantee |
| B7 VAR-CPPI | VaR-conditional multiple m_t ≤ −1/Q_α | Day-level epoch adaptation; biggest look-ahead risk in family; time-respecting estimation mandatory |
| B8 ES-CPPI | ES-conditional multiple m_t = |ES_α|⁻¹ | Always ≤ B7's multiple; warm-up forced m=1 for N epochs |
| B9 NYSTRUP | Drawdown-scaled attenuation of an edge-free base stake s₀ | £1 granularity destroys the attenuation at s₀=£1 on £100 — needs s₀≥£3 to express |
| B10 CPPP | Performance participation vs pre-registered benchmark | Diagnostic arm only; protects relative, not capital |

### Group C — risk-statistic-targeted scaling (edge-free)

| ID | Rule | Notes |
|---|---|---|
| C1 RISK-TARGET | s = κ·W / statistic, statistic ∈ {realised MDD (DD-10), DaR_q (DD-11), CDaR_α scalar (DD-12), day-CVaR_α (CVAR_TARGET_SCALING)} | Homogeneity-exact inversions; day-block bootstrap; MDD arm carries single-observation error (Chekhlov's own warning); day-CVaR arm needs a defined refusal branch for Ĉ_t ≤ 0; window discipline pre-registered |
| C2 EMDD-FLAT | Flat stake from E[MDD] = 1.2533·σ·√T at zero drift (Magdon-Ismail) | On £100 with a 20% one-year MDD target: s* = £0.65 < £1 floor. Tightest feasible target ≈ 31%. DD-09 signed-drift branches kept as diagnostic; evaluate Q_p numerically (drift correction ~10–20% at x=1.47, not negligible) |

### Group D — growth / utility rules (ALL require a signed edge estimate)

| ID | Rule | Notes |
|---|---|---|
| D1 K-FULL | f=(pb−(1−p))/b, b=(O−1)(1−c) | Ruin 0.6% (right sign) vs 100% (wrong sign) |
| D2 K-FRAC | k·f_Kelly | Absorbs 1/γ map and DD-15 Thorp inversion (c* from x^(2/c−1)=β; c*=0.268 reproduces RCK λ=6.456 exactly — same object). CORRECTED: half Kelly was NOT worst-of-all in Metel (CCx α=0.10 scored 12.158 < 13.268) |
| D3 K-CRRA | Exact binary f=(K−1)/(K+b), K=(pb/(1−p))^(1/γ) | Absorbs CRRA_EXACT_BINARY_V1. γ-from-drawdown map: γ=(1+ln β/ln x)/2. Defensible γ ≥ 1.474 (c=5%) / 3.022 (c=2%) gives stake < £1 on £100 — inoperable bank size |
| D4 HARA-FLOOR | K-CRRA fraction applied to cushion W−F | Floor holds pathwise for ANY p (f<1 strictly); sizing still edge-fed; silent-freeze below £1 near floor |
| D5 CARA | s = ln(pb/(1−p))/(a(1+b)), wealth-independent | a=γ/W_ref match to CRRA is first-order only |
| D6 K-BAYES | Chu–Wu–Swartz estimators: f₀ mean; f₁ median (tie control — f₁=f₀ to 3dp in all five examples); f₂ squared-error (negative control — never abstains, largest f always); f₃ asymmetric loss | CORRECTED: f₃ ordering not universal — under the sceptical a=b=100 prior, f₀=f₁=0.005 < f₃a=0.008 < f₃b=0.012; f₃ is NOT guaranteed most conservative |
| D7 K-LCB | Kelly at pre-declared conservative quantile of p | With the current zero-spanning day-clustered CI: f=0 identically. The honest "not yet" rule; abstention must be scorable |
| D8 K-SHRINK | Baker–McHale shrunken Kelly | BLOCKED: shrinkage closed form not obtained; do not invent; fallback D6-f₀ |
| D9 CC2 | Metel chance-constrained reweighting | Sandwich-covariance input required |
| D10 K-EPMC | Metel E[p] Monte Carlo + Jensen lower bound | Beat plug-in in all four experiments; ~⅓ of available log growth destroyed by estimation error alone (18.5 vs 27.5) |
| D11 DRK-BOX | Distributionally robust Kelly, box ambiguity | Highest minimal wealth in every Uhrín table (0.08/0.23/0.28), 0% ruin |
| D12 DRK-DIV | f-divergence DR Kelly (KL/revKL/TV/χ²) | Entry TRUNCATED — re-emit before coding |
| D13 RCK | Busseti–Ryu–Boyd: max E log s.t. E[(rᵀb)^−λ]≤1, λ=ln β/ln α | Whole-CDF drawdown bound; dominates fractional Kelly for the drawdown objective (0.047 vs 0.035 at matched 10% risk); Lemma 1: auto-zero when every bet has E r ≤ 1; binary per-bet case degenerates to a fractional Kelly — the solver buys nothing except the simultaneous case |
| D14 RCK-CRRA | Long 2026 CRRA support-invariance | Unreplicated 2026 single-author preprint — carry flagged |
| D15 GZ-DD | Grossman–Zhou ratcheting-floor cushion, ρ_eff=α+ρ(1−α) | Absorbs DD-01/HARA_DRAWDOWN_HWM (CORRECTED: discrete-time non-optimality is Klass & Nowicki 2005, not "Cui, Nguyen"); ρ=1 arm = KOP numeraire (exact (1−α) growth cost theorem); Zhou-Shang risk-floor wrapper (functional form is a reconstruction — label in ledger) |
| D16 HB-KELLY | DD-04 fitted-γ drawdown-modulated Kelly | γ*=11.15 fitted on 60 returns — thin-basis warning stands |
| D17 DD-BARRIER | Additive barrier stake s*=2eD/(v² ln(1/q)) | £1.40 at q=5%, D=30, e=0.07; collapses to "exit w.p. 1" at e≤0 |
| D18 REDD-COPS | Yang–Zhong rolling economic drawdown | TRUNCATED entry + practitioner-blog formula unverified — re-emit and re-check flag |
| D19 JOINT-HARA | Joint same-day expected-utility allocation (Whitrow / Whelan) | The correct multi-bet member; Whelan's aggressive multi-outcome result must NOT reproduce under back-only N=2 |
| D20 BAYES-CRRA | Posterior-integrated CRRA | Structural warning verified: FOC at f=0 depends only on posterior MEAN — a zero-spanning interval with positive mean still stakes. Never abstains |

### Group E — downside / safety-first (mixed)

| ID | Rule | Notes |
|---|---|---|
| E1 CVAR-LP-MIN | Min CVaR at fixed day budget (Rockafellar–Uryasev LP) | CORRECTED: use π_k-weighted form ζ+(1/(1−α))Σπ_k u_k; the equal-weight 1/(q(1−α)) form is valid ONLY for equal-probability scenarios. Runs on de-vigged market probabilities — no signed edge |
| E2 CVAR-LP-EV | Max EV s.t. CVaR budget | CORRECTED: same weighting fix — as published it certified a tail budget it did not satisfy. Inoperable at non-positive conservative edge (optimum is s=0) |
| E3 CVAR-LP-MULTI | Multi-level CVaR shaping (R-U 2002 Thm 16) | CORRECTED: weighting + drop the α=0.99 level (own discipline caps α≈0.95 at ~250 day-blocks) |
| E4 ROY | Safety-first ratio (fixed-budget / multi-period forms only) | Single-period unconstrained form is degenerate (demands zero exposure) — never trade it |
| E5 ROY-MILP | Exact shortfall-probability MILP (LPM₀) | Path/scale variant is the edge-free arm; allocation form needs probabilities |
| E6 TELSER | Max EV s.t. P(loss>D)≤ε (CVaR surrogate via Cor. 7) | Edge-needing; magnitude-blind |
| E7 KATAOKA | Max ε-quantile floor | Same split: day-block scale arm edge-free, allocation arm not |
| E8 OMEGA-WRAP | Uhrín fractional wrapper f_ω = ω·f_base + (1−ω)·cash, selected by max med(W) s.t. P(min W < 0.9W₀) ≤ 0.05 | The published formalisation of "keep it safe, keep it trending up"; re-derive Q5 wording explicitly before use |

### Exclusions (not carried)

1. **OBPI-SYN** — structurally inapplicable: a binary hold-to-settlement claim has no resizable underlying, no delta; lay-side unwind prohibited. Recorded as a negative structural finding.
2. **MERTON-DIFF** — dominated (§5).
3. **QRCK** — dominated (§5).
4. **TRIGGER-BAND CPPI** — dominated (§5).
5. **CVAR-SINGLE** — exact identity with A1 at every conventional α; kept as a lemma, not an arm.

### Retained known-bad controls (harness validation — a harness that fails to rank these last is broken)

FP-NAIVE (A3), SL-PI (stop-loss insurance: floor violated, 14.72% vol, highest mean — the E[W_N] pathology proxy), RATCHET-PIN (peak-pinned stake: ~19.3% of −3% paths terminally frozen), THROTTLE (≡ BANKDIV N=100 self-switch-off, verified identity), CONF-LADDER (confidence points: the Uhrín informal-heuristic class ruined 85.2% / 36.1% of paths on a dataset where the model genuinely beat the market), K-BAYES-f₂ (never abstains, largest fraction in every example), K-BAYES-f₁ (designed tie control).

---

## 2. THE MATRIX

Rows = canonical rules (variants inherit). Columns = taxonomy objectives. † = row is conditional on a true positive edge; while the sign is unproven every † row's growth cells are undefined and its risk cells are the measured wrong-sign outcomes.

Ratings: **OPT** = proved/measured optimal for that objective; **+** good; **0** neutral; **−** bad; **✗** pathological.

Column-level verdicts (identical for every row, so not tabulated): **Sharpe** — never an optimisation target for any rule: the Sharpe-optimal stake is zero (Hakobyan–Lototsky Thm 2.1); report and deflate only. **Sortino** — odds-mix statistic at MAR=0; stratify by odds band or it measures the price mix. **Calmar** — not computable for 36 months; report unavailable. **E[W_N]** — optimised only by betting everything (Samuelson); SL-PI is its diagnostic proxy; skew 45.5 / kurtosis 2,303 territory; never a target.

| Rule | Log growth (2.1) | Median W_N (2.3) | Q05 W_N (2.4) | P(ruin £1) (2.5) | P(goal before ruin) (2.6) | E[MDD]/CDaR (2.7/2.9) | DD-prob control (2.8) | P(ahead)/honest ROI (2.15) | CRRA CE (2.17) | n_eff (2.21) |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 FLAT | 0 no compounding | + tight dist | + low dispersion | + slow diffusion¹ | **OPT** timid play, p>½ (Ross 1974) | + smallest scale, √T growth | 0 no mechanism | **OPT**-class: unweighted ROI unbiased | + at high γ | **OPT** deff=1, uniquely |
| A2 FP-NET / A4 FR-PAY | 0 | + | + lower per-bet var | + | + | + variance-shaped | 0 | ✗ drops ~27% of prices, all long — selection-biased scorecard | + | − population changes |
| A6 VE-LADDER | 0 | + | + | + | + | **+** per-bet sd equalised, full coverage | 0 | + | + | − deff=1+CV² |
| A7 SQRT | + profits compound | 0 | + | **+** initial bank never escalated | + | + | 0 | + | + | − |
| A8/A9/A10 ladders | between A1 and B1 | ← | ← | ← | ← | ← | ← | ← | ← | ✗ at N=W₀ (trap) |
| B1 PROP-F† | + compounds; ✗ at μ≤0: W→0 a.s. (Jensen) | f=.02: 209/88.8/59.4 at +7/0/−7%² | − | − floor makes ruin real | − | − | − | − even record loses (1−f²)ⁿ; ROI understated ×½ | 0 | ✗ stake-weighted |
| B2 CPPI m≤1 | − cushion-only | − zero-edge median 59.7 vs flat ~100 | + | **OPT**-class: floor a.s., P(<50)=0.0% all regimes | − | + bounded by cushion | **+** implies bound | − | + | − |
| B3 LB-FRAC | −− | −− | + | **OPT**-class, ≥ B2 | − | + | + | − | + | − |
| B4 TIPP | − lowest mean (4.89%) | − | + | **OPT**-class ratchet floor, never violated | − | **OPT**-class measured: 2.24% vol vs CPPI 5.88% | + | − cash-lock: permanent underwater once monetised | + | − |
| B5 HB-CAP | 0 (cap, not sizer) | 0 | + | **+** floor (1−d_max)·HWM | 0 | **OPT** a.s. pathwise bound, distribution-free³ | **OPT**-class (prob. 1, not 1−β) | 0 | 0 | 0 base-rule dep. |
| B7/B8 VaR/ES-CPPI | 0 | 0 | + | + | 0 | + | + targeted breach rate (~2.5/yr at α=.01 daily) | 0 | 0 | − |
| C1 RISK-TARGET | 0 | 0 | + | + | + | **+** statistic directly targeted (exact homogeneity) | + approx | + | + | 0 slow scale drift |
| C2 EMDD-FLAT | 0 | + | + | + | + | **OPT** at zero drift by construction; infeasible below ~31%/yr target on £100 | + | + | + | **OPT** (flat) |
| D1 K-FULL† | **OPT** (Breiman) | **OPT** (Ethier 2004) | ✗ $1,000→$18 paths | ✗ 0.6%→**100%** on sign flip⁴ | − 0.67 double-before-halve | ✗ P(halve)=½ | ✗ 0.397 at α=0.7 | − | OPT at γ=1 only | ✗ |
| D2 K-FRAC† (k=½) | + 75% of growth | + | + $145 bad path | + 0% (right sign) | + 8/9 | + P(halve)=1/8 | − dominated instrument: 0.035 vs RCK 0.047 | − | ≈1/γ approx | ✗ |
| D3 K-CRRA/CARA† | + | + | + | + | + | + | − | − | **OPT** exact by construction; ≈D2 within 1.000–1.250× | ✗ |
| D6 K-BAYES-f₀† | + | + | + | + shrunk 0.048 vs 0.089 | + | + | − | − | + | ✗ |
| D7 K-LCB | · f=0 today | · | · | **OPT** trivially (no bets) | · | · | · | · | · | + preserves budget |
| D9–D12 est-aware† | + recovers ⅓ lost to estimation | + | **+** best in family (DRK-BOX min 0.08–0.28) | + 0% ruin all tables | + | + | + | − | + | ✗ |
| D13 RCK† | + 0.047 at 10% risk | + | + | + auto-zero at E r≤0 (Lemma 1) | + | + | **OPT** proved whole-CDF bound; dominates D2⁵ | − | + | ✗ |
| D15 GZ-DD† | + | + | + | + cushion floor holds any p | − | + continuous-time optimal; not optimal discrete (Klass–Nowicki) | + | − | + | ✗ |
| D19 JOINT-HARA† | + | + | + | + | 0 | + | 0 | − | **OPT** jointly per day | ✗ |
| E1 CVAR-LP-MIN | 0 | 0 | + | + | 0 | **OPT**-class: CVaR is the LP objective | + | + | 0 | 0 |
| E4–E7 Roy/Telser/Kataoka | 0/† | 0 | + | + own objective | + | 0 | + | 0 | 0 | − |
| E8 OMEGA-WRAP | inherits base | **target** of §4.1 criterion | + | constraint of §4.1 (Q5>0.9W₀) | + | + | + | + | + | inherits |
| Controls (SL-PI, RATCHET-PIN, THROTTLE, CONF-LADDER, f₂) | −/✗ | ✗ | ✗ | ✗ (85.2%, terminal freeze, self-off, floor breach) | ✗ | ✗ | ✗ | ✗ | ✗ | — |

¹ Zero-edge E[MDD] for a £1 flat unit ≈ 30.7 units per 600 bets — a £30 budget is expected to be consumed by drawdown alone at zero edge within ~1 year. ² Verified Monte Carlo medians. ³ Probability-one bound needing no distribution, no i.i.d., no edge — the strongest guarantee in the entire set. ⁴ Uhrín et al.: identical rule, ruin 0.6% with KL advantage, 100% without. ⁵ In the binary one-bet-per-market case RCK degenerates to a fractional Kelly; its dominance is in how the fraction is derived (λ from (α,β)) and in the simultaneous-bet case.

---

## 3. THE EDGE-FREE PARTITION (the decision-relevant section)

**Operable now, while the edge CI spans zero — 28 arms.** These consume only: bank state, declared risk policy, the odds ladder, loss-tail/path statistics, or de-vigged market probabilities. Verified no-edge-smuggled-through-constants in every case.

- Flat/shape: **A1 FLAT, A2 FP-NET, A3 FP-NAIVE (control), A4 FR-PAY, A5 FP-PROP, A6 VE-LADDER, A7 SQRT, A8 STEP, A9 REBASE, A10 BANKDIV (N≠W₀)**
- Floors: **B1 PROP-F, B2 CPPI (all variants), B3 LB-FRAC, B4 TIPP (+RATCHET-CLICK, ABS-DD-FLOOR), B5 HB-CAP, B6 MARGIN-FLOOR, B7 VAR-CPPI, B8 ES-CPPI, B9 NYSTRUP (on edge-free s₀), B10 CPPP (diagnostic)**
- Risk targeting: **C1 RISK-TARGET (×4 statistics), C2 EMDD-FLAT**
- Downside: **E1 CVAR-LP-MIN** (de-vigged market probs; note: the empirical day-block variant is a *scale* rule, not an allocation rule — history cannot map to today's bet identities), **E5/E7 path-scale variants, E8 OMEGA-WRAP** (wrapper)
- Controls: **SL-PI, RATCHET-PIN, THROTTLE**

**Inoperable while the sign is unproven — every Group D rule plus E2, E6, allocation-form E4/E5/E7, CONF-LADDER.** All consume a signed p or edge. The measured cost of running one anyway with the wrong sign is 100% ruin. Three special cases:

- **D7 K-LCB is the one Kelly-family rule honestly operable today**: fed the current zero-spanning day-clustered interval it outputs f=0 deterministically. It is the formalisation of "not yet" and its abstention must be scored, not treated as missing.
- **D20 BAYES-CRRA and D6-f₂ are the dangerous opposites**: both produce positive stakes from a zero-spanning interval (FOC depends only on the posterior mean; f₂ never abstains). They must never be promoted from control to contender while the sign is open.
- **Kelly at pure de-vigged market probabilities refuses to bet** after commission (E r ≤ 0 ⇒ f=0 by Lemma 1) — there is no edge-free way to run a growth rule; this is structural, not an implementation gap.

**Ranking for the measurement phase (research priority, not staking advice):** Tier 1: A1 (incumbent, n_eff-optimal, SPEC-060 twin), B2 m≤1, B4/B5 (the only a.s. guarantees), C1, E8 as the selection criterion. Tier 2: A6, A7, B3, B7/B8, C2, E1. Tier 3 (controls): the seven straw men. Group D enters the harness only as counterfactual replay, gated on the edge test resolving.

---

## 4. THE SIMULTANEOUS-BET PROBLEM

Several bets settle per UTC day and are correlated; the day is the unit of analysis. Single-bet Kelly applied independently to a card **overstakes** (Whitrow 2007). Drawdown estimates are ~0.7-correlated with the dependence parameter, so bet-wise resampling understates every drawdown metric — all path metrics from day-block resampling only.

**Native, correct multi-bet formulations:** D13 RCK (vector problem, verified in the paper), D19 JOINT-HARA (2^K joint states or Whitrow gradient; Whelan's mutually-exclusive aggressiveness must not reproduce back-only), E1–E3 CVaR LPs (scenario programs over the day card, with the π_k weighting fix), E5/E6/E7 MILPs, D9/D10 Metel portfolio forms, D11/D12 DR Kelly, B5 HB-CAP (Generalised Lemma, Σ|X_min|I ≤ M·V — pathwise multi-bet cap).

**Correct only with day-level reservation (must be coded as a constraint, not assumed):** B2 CPPI, B3, B4 TIPP, D4 HARA-FLOOR, B6 — the floor guarantee requires Σ(same-day stakes) ≤ cushion, because an all-lose day breaches the floor for any m>1. Verified fix: reserve the cushion across the open card. B7/B8 use the day-level epoch reinterpretation.

**Per-bet rules that silently overstake a correlated card:** D1, D2, D3, D5, D6, D8, D15, D16, D17, D20 (each prices bet i as if alone: k same-day bets at fraction f each ≈ k·f day exposure), and B1 PROP-F / A5 FP-PROP for the same reason. If any is ever traded, its stake must be computed jointly or divided by a declared same-day cap.

**Structurally neutral:** A1, A2–A4, A6, C1, C2 — flat-shaped stakes do not compound within a day, but their day-level worst case is k·u and every loss-budget/floor check must use that, not u.

---

## 5. DOMINATED — DROPPED BEFORE THE EMPIRICAL STUDY

1. **MERTON-DIFF ≺ D3 K-CRRA.** Identical inputs (p, b, γ); the exact binary closed form costs nothing more; the diffusion approximation errs +4.1% at O=1.30, flips sign at long odds, and can emit f>1. No objective on which it beats the exact form. Dropped.
2. **QRCK ≺ D13 RCK.** Same inputs, same solver class; RCK 0.047 growth at measured 10% risk vs QRCK 0.044 (after λ had to be hand-dropped to 2.800 because QRCK carries no guarantee); paper's own verdict "RCK yields superior bets". Dropped.
3. **TRIGGER-BAND CPPI ≺ daily-recomputed B2.** The band exists to save rebalancing cost; on Betfair recomputing a stake is free, so the band buys only gap risk (violations 0.018% vs 0.013%; 0.341% vs 0.260%). Dropped.
4. **CVAR-SINGLE ≡ A1** at every conventional α (α>p across the whole odds range ⇒ per-bet CVaR = stake identically). Duplicate, not carried.
5. **BANKDIV at N=W₀/u** ≺ everything: self-switch-off (bets £1 until first dip below 100, then never again). Configuration banned.
6. **K-BAYES-f₁ ≡ f₀** to three decimals in all five verified examples — kept only as the designed tie control.
7. **Conditional domination, noted not dropped:** fractional Kelly as a *drawdown-control instrument* is dominated by RCK (0.035 vs 0.047 at matched risk); in the binary per-bet case the two coincide, so D2 stays, with its fraction derived the RCK way (λ from pre-registered (α,β)) rather than by folklore k.
8. **Retained despite domination on every preservation objective** (as controls, per §1): FP-NAIVE, SL-PI, RATCHET-PIN, THROTTLE, CONF-LADDER, K-BAYES-f₂.

---

## 6. WHAT THE RESEARCH COULD NOT ESTABLISH

1. **Whether the edge exists.** Nothing above touches it. And because a rule comparison is the edge test rescaled (§0), the head-to-head cannot rank rules on reward at any confidence the edge test fails; with n_eff as low as 27 bets for genuinely different rules, reward rankings from this dataset are mostly noise. Only risk-shape columns are estimable now.
2. **Baker–McHale shrinkage closed form** (D8): full text not obtained; the rule cannot be coded; the identified fallback is D6-f₀. The paper remains the single most on-point publication for this operation and should be purchased.
3. **Four truncated verification entries** must be re-emitted before implementation: DRK-DIV, REDD-COPS (including its edge flag), SQRT's source field, RCK's measuredEvidence tail.
4. **Odds-mix-dependent constants are unpinned.** σ_R=0.9364, the 27.0% FP-unplaceability figure, and every E[MDD]-derived pound value depend on an unstated modelled odds population (internally consistent — 0.9364·√(0.98/0.95)=0.9511 exactly — but unverifiable). The harness must recompute all of them from the platform's actual declared odds population and publish it.
5. **Metric definitions not yet frozen:** "P(bank<£50)" was used in the final-bank sense; the path-minimum probability is roughly double at zero edge. Uhrín's Q5 constraint wording is ambiguous as printed. Both must be frozen as explicit formulas (path-minimum recommended) before any rule is compared on them.
6. **Continuous-time optimality does not transfer:** Grossman–Zhou is provably not always optimal in discrete time (Klass & Nowicki 2005); every "OPT" tag inherited from a diffusion theorem (D15, KOP, D2's γ-map) is approximate on a discrete £1-quantised lattice. The GZ multiplier scaling (1/(1−λ)) ambiguity and the "12 to 25 percent" quote remain unverified behind the paywall.
7. **Positive-drift E[MDD] correction:** the operation sits in the Q_p asymptotic crossover (x≈1.47); the correction is ~10–20%, so C2 must evaluate Q_p numerically, not assume the zero-drift constant.
8. **Unverified quotes carried with flags:** Ben Ameur–Prigent "monetized" sentence (B6); Zhou-Shang functional form is a reconstruction; Ethier–Tavaré ½ constant confirmed only at survey level; Roy/Telser/Kataoka/Sortino originals read via secondary restatements.
9. **Bank-size infeasibility is pervasive and unresolved by any rule choice:** defensible CRRA γ (≥1.474 at 5% commission), conservative E[MDD] targets (<31%/yr), and NYSTRUP attenuation are all inexpressible on a £100 bank with a £1 floor. The comparison lattice is coarse: at O=3.00 flat £1 and quarter-Kelly are the same rule; at 1.30 they differ ×6. Every result must be stratified by odds band or it is an artefact of the price mix.
10. **Nine verification corrections are load-bearing and must be applied before the harness freezes:** the three CVaR LP π_k weightings; FP-NAIVE's boundary coverage (keeps 2.00, drops 2.02/2.04); VE-LADDER sd closed form (0.4359 at 1.20); Metel half-Kelly not-worst; Bayes asymmetric-loss ordering; Klass–Nowicki attribution; Khuman gapless-dominance scope (series A vs B); the struck Dichtl–Drobetz "superior downside protection" quote; the restated Hubaček train/test finding.