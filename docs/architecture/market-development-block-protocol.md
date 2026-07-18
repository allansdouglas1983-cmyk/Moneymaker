# Market-development block protocol — SPEC-032 training-corpus production

**Status:** PREPARATION ONLY. This document defines a protocol to be executed LATER,
**only after** the founder approves the targeted pre-June market-data purchase
(`docs/research/requests/advanced-may-2026-market-procurement-proposal.md`). It executes
nothing now, spends no budget, buys no data, reads no June data, and fits no model. It is
the step-by-step recipe by which each eligible match in the purchased **pre-June
market-development month (default May 2026)** becomes one SPEC-032 training row carrying
BOTH an honest fundamental F2 probability AND a governed Betfair `p_market_info`.

**Scope of what this block does — and only this.** It PRODUCES the SPEC-032 combination
training corpus (`§6`). It trains alpha/beta on nothing; fitting is a separate, later,
human-registered step (`spec032-combination-registration-v1.yaml`,
`l4_pricing.stage_two.fit_stage_two`). This is **development data** — it spends **no
confirmatory alpha** and touches **no lockbox** (June 2026 remains sealed, SPEC-092).

**Why a dedicated block exists.** The June F0 run (`docs/evidence/stage2b-f0-f2-runs/`)
produced a governed Betfair market yardstick but recorded *no market-relative claim: no
Betfair baseline exists pre-June*, so alpha/beta (SPEC-032) has never had a corpus that
pairs an honest fundamental with a real Betfair information price on the SAME market
without touching the sealed June universe. A purchased pre-June market month supplies
exactly that pairing, entirely before the `2026-06-01` boundary, so the combination can be
fitted as development without spending the June confirmatory budget.

---

## 0. Preconditions (all must hold before any step runs)

1. **Founder approval on record** for the targeted market-data purchase, with the rights
   registry (SPEC-044 / Gate -1, SPEC-101) recording per-use permission covering *model
   training* and *offline research* for the Betfair pre-June market data. Absent rights,
   the block does not run (fail closed).
2. **Vintage frozen.** The purchased market data is byte-preserved under its own
   `raw/vintage-<YYYY-MM-DD>/` with a sorted `MANIFEST.sha256` and `PROVENANCE.json`,
   mirroring `docs/evidence/tennis-data-2026-07-18/` discipline (provider change ⇒ NEW
   vintage, never overwrite).
3. **Boundary.** Every match in scope has its event date strictly **before 2026-06-01**.
   The default development month is **May 2026**; any purchased pre-June month is
   admissible on the same terms. A single post-boundary row is COUNTED-NEVER-READ, never
   silently dropped.
4. **Frozen policy artefacts pinned by version string** (no re-tuning inside this block):
   - F0 decision policy: `COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE`, `W = DWELL_SECONDS = 60 s`,
     `L = MAX_NOMINAL_LEAD_SECONDS = 300 s`, `reschedule-policy-v1`
     (`sport_tennis/market_yardstick.py`).
   - Info price: `info-price-v2` (implied midpoint of best back/lay, normalised over the
     two active selections; scope `betfair MATCH_ODDS`).
   - Identity: `td-norm-v1` (`sport_tennis/identity_bridge.py`,
     `NORMALIZATION_VERSION = "td-norm-v1"`).
   - Fundamental: the F2 selection frozen at F2 registration — Design B chronology,
     per-tour ratings `td-atp` / `td-wta`, K from the F2 registration selection rule
     (ATP K=24 / WTA K=32 as selected in `EXP-STAGE2-F2-GLOBAL-ELO-001`), label-policy-v1
     completed-only, and `calibration-policy-v2` affine map.

If any precondition is unmet, the block STOPS and reports which precondition is blocked
(the three rules: never ship a degraded version of a money/evidence-critical step).

---

## 1. Reconstruct the F0 `p_market_info` (governed Betfair information price)

For each eligible match's pre-off Betfair `MATCH_ODDS` book, replay the FROZEN as-of-
`marketTime` state machine exactly as June F0 did — **no re-tuning, same code path**:

1. Build the per-market pre-off timeline of `MarketTimelineEvent` records (publish time
   `pt_ms`, schedule-as-known-then `market_time_ms`, `status`, `inplay`, best-back and
   best-lay tick/size per selection). The input type carries prices/schedule/status ONLY;
   winners, settlement, P&L and CLV are structurally absent, so F0 cannot read an outcome.
