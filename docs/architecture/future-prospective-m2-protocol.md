# Future-prospective M2 protocol — post-freeze combined-vs-market confirmation (Stage 2E)

**Returned for founder approval. This document authorises and implements NOTHING.** It
specifies a protocol; it does not open any stream, purchase any data, spend any alpha,
place any order, or activate any specification. The existing one-shot gate
(`specs/gates/probability-m2.yaml`) is **not** altered or discarded by this proposal.

## 0. Why this document exists (Stage 2E re-sequencing)

The programme has been re-sequenced by the founder. June 2026 is **no longer** the final
independent M2 confirmation block. Under Stage 2E, June is spent as:

- **Stage A — external M1 transfer check for F2** (the frozen affine-calibrated global
  Elo). This is a transfer/validity check, not the M2 confirmation.
- **Stage B — SPEC-032 combination-coefficient DEVELOPMENT**, entered **only if Stage A
  M1 returns PASS**: fitting `alpha, beta` for the combined probability via a nested
  chronological out-of-fold (OOF) diagnostic plus a final pooled fit.

Because June is consumed as M1-transfer evidence **and** as the SPEC-032 development block,
June can **no longer** serve as untouched, confirmatory M2 evidence: a block used to fit
and diagnose the very coefficients under test is contaminated for confirming them
(`.claude/rules/stage2-evidence-discipline.md` — "retrospective … after seeing outcomes"
is a contamination event; SPEC-031 time-respecting OOF).

Therefore the **confirmation stream for M2 becomes genuinely UNSEEN, post-freeze future
matches** — matches that occur only after the final combination model is frozen. This
document specifies that future-prospective M2 protocol.

The remaining confirmatory family-wise alpha is **0.025** (family budget 0.05; the
F3-vs-F2 confirmatory trial already spent 0.025). Under Stage 2E that **0.025 is PRESERVED
for this future M2** and is **NOT** spent on the June Stage-B development diagnostic. The
June development diagnostic reads no confirmatory alpha; it is model development, governed
by `.claude/rules/stage2-evidence-discipline.md`, not a gate.

## 1. Purpose and the primary comparison

**Purpose.** Confirm whether the **pre-fitted combined probability** adds predictive
information **beyond the governed Betfair market probability**, on genuinely **UNSEEN,
post-freeze** tennis matches.

- **Combined probability (candidate):** the SPEC-032 stage-two output,
  `c = softmax(alpha·log p_fundamental + beta·log p_market_info)` within the match choice
  set, with `alpha, beta` fitted on June (Stage B) and then **frozen**;
  `p_fundamental` = the final affine-calibrated F2; `p_market_info` = the governed Betfair
  committed price (info-price-v2).
- **Baseline:** market-only `p_market_info` (the governed Betfair F0 committed price).
- **Primary comparison:** market-only `p_market_info` vs the pre-fitted `p_combined`. This
  is combined-vs-market, exactly as in `specs/gates/probability-m2.yaml` — **not**
  standalone-fundamental-vs-market. A fundamental model that merely re-derives the market
  adds nothing; the test is whether SPEC-032 blending improves on the market alone.
- **Endpoint (per match):**

  ```
  d_i = ll_market - ll_combined
      = ln p_combined(winner) - ln p_market(winner)
  ```

  read on the **actual winner**. `d_i > 0` means the combined model beat the market on that
  match. This is exactly `l8_evidence.paired_inference.PairedRace` with `p_market_winner`
  and `p_combined_winner`; `d_r` is computed there (`PairedRace.d_r`). No new endpoint
  arithmetic is introduced — the existing, tested SPEC-090 code is the endpoint.

This confirmation licenses **nothing** about live trading, EV, staking, ROI, CLV, or
profitability. The ADR 0015 block stands regardless of outcome.

## 2. Frozen inputs — may NEVER change during the evidence phase

The moment the future confirmation stream begins, every one of the following is a **frozen
artefact**. If any of them changes between the freeze and any read of the evidence, the
sequential validity is **void** and the trial is burned. This is the hard invariant of any
always-valid procedure: every appended future match is scored by the **same** frozen
artefacts.

