# Proposal: targeted procurement of May 2026 Betfair tennis market data (SPEC-032 alpha/beta training block)

**Status:** PROPOSAL — returned for founder review. Authorises nothing. Requests no purchase.
**Type:** ADVISORY (data-procurement proposal; not a Deep Research handoff).
**Date drafted:** 2026-07-18
**Related:** SPEC-032 (stage-two market combination), SPEC-031 (time-respecting cross-fitting),
SPEC-021/SPEC-095 (benchmark/closing taints), SPEC-092 (June lockbox), SPEC-101/SPEC-103
(licensing + budget separation), ADR 0015 (Betfair account-activity block).

---

## Purpose (what this block is for, and what it is not)

The programme has selected **F2 global Elo** as its fundamental model (F3 surface Elo closed
`FAIL_HARM`). Fundamental probabilities are calibrated via affine-logit
(`calibration-policy-v2`).

The central open question at **M2** is **not** "does F2 beat the market standalone." It is
whether the **pre-fitted COMBINED probability** — SPEC-032's softmax of
`alpha*log(p_fundamental) + beta*log(p_market_info)` — adds predictive information **beyond**
the governed Betfair market probability `p_market_info`.

Fitting that 2-parameter combination requires a **pre-June** dataset carrying **both**:

1. an honest out-of-sample **F2 fundamental probability**, and
2. a **governed Betfair `p_market_info`** produced at the **frozen operational policy**
   (`COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE`, dwell `W = 60s`, max nominal lead `L = 300s`;
   info-price definition `info-price-v2`, implied-midpoint).

**No existing pre-June dataset has both.** The pre-June evaluation corpus has F2 but no
purchased Betfair prices (see `docs/architecture/baseline-availability-and-gate-roles.md`:
Betfair `p_market_info` "DOES NOT EXIST" pre-June). Tennis-Data bookmaker odds are
**quarantined** and are never a proxy for the Betfair baseline.

This purchase exists **only to build the SPEC-032 alpha/beta training block**. It is **not**
an attempt to spend the June M2 alpha, and it does **not** touch the sealed June lockbox.

**June 2026 is the sealed lockbox (SPEC-092).** It must not be opened, purchased, inspected,
or used to fit alpha/beta. Any June access burns the lockbox.

## Default recommendation (one line)

Purchase **Betfair historical data, "Betfair Tennis ADVANCED" tier, month of MAY 2026,
`MATCH_ODDS` markets, singles only — ONE month only. No bulk order, no 12-month order.**

---

## The founder's required 10 return items

### 1. Exact Betfair historical-data portal selections

