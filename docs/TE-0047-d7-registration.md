# TE-0047 — REGISTRATION: the D7 conservative-bound allocator (matrix K-LCB), exact form

**Date:** 2026-07-30. **Type:** pre-registration, frozen BEFORE any test, implementation or
replay output. **Authority:** founder directive 2026-07-30 ("Accept proposals build it
properly no shortcuts"), accepting the DR-007 → D7 sequence. **Lineage:**
DR-TENNIS-STAKING-006 matrix D7 K-LCB — *"Kelly at pre-declared conservative quantile of p…
the honest 'not yet' rule"* — unlocked by DR-TENNIS-STAKING-007 (DR-003's spans-zero
condition discharged on the supported reading at the attested 2%).

This is NOT a shrink, NOT a multiplier, NOT the withdrawn Amendment-2 rule. The stake is
Kelly arithmetic evaluated at the **lower bound** of the measured day-clustered edge
interval — a subtractive conservative displacement (SPEC-034 consume-the-lower-bound
semantics). If the conservative bound ever touches zero, the rule stakes nothing, by
construction: DR-003's warning ("no shrinkage factor is protective" against a mis-signed
edge) is carried inside the formula rather than bolted on.

## The exact formula (all arithmetic exact Decimal / integer pence; floats prohibited)

For day card of k selected bets, morning bank W pence, high-water mark HWM pence:

```
b_i   = (O_i − 1) · (1 − c)                    commission-adjusted net odds
e_i   = p_i · (b_i + 1) − 1                    per-unit expected value (central)
e_i^c = e_i − Δe                               conservative edge (interval lower bound)
f_i   = e_i^c / b_i        if e_i^c > 0        Kelly at the conservative bound
      = 0                  otherwise           refusal — the D7 "not yet" branch
want_i = floor( W · f_i / k )                  same-day joint treatment (÷ k, see below)
```

then the **multi-bet HB-CAP day budget** (matrix B5 Generalised Lemma, pathwise, matrix §4):

```
cap = max( floor( W − (1 − d_max) · HWM ), 0 )
grant in canonical order: stake_i = min(want_i, cap_remaining); cap_remaining -= stake_i
```

then engine semantics downstream: `reserve_day` feasibility + £1-minimum skip-never-round-up.

## Frozen constants, each with its provenance