| Frozen input | Frozen value / policy |
|---|---|
| F2 global Elo model | the final global-Elo artefact (model version pinned at freeze) |
| Affine calibration | calibration-policy-v2 — ATP intercept `0.025399`, temperature `1.218638`; WTA intercept `0.029204`, temperature `1.150681` |
| F0 price method | info-price-v2, `COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE`, `W = 60s`, `L = 300s` |
| SPEC-032 coefficients | `alpha, beta` as fitted on June (Stage B) and frozen — the pooled final fit, pinned by digest |
| Identity policy | the frozen player/match identity resolution policy |
| Eligibility policy | the frozen match-eligibility / intersection policy |
| Benchmark | the frozen adapter-declared benchmark (no non-racing closing benchmark is selected; SPEC-095) |

**No model updates, no calibration updates, no coefficient updates, no eligibility change,
no benchmark change** during the evidence phase. No automatic live learning (CLAUDE.md hard
prohibition): a change to any of the above is a new immutable version, a new gate
evaluation, and human approval — it does **not** continue the same sequential test. Each
frozen artefact is digest-pinned in the experiment record before the first future match is
scored.

## 3. The evidence unit and how blocks accrue

- **Evidence unit:** one **future match** (the tennis market choice set — the match, never
  the selection; SPEC-090, `.claude/rules/evidence.md`), reduced within its **UTC-calendar-day
  cluster**, the tennis correlation-cluster key (SPEC-090). Selection-level independence is
  forbidden.
- **Within a block:** the per-day clusters are the resampling/summary unit — exactly
  `l8_evidence.paired_inference.block_bootstrap_ci` clustered by UTC calendar day. A single
  cluster-day cannot estimate between-day variation and is refused
  (`InsufficientMeetingDaysError`), never silently degraded.
- **Blocks accrue chronologically.** A block is a contiguous future window (e.g. one
  calendar month). Blocks enter the accumulating evidence strictly in time order; a match is
  never moved to a different day's cluster and a day is never split across blocks.
- **Frozen universe / exclusion funnel.** Each block's eligible universe is frozen before
  its outcomes are known; every excluded match stays in the funnel with a typed,
  knowledge-time reason (`.claude/rules/evidence.md`; SPEC-038). Missing predictions are
  abstentions in the denominator, never silent drops.

## 4. Two candidate statistical designs (founder chooses)

The fuller A-vs-B treatment and the power reality are in
`docs/architecture/m2-alpha-preservation-review.md`. Both designs test the **same**
combined-vs-market endpoint on the **same** UTC-day-clustered unit, spend the **same** total
confirmatory alpha **0.025**, and honour the **same** frozen inputs (§2). They differ only in
how the future evidence is accumulated and when it may be read.

Power reality (from the alpha-preservation review): at the planning `sigma_d ~ 0.04075` and
`delta = 0.0007` nats, a decisive fixed-sample one-sided test needs `~ 32,212` paired
decision units. At `~ 1,000` scorable combined-vs-market matches per month, that is
`~ 31` comparable months to reach fixed-sample power for an effect as small as `delta`; an
always-valid procedure pays a modest additional penalty on top. Neither design manufactures
power the data volume does not contain — they resolve **sooner** only if the true effect is
**larger** than `delta`.

### Design (a) — pre-registered FIXED-horizon one-shot

- A single future window with **N and the window pre-committed BEFORE any match in it is
  scored** (SPEC-094 pre-registration; no peeking, no optional stopping).
- Inference: the existing `l8_evidence.paired_inference.block_bootstrap_ci` clustered
  bound, evaluated once by the SPEC-093 deterministic evaluator against the frozen
  boundaries (`delta = 0.0007`, one-sided `97.5%` lower bound, `alpha_charge = 0.025`).
- **Engineering cost: near-zero** — this reuses the existing tested clustered bootstrap and
  the existing gate machinery; it is the future-window analogue of the current
  `probability-m2.yaml` one-shot.