2. Run `commit_once_decision(timeline, first_inplay_pt_ms=…)`:
   - Commit the **one** decision at the first admissible `t` where status is `OPEN`,
     pre-in-play, remaining lead `market_time_ms − t ∈ [0, L]`, and the dwell `W` has
     elapsed since the last `marketTime` revision (a revision inside the dwell resets it).
   - `COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE`: exactly one committed decision per market;
     later `marketTime` revisions **hold** (never re-decide) and are counted in
     `post_commit_revision_count` per `reschedule-policy-v1`.
3. At the committed `t`, compute `p_market_info` from the two-sided book via
   `market_probabilities_from_book` — `info-price-v2`: per selection
   `raw_p = (1/best_back + 1/best_lay)/2` on the canonical integer ladder
   (`price_contracts.ladder.price_of`; **tick index is integer, never float**), normalised
   to unit sum over the two active selections.
4. **Retain refusals as typed decisions, not gaps.** A market with no admissible window
   records `NO_VALID_COMMIT_WINDOW`; a market whose committed instant lacks a two-sided
   two-selection book records `NO_TWO_SIDED_BOOK_AT_COMMIT` (also `EMPTY_TIMELINE`). Both
   the committed and refused outcomes are decisions and both stay in the denominator (`§4`).

Each committed market yields `decision_digest`, `book_state_digest`,
`commit_pt_ms`, `market_time_ms_at_commit`, `post_commit_revision_count`, and
`p_market_by_selection`, identical in shape to
`docs/evidence/stage2b-f0-f2-runs/F0_MARKET_YARDSTICK_MANIFEST.jsonl`.

---

## 2. Generate an HONEST prequential F2 fundamental prediction (leakage-safe by construction)

For each eligible match, produce `p_fundamental` from F2 with **no path by which a match's
own outcome, or any same-or-later data, can influence its probability**:

1. **Expanding-window prequential Elo.** F2 is the frozen expanding-window Elo
   (`sport_tennis` Elo family) trained ONLY on data strictly **before the match date**.
   Ratings for the match are the state accumulated from prior matches only; the match's
   result is applied to the ratings **after** its probability has been emitted, never
   before. No match ever contributes to its own rating input.
2. **Per-tour independent ratings.** `td-atp` and `td-wta` ratings evolve separately (no
   pooling in v1 — pooling is a governed change with its own evidence). K is **frozen from
   the F2 registration selection rule** (K=24 ATP / K=32 WTA); this block re-selects
   nothing on K.
3. **Cold-start honesty.** A player enters scored evaluation only with ≥ the F2-registered
   minimum prior corpus matches; otherwise the match is an explicit abstention with a
   typed reason (`§4`), not a guessed probability. New players use namespace-mean
   initialisation, provisional until the minimum is met.
4. **Final calibration uses only prior authorised data.** The affine map
   (`calibration-policy-v2`: `z_cal = intercept + z / temperature` in logit space) is
   applied to the raw F2 probability. Its `(intercept, temperature)` parameters are those
   fit on **prior authorised pre-development data only** — they must **not** be fit on, or
   on-or-after, the match being predicted, and never on any May/pre-June development match
   whose probability they calibrate in a way that could see that match's outcome. Fold-safe
   by construction (the F2 crossfit/OOF seam owns fold assignment); the affine slope is
   refused if non-positive.
5. **The stored fundamental is the affine-calibrated `p_fundamental`.** Both raw and
   calibrated values may be recorded for diagnostics, but the corpus row (`§6`) carries the
   affine-calibrated probability as the SPEC-032 fundamental input.

**Leakage-safe statement.** Because (a) ratings feeding the prediction come only from
matches strictly earlier than the predicted match, (b) K and the design are frozen
pre-block, and (c) the calibration parameters are fit only on prior authorised data,
**no match outcome influences its own probability, and no future or contemporaneous
outcome influences it either.** This is leakage-safe by construction, not by inspection —
consistent with SPEC-020/021/023/031 and `.claude/rules/stage2-evidence-discipline.md`.

The odds-free F2 pipeline reads **no bookmaker odds columns** at any point (`§5`).

---

## 3. Join fundamental to market by GOVERNED identity