| constant | value | provenance |
|---|---|---|
| c (commission) | `0.02` | TE-0044 founder-attested Basic rate; SPEC-081 status ASSUMPTION until statement (task #89) |
| Δe (conservative displacement) | `0.0249` per unit stake | TE-0043 raw sweep, model source, supported fills, 2%, min_edge 0.02: ROI +3.86% CI95 [+1.37%, +6.29%] → 3.86 − 1.37 = 2.49pp. Day-clustered, 2,000 draws, 9,793 bets, 2,763 days |
| d_max (max drawdown) | `0.30` | founder tolerance, accepted 2026-07-30 (proposed "lose at most 30% of bank", chance 5%; B5 enforces it with probability ONE — strictly stronger) |
| min stake | 100 pence | DR-005 verified (Betfair Exchange, 7 Feb 2022) |
| k | count of same-day selected bets | matrix §4: per-bet rules "divided by a declared same-day cap"; ÷k is the perfectly-correlated treatment (DR-004 / SPEC-090: within-day ρ unmeasured, independence assumptions forbidden) |

**Threshold coupling, registered:** Δe is the displacement of the operative firing threshold
(MIN_EDGE = 0.02). If the firing threshold ever changes, Δe MUST be re-pinned from the same
sweep's corresponding row in the same change — a stale pairing is a defect. p_i is the served
model probability of the selected side (the deployed model, identical to the site).

## relevant_inputs

`p_model`, `odds`, `commission`, `delta_e`, `opening_bank_pence`, `peak_bank_pence`,
`card_size`.

## metamorphic_properties (the RED tests implement exactly these)

1. `e_i^c ≤ 0` ⇒ stake 0, for every bank, card and odds — refusal at the conservative bound.
2. Increasing Δe never increases any stake; Δe large enough zeroes the whole card.
3. Stakes scale with the bank: doubling W (HWM scaled equally) doubles each pre-cap stake
   within the 1p lattice.
4. At fixed p, shortening odds never increases the fraction (f monotone non-decreasing in b).
5. Raising p_i at fixed odds never decreases stake_i.
6. Doubling card size k halves each pre-cap stake within the 1p lattice.
7. Σ stakes over the day ≤ W − 0.70·HWM always; when 0.70·HWM ≥ W the card stakes zero.
8. From any state, an all-lose day leaves bank ≥ 0.70·HWM ≥ 0.70·W₀ — the structural floor.
9. A same-card bet below the conservative break-even never perturbs the others' stakes
   except through k (it still counts in the card size — it was selected, the correlation
   charge stands).

## The harness run (pre-declared)

Arm `D7_LCB` enters the frozen STK-HARNESS-V1 study: N_trials 13 → 14 (Bonferroni at the
true count), same paired draws, same scenarios (as-measured / half / zero / sign-reversed),
gates G1–G4, incumbent and controls unchanged. Secondary, labelled: the six-month-horizon
frontier (founder's declared horizon) re-run with the arm included.

**Pre-declared expectations, honestly:**
- G1/G2 (zero- and negative-edge survival): expected PASS **by construction** — the B5 day
  budget bounds drawdown at 30% with probability one in every scenario, so
  P(DEAD_FLOOR at 0.70·W₀) = 0 structurally.
- G3 (silent death): genuine risk on small banks — at Δe-displaced edges the fractions are
  small, and on ~£100 a k-divided stake is frequently below £1 (matrix §6.9's bank-size
  infeasibility, which no rule choice removes). Measured and reported, not hidden; the
  serving path shows skips as skips.
- Superiority over flat at α/N: NOT expected to be establishable on the historical sequence
  (|t_pair| ≤ t_edge governs the non-compounding comparison and n_eff is small for
  genuinely different rules). The adoption claim is risk-shape + founder directive, not a
  proven reward ranking — the same honest basis TE-0046 established.

## What adoption means (and does not)

Adoption = the site DISPLAYS this rule's suggested stakes for the founder-entered bank
(golden-vectored Python↔JS, exact pence), and ADR 0020's manual trial records them.
Placement remains manual and human, always; the recording flow still refuses without a
pre-set loss budget; nothing places, cancels or amends an order. No reward claim is made
until the trial's realised fills and the SPEC-081 statement exist.

## Ledger

No SPEC-ID changes. No gate evaluated by this document. Results append to TE-0047 only
after the frozen run completes; this registration is immutable once committed.

## RESULTS — the frozen run (appended 2026-07-30, after completion; registration above untouched)

Run: config sha256 `baa4f7b8fd20a94e…`, ledger 9,793 bets / 2,763 days (sha `fd0e1d18c6e0ef54…`),
1,000 paired draws × 4 scenarios × 14 arms; raw output
`tennis-edge/docs/evidence/staking/stk-harness-v1/results.json`. D7_LCB rows (pence,
start 10,000, founder floor 7,000):

| scenario | realised path | median | q05 | P(DEAD_FLOOR) | P(silent flag) |
|---|---|---|---|---|---|
| as-measured | **11,041** | 11,693 | 7,071 | **0.000** | 1.000 |
| half | 10,516 | 10,835 | 7,077 | **0.000** | 1.000 |
| zero | 9,711 | 10,040 | 7,057 | **0.000** | 1.000 |
| sign-reversed | 9,267 | 9,048 | 7,006 | **0.000** | 1.000 |

**Gates, against the frozen thresholds:**

- **G1 (floor breach at zero ≤ 0.05): PASS — 0.000.** **G2 (at sign-reversed ≤ 0.10):
  PASS — 0.000.** The pre-declared probability-one bound held EXACTLY: across all 56,000
  replayed histories in every scenario, including the sign-reversed world, the bank never
  touched the founder floor. Even the 5th-percentile final (7,006–7,077) sits above it.
  No other edge-consuming arm in the study's history has this property; the withdrawn
  CONS_KELLY breaches in 32.5–72.5% of draws.
- **G4 (clamp distortion ≤ 0.05): PASS** — the rule's own day budget makes harness-level
  clamping structurally unreachable.
- **G3 (silent death ≤ 0.10): FAIL — 1.000, exactly as pre-declared.** On the study's
  £100 bank, every history contains at least one 30-consecutive-day stretch where every
  k-divided conservative stake falls below the £1 minimum — matrix §6.9's bank-size
  infeasibility, which no rule choice removes. This is the honest cost of conservatism at
  £100: the rule protects the floor partly by not betting. On larger banks the stakes
  clear £1 far more often (six-month £200 frontier below); the page shows every skip as a
  skip.
- **Superiority over flat at α/N: NOT claimed**, per the registration — the adoption
  basis is the risk-shape result plus the founder directive (ADR 0020 Amendment 4), and
  that is what this run delivers: the only arm measured with a zero floor-breach
  probability in every scenario AND the highest realised-path finish in the study
  (+£10.41; every flat arm's realised path froze at the £70 floor).

**Scenario-semantics caveat, stated where the numbers are:** the §4.3 haircut zeroes the
EQUAL-WEIGHT per-unit mean. D7 weights stakes by conservative edge, so it retains
weighted drift under the zero scenario — its positive zero-scenario median is a property
of the scenario's declared scope, NOT evidence of edge-free profit. The admissibility
claim is the floor row, never the zero-scenario reward row.

**Standing:** the rule is adopted for display and the manual trial by founder directive
(Amendment 4); this run adds the risk-shape evidence the registration pre-declared it
would. The realised-fill edge remains unmeasured until real recorded bets settle
(SPEC-081, task #89). Six-month £200 frontier (pre-declared secondary, exploratory)
appended separately as `six-month-frontier-v2.txt`.