| Field | Selection |
|---|---|
| Data product | Betfair Historical Data (official downloadable historical exchange stream) |
| Tier / plan | **Tennis ADVANCED** |
| Sport | **Tennis** |
| Market type | **`MATCH_ODDS`** only |
| Month | **May 2026** (2026-05-01 → 2026-05-31 inclusive, UTC) |
| Event type | **Singles only** (exclude doubles; exclude non–Match-Odds tennis markets such as set/game/handicap where separable at the portal filter) |
| Region / competition filter | No region restriction at purchase — take the full month's tour-level + lower-tier `MATCH_ODDS` as the tier delivers; singles restriction applied at ingestion where the portal cannot pre-filter |
| Format | Native Betfair historical stream archive (the ADVANCED tier's per-market recorded stream files), pre-off segments retained; **pre-off use only** |

Rationale for `MATCH_ODDS` only: it is the mutually-exclusive two-selection choice set the
platform prices (SPEC-030/SPEC-054), and the only market the F0 state machine and F2
fundamental are defined against.

### 2. Current price as advertised

**[[ PLACEHOLDER — founder to confirm at the live Betfair historical-data portal at request
time ]]**

No figure is fabricated here. The Betfair historical portal prices per sport, per tier, per
month, and the ADVANCED tier price is confirmed only at the portal. The founder must read the
live per-month ADVANCED tennis price and enter it here before any approval. **Estimate basis
(outcome-blind):** a single-month ADVANCED single-sport order is the smallest purchasable
unit; the cost is the advertised one-month line item — **not** a 12-month or bulk multiple.

### 3. Expected raw market count for the month (order-of-magnitude estimate)

**Estimate: order of ~2,000–3,500 `MATCH_ODDS` singles markets for May 2026.** *(ESTIMATE —
order of magnitude only, cannot be known exactly without purchase.)*

Basis: May is a dense tour-level tennis month (full clay swing, ATP + WTA), and the observed
June 2026 corpus held **2,876** raw markets (`docs/evidence/tennis-data-2026-07-18/`). May's
calendar density is comparable to June's, so a similar order of magnitude is expected. The
actual count depends on **tier coverage**: ATP + WTA **tour-level** singles are the core;
**Challenger / ITF** depth is included only to the extent the ADVANCED tier records those
lower-tier markets. Treat the figure as an order-of-magnitude planning number, not a
committed count.

### 4. Expected Tennis-Data identity coverage

Reference — observed **June 2026** coverage (`docs/evidence/tennis-data-2026-07-18/`):
- both-players-mapped: **1,218 / 2,876 = 42.4%**
- strict mapping: **50.5%**

**Estimate for May 2026:** *similar* coverage for **tour-level** matches (ATP/WTA main draws
map well through the `td-norm-v1` bridge), and **lower** coverage for lower-tier
(Challenger/ITF) matches, where Tennis-Data identity mapping is sparser. *(ESTIMATE by
analogy to June; true coverage is knowable only after ingest.)* Tennis-Data is used for
**identity only** — never for odds (see item 9).

### 5. Expected F2/F0 join count

The usable training rows are markets carrying **both** a committed F0 `p_market_info` **and**
an F2-emittable fundamental probability.

Reference — the analogous **June** intersection was **1,027 / 2,876 ≈ 36%**.

**Estimate for May 2026:** a **similar proportion (~36%)** of the raw May market count, i.e.
**order of ~700–1,300 joined markets** on the ~2,000–3,500 raw estimate above. *(ESTIMATE —
the true intersection depends on realised identity coverage, F0 commit rate under the frozen
policy, and F2 emittability; knowable only after ingest.)* This is the count that actually
feeds the deterministic SPEC-032 MLE.

### 6. Tournament / tour / surface composition for May 2026 (calendar fact)

May 2026 is the **European clay swing** (calendar fact, outcome-blind):
- **ATP + WTA** tour-level events: **Madrid**, **Rome**, plus **Geneva**, **Lyon**
  (ATP 250), and **Strasbourg** (WTA) in the run-up week.
- **Roland Garros** (clay Grand Slam) **begins ~late May** (main draw typically starting the
  final week of May, running into June).
- Surface: **predominantly clay** across the month.

This is stated as calendar composition only — no outcome or performance signal is involved.

### 7. Why this month is suitable for fitting SPEC-032 alpha/beta

- **Recent regime.** May 2026 reflects current player form, liquidity and market behaviour —
  the same regime the June evaluation runs in.
- **Immediately pre-June.** The operational policy
  (`COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE`, `W=60s`, `L=300s`, `info-price-v2`) and the
  liquidity/microstructure profile match the June evaluation block as closely as any month
  can, so alpha/beta are fit on comparable conditions.
- **Enough tour-level matches** (item 5 estimate) for a **deterministic 2-parameter MLE** —
  alpha and beta over `log p_fundamental` and `log p_market_info` is a small, well-posed fit;
  a few hundred joined choice sets is workable (with wide uncertainty, item 8).
- **Distinct from June** — a different calendar month, so fitting on it introduces **no
  lockbox contamination** (SPEC-092) and no SPEC-031 time-respecting violation for the June
  evaluation.

### 8. Known limitations (including Grand Slam concentration)

- **Roland Garros concentration (late May).** Introduces a **best-of-5 men's-singles
  regime** distinct from best-of-3, and a **large correlated cluster** of matches on **few
  calendar days**. Under the tennis correlation-cluster key (UTC calendar day, SPEC-031/
  SPEC-090), this concentrates weight on a handful of clusters and inflates within-cluster
  correlation for that stretch.
- **Clay-surface concentration.** May is predominantly clay, so **surface diversity is
  limited** — alpha/beta are fit largely on clay-regime data. (F2 is a global Elo, so this is
  a data-composition caveat, not a surface-model dependency; F3 surface Elo already closed
  `FAIL_HARM`.)
- **Single-month sample.** One month means **alpha/beta uncertainty will be wide.** The fit
  is usable but the parameter confidence region is broad; this is disclosed, not tuned away.
- **Lower-tier identity coverage gaps.** Challenger/ITF matches map less reliably through
  `td-norm-v1`, so the joined block skews tour-level (items 4–5).
- **Order-of-magnitude counts.** Items 3–5 are estimates; the realised joined count could
  land below the planning range and further widen alpha/beta uncertainty.

### 9. Checksum + ingestion runbook

On receipt (deterministic, retain-everything):

1. **Checksum first.** Record **SHA256 of every delivered file** into a `MANIFEST.sha256`
   before any parsing.
2. **Vintage-stamped raw store.** Place the untouched archive under a vintage-stamped raw
   directory (e.g. `docs/evidence/betfair-may-2026-<ingest-date>/raw/`), append-only, never
   mutated (SPEC-001 spirit: persist bytes exactly as received).
3. **Parse pre-off only.** Parse the **`MATCH_ODDS` pre-off book only**. No in-play segment
   is used (hard prohibition: pre-off only, every sport).
4. **Frozen F0 state machine.** Run the frozen F0 `COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE`
   commit machine (`W=60s`, `L=300s`, `info-price-v2` implied-midpoint) to emit
   `p_market_info` exactly as June — no policy variation.
5. **Identity join.** Join identities via the **`td-norm-v1`** Tennis-Data bridge —
   **identity only**.
6. **Retain refusals/exclusions.** Every refusal, non-commit, and exclusion is recorded with
   a reason at knowledge-time (frozen universe; missing data becomes an explicit exclusion,
   never a disappearance).
7. **Never read Tennis-Data odds columns.** Tennis-Data odds fields stay **quarantined** —
   never read, scaled, blended, or substituted into `p_market_info` (baseline-availability
   doc; SPEC-021/SPEC-095 taint discipline).
8. **Per-market manifest.** Produce a per-market F0 / eligibility manifest **exactly like the
   June F0/eligibility manifests**, so the May block is directly comparable in structure (not
   in outcomes) to June.

### 10. Explicit confirmation of outcome-blind month selection

**The month selection used no outcome, no return, and no model-performance signal.** May 2026
was chosen purely as **"the calendar month immediately before the sealed June lockbox"** — a
single, **outcome-blind, pre-registered** criterion fixed before any data was seen. No May
result, price movement, or fitted alpha/beta value influenced the choice, and none could,
because the data is not yet in hand.

---

## If May is unsuitable from metadata alone

If May's metadata (e.g. Roland Garros best-of-5 concentration, clay-only surface, or a
lower-than-expected joined count) makes it unsuitable, propose **ONE** alternative pre-June
month:

**April 2026.**

- **Composition (calendar fact):** mixed **hard → clay** transition — **Monte Carlo**,
  **Barcelona**, **Munich**, and the **Madrid** start (ATP), with **Charleston** (clay) and
  **Stuttgart** (WTA) on the women's side.
- **Outcome-blind reason:** still **immediately recent / same regime**; **more surface
  diversity** (hard and clay, not clay-only); and **no Grand Slam best-of-5 regime** and no
  single large late-month correlated cluster.

**Only ONE month is proposed** — April as the sole alternative to May. **Never a 12-month or
bulk order.**

---

**NO PURCHASE IS AUTHORISED BY THIS DOCUMENT. It is returned for founder approval; the exact
portal order + confirmed price must be approved before any spend (SPEC-101/103; ADR 0015
blocks all Betfair account activity including data purchase while it stands).**