A market becomes a corpus row only when the fundamental and the Betfair market resolve to
the **same governed identity** and F0 committed:

1. Resolve both players through the identity bridge (`sport_tennis.identity_bridge`,
   `td-norm-v1`: NFKD diacritic strip, casefold, space-collapse) against the purchased
   market's Betfair runner names. Namespaces stay distinct — ATP ⇒ `td-atp`, WTA ⇒
   `td-wta` — carried as a namespaced `CompetitorId` (`sport_core.competitors.CompetitorId`).
2. **Homonym refusal.** A `HOMONYM_MULTIPLE_BETFAIR`, `HOMONYM_MULTIPLE_SOURCE`, or
   `CROSS_NAMESPACE_AMBIGUOUS` case is refused with its typed `UnresolvedReason`, never
   guessed.
3. **Frozen correction ledger.** Identity corrections come ONLY from the existing
   append-only governed correction ledger (`load_correction_ledger` / `apply_corrections`).
   This block adds **no new guessed corrections**; a genuinely new correction is a separate
   human-approved ledger change, out of scope here.
4. **Join condition.** A market joins the corpus iff **both players resolve** to a
   `CompetitorId` AND F0 **committed** (`§1`) AND F2 emitted a scored (non-abstained)
   fundamental (`§2`). Any market failing any clause is an explicit exclusion (`§4`),
   never a silent drop.

---

## 4. Retain every refusal and exclusion, in the denominator (SPEC-038 discipline)

Nothing is silently dropped. Every eligible market produces exactly one manifest record —
either a corpus row or a typed exclusion — and both remain in the denominator:

- **F0 refusals:** `NO_VALID_COMMIT_WINDOW`, `NO_TWO_SIDED_BOOK_AT_COMMIT`, `EMPTY_TIMELINE`.
- **Identity exclusions:** `EXCLUDED_IDENTITY:NO_SOURCE_MATCH`, homonym reasons,
  cross-namespace ambiguity.
- **F2 exclusions:** cold-start below the prior-match minimum; label-policy exclusions
  (WALKOVER, ABANDONED, SCHEDULED, AMBIGUOUS — no play signal / no declared winner);
  duplicate/conflicting-winner rows per the frozen acceptance-audit policy.
- **Boundary exclusions:** any post-`2026-06-01` row COUNTED-NEVER-READ.

**Manifest.** Produce a per-market JSONL manifest mirroring the June artefacts
(`docs/evidence/stage2b-f0-f2-runs/F0_MARKET_YARDSTICK_MANIFEST.jsonl` and
`docs/evidence/tennis-data-2026-07-18/JUNE_F2F3_ELIGIBILITY_MANIFEST.jsonl`), one record
per market carrying at least: `market_id`, `cohort`, `source_vintage`, `identity_policy`,
`label_policy`, F0 fields (`committed`, `commit_pt_ms`, `market_time_ms_at_commit`,
`post_commit_revision_count`, `decision_digest`, `book_state_digest`,
`p_market_by_selection`, `policy`, `price_method`, `refusal_reason`), the resolved
`CompetitorId` per selection (or unresolved reason), `f2_scored` / `f2_abstain_reason`,
`both_mapped`, `corpus_row_emitted` (bool), and the typed `reason` when not emitted. Emit a
`_SUMMARY.json` (counts of committed / refused-by-type / excluded-by-type / rows emitted)
and a `DIGESTS.txt` over every produced artefact, exactly as the June run did.

---

## 5. Never use Tennis-Data bookmaker odds columns

The fundamental pipeline is **odds-free everywhere**. Tennis-Data bookmaker odds columns
(catalogued by name/null-count and QUARANTINED at acceptance) MUST NOT be read by F2, by
calibration, by identity resolution, by eligibility, or by corpus assembly. The **only**
market probability in this block is the Betfair-derived F0 `p_market_info` (`§1`). This is
enforced by the existing outcome/field classification and quarantine discipline
(`docs/evidence/tennis-data-2026-07-18/`), not by convention.

---

## 6. Output — the SPEC-032 training corpus (produce only; fit later)

The block emits the SPEC-032 combination corpus: one row per joined market
(`§3` join condition met), each row carrying:

- `race_id` — the market's decision-unit id (the tennis match choice set of exactly two
  mutually exclusive selections);