- **Cost of the simplicity:** N and window must be fixed in advance; a single underpowered
  window is expected to return CONTINUE / INCONCLUSIVE, and once resolved the 0.025 is spent
  — no further look is licensed without a newly governed programme and a multiplicity reset.

### Design (b) — ANYTIME-VALID sequential (testing-by-betting)

- An **e-process / confidence sequence** on the day-clustered paired endpoint: a
  non-negative test supermartingale whose running product of per-block e-values yields an
  **always-valid** level-`alpha` test, **valid under optional stopping and optional
  continuation** (Ville's inequality). "Peek after each block and stop when convincing" does
  not inflate `alpha`.
- **Alternative anchor:** `delta = 0.0007` nats — the e-value is built to grow fastest when
  the true improvement is `~ delta` (a GRO / mixture construction against
  `H0: mean improvement <= 0`; the exact construction is registered before the first look).
- **PASS boundary:** e-process `>= 1/alpha = 40` for `alpha = 0.025`, on the
  improvement side.
- **FAIL_HARM:** a **symmetric** harm e-process crossing on the degradation side.
- **FAIL_FUTILITY:** a **registered** futility rule — a max-blocks cap and/or a
  projected-information rule that shows `delta` is effectively excluded — reached without
  crossing PASS.
- **Between-block accumulation:** each future block (e.g. a month) contributes one e-value
  computed from its UTC-day-clustered statistic; the process is the product across blocks in
  chronological order. Both the within-block clustering and the between-block product are
  registered before the first look.
- **Engineering cost: material and money-critical.** **SPEC-096 (anytime-valid monitoring)
  is currently registered `planned` and UNIMPLEMENTED.** Design (b) therefore requires:
  1. a **money-critical implementation slice** (`l8_evidence`) — the e-process /
     confidence-sequence producer, its per-block clustered reduction, determinism + replay
     tests, and mutation coverage — built to the three rules (no stubbing, no test
     weakening, no LLM in the numerics; CLAUDE.md); and
  2. a **SPEC-096 activation**, which is a **human-controlled specification change**
     (`planned -> active`), not a config tweak.

  Until both land, design (b) cannot be run. The SPEC-093 evaluator already carries the
  `anytime_valid_bounds_v1` **contract** in `specs/gates/v1.yaml`, but the producer behind
  it does not yet exist.

## 5. Shadow-only start and the reporting contract

- The future stream begins **ONLY after the final combination model is frozen** (F2 +
  calibration-policy-v2 + info-price-v2 + the June-fitted `alpha, beta`, all pinned per §2).
- The stream is **SHADOW-ONLY**: no orders, no stakes, no execution, no account activity of
  any kind. It scores probabilities against realised match results and nothing more. (This
  is a probability-evidence stream; ADR 0013 analytics read-only posture and the CLAUDE.md
  no-in-play / back-only / ADR-0015 blocks all remain in force and are untouched by it.)
- **The stream MUST report:**
  - market-only vs combined **paired log score** on the actual winner (the SPEC-090
    endpoint, per match and aggregated per block);
  - **cluster-aware or anytime-valid uncertainty** — the UTC-day-clustered block-bootstrap
    interval (design a) or the e-process value / confidence sequence (design b);
  - **coverage** — matches scored vs eligible, with the full typed exclusion funnel;
  - **calibration transfer** — choice-set-level calibration-in-the-large and slope on the
    post-freeze stream (SPEC-097), to show the frozen calibration still holds out of sample;
  - **operational refusals** — every abstention, single-cluster refusal, identity/eligibility
    refusal, or frozen-artefact-mismatch, with a knowledge-time reason.
- **The stream MUST report NONE of:** ROI, P&L, CLV (any flavour), EV, stake, selection,
  betting recommendation, or profitability. This is a **hard prohibition** during the
  evidence phase (`probability-m2.yaml` `excludes`; `.claude/rules/evidence.md`;
  `.claude/rules/stage2-evidence-discipline.md`; CLAUDE.md). CLV is a diagnostic family and
  never a training target; none of these quantities may steer, or even annotate, the
  confirmation.

## 6. Stopping rules and exact alpha accounting

**Outcomes (both designs; never a boolean — `.claude/rules/evidence.md`):**

- **PASS** — combined beats market by `>= delta = 0.0007` nats with a strictly positive
  clustered lower bound (design a) / the e-process crosses `1/alpha = 40` on the improvement
  side (design b). Licenses nothing about trading (ADR 0015 stands).
- **CONTINUE** — plausible but not demonstrated: the interval includes zero, or the
  accumulated future evidence is too small / too wide to resolve. INCONCLUSIVE lives here.
  For design (b), more founder-approved blocks may be appended. For design (a), the
  pre-committed window is simply reported as CONTINUE.
- **FAIL_HARM** — material degradation (combined worse than market): the one-sided upper
  bound below the harm threshold `0.0` (design a) / the symmetric harm e-process crosses
  (design b); or any governance item false.
- **FAIL_FUTILITY** — the registered futility rule excludes an improvement as large as
  `delta` (design a: upper bound `< 0.0007`; design b: the registered max-blocks /
  projected-information futility rule fires without a PASS crossing).

**Exact alpha accounting.** The confirmatory charge is **0.025**, and multiplicity is taken
against the **one prior confirmatory trial** (F3-vs-F2), exactly as in the frozen one-shot
gate (SPEC-091):

```
(1 - confidence_level) * (number_of_prior_trials + 1)
    = 0.025 * (1 + 1) = 0.05 = alpha_budget_total   OK (family exhausted at that charge)
```

- Design (a) spends the 0.025 **once**, on the pre-committed future window.
- Design (b) spends the **same** total 0.025 across the whole sequential procedure — the
  always-valid guarantee (Ville) controls type-I error at `alpha` **simultaneously for all
  stopping times**, so appending blocks does **not** re-charge alpha per look. The 0.025 is
  the whole-procedure budget, not a per-block charge.
- `delta`, the confidence level, the clustering, and the seed / e-process construction are
  **pre-registered and frozen before observation**; they MUST NOT be changed to force a PASS
  or a FAIL. Doing so voids the trial (SPEC-094; `probability-m2.yaml` `underpowering_note`).

**Data acquisition.** Future months are **individually founder-approved, one month at a
time, no bulk**. Per the founder's spending policy, **no further historical purchase is
authorised merely for sample size**. The sequential procedure may stop for PASS, FAIL_HARM,
FAIL_FUTILITY, or budget / max-blocks exhaustion; it never implies a standing purchase
commitment.

## 7. Governance

- **Approval-before-start.** The exact statistical method (design a or design b), and — for
  design b — the exact e-process construction, PASS/HARM/FUTILITY boundaries, max-blocks cap,
  and per-block reduction, must be **returned for founder approval BEFORE the future stream
  starts**. Nothing accrues, and no artefact is frozen for confirmation, until that approval.
- **The existing one-shot gate is retained.** `specs/gates/probability-m2.yaml` stays intact
  and is **not** discarded by this proposal. If founder chooses design (a), the future-window
  one-shot is its natural continuation; if founder chooses design (b), the one-shot gate
  remains on record and design (b) is added under a SPEC-096 activation. `specs/**` is
  CODEOWNERS human-owned; a founder veto voids this record.
- **specs are frozen against the evidence they judge (Rule 2).** The gate structure and the
  future evidence it is evaluated on never change together. Any change to the frozen inputs
  (§2), the boundaries (§6), or the method (§4) is a new pre-registration and a new gate
  version, never an in-place edit.
- **No LLM in the numerics or the gate.** No LLM estimates a probability, prices, sizes,
  smooths, repairs, or decides any outcome here (CLAUDE.md three rules; SPEC-093). Every
  numerical decision comes from deterministic, tested, replayable code — for design (b), that
  code does not yet exist and must be built to the money-critical bar and independently
  verified by CI (`make verify` / `make mutants` / `make replay`) before it can gate.

---

**This protocol is a PROPOSAL. It is not implemented and the future stream does not start
until the final combination model is frozen AND the founder approves the exact sequential
method and stopping rules. No confirmatory alpha is spent by this document.**