- `p_fundamental` — the **affine-calibrated** F2 probability per selection, a float in
  `(0, 1)` summing to 1 across the two active selections, carried as a provenance-bearing
  out-of-fold fundamental (`l4_pricing.crossfit.OOFFundamental`) so SPEC-031 re-verifies
  out-of-fold-ness at consumption;
- `p_market_info` — the F0 `info-price-v2` probability per selection **typed as
  `price_contracts.prices.MarketInfoPrice`** (never a bare float, never a close price);
- `winner` — the settled winning selection of the match, read ONLY for the pre-June
  development corpus (never a June/lockbox row), used solely as the MLE label.

These rows are consumed ONLY by the later, separately registered fitting step
(`spec032-combination-registration-v1.yaml`) which calls
`l4_pricing.stage_two.fit_stage_two(races, oof, market_prices, horizon=…)` to fit
`(alpha, beta)` by deterministic grouped-softmax MLE on the winner
(`score_i = alpha·log(p_fundamental_i) + beta·log(p_market_info_i)`,
`c = softmax(score)`). Collinear inputs are refused (`CollinearInputsError`). **This
protocol produces the corpus and stops. It fits nothing.** The horizon of the corpus must
match the deployment horizon at fit time (SPEC-033); a mismatch is refused there.

---

## Hard prohibitions

- **No June data.** The June 2026 universe is the sealed lockbox (SPEC-092). No June
  market, outcome, calibration input, or feature is read, trained on, or peeked at by this
  block. Looking burns the lockbox.
- **No bookmaker odds in the fundamental.** Tennis-Data odds columns stay quarantined; the
  F2 pipeline is odds-free; the only market probability is the Betfair F0 `p_market_info`
  (`§5`).
- **No confirmatory alpha spent.** This is a **development** block. It debits no
  family-wise error budget and asserts no gate outcome. It produces training data for
  alpha/beta, nothing evaluated against a confirmatory endpoint.
- **No outcome peeking to steer F2 or calibration.** K, the chronology, the prior-match
  minimum, and the affine parameters are all frozen from prior authorised data before this
  block runs. No modelling choice here is justified by returns, ROI, CLV, hindsight, or
  inspecting who won (`.claude/rules/stage2-evidence-discipline.md`). The development
  `winner` label enters **only** the later MLE, never the choice of any policy.
- **No live betting, no execution, no order state.** The block reads historical purchased
  market data offline; it places nothing, and imports nothing from `l5_decision` /
  `l5b_risk` / `l6_broker`.
- **No LLM-produced numbers.** No probability, calibration parameter, price, or label is
  created, altered, smoothed, or repaired by an LLM — every number is deterministic tested
  code.
- **Development evidence only.** Outputs are development artefacts. They inform the
  alpha/beta fit; they prove no gate and authorise no spend.

---

## Provenance

Every produced corpus row and every manifest record is stamped so it is reproducible from
approved manifests and its lineage is auditable end to end:

- **Source vintage** — the frozen `vintage-<YYYY-MM-DD>` of the purchased market data
  (and the `vintage-2026-07-18` Tennis-Data results vintage for the fundamental), with the
  raw `MANIFEST.sha256` digest.
- **Identity policy version** — `td-norm-v1`, plus the correction-ledger digest applied
  (frozen; no new corrections).
- **F0 policy string** —
  `COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE W=60s L=300s (reschedule-policy-v1)` and
  `price_method = info-price-v2 (implied midpoint best back/lay, normalised; scope betfair
  MATCH_ODDS)`, with per-market `decision_digest` and `book_state_digest`.
- **F2 lineage** — K per tour (ATP 24 / WTA 32), the affine calibration
  `(intercept, temperature)` per tour under `calibration-policy-v2`, the
  `trained_through` date (strictly before the predicted match), the Design-B chronology id,
  and `label-policy-v1-completed-only`.
- **Manifest digest** — a `DIGESTS.txt` (sha256) over every produced artefact and a
  `_SUMMARY.json` of the full committed / refused / excluded / emitted funnel, mirroring
  `docs/evidence/stage2b-f0-f2-runs/`. The SPEC-032 fit step (later) records these digests
  as its bound data manifest.

Target output location (created only when the block is executed):
`docs/evidence/market-development-block/` (per-market manifest, summary, digests), mirroring
the June F0/eligibility evidence layout.
