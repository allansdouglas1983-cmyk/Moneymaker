# ADR 0016 (PROPOSED) — Sport pivot: Betfair Tennis Research Platform

**Status:** PROPOSED — founder directive 2026-07-16: freeze horse-racing
implementation (no deletion, no architecture rewrite, no evidence changes), replace
the sport adapter, minimal specification changes only. **No code until approved.**
This document is the required pre-implementation packet: impact assessment,
migration plan, exact files affected, SPEC changes.

---

## 1. Tennis impact assessment

### What transfers unchanged (the overwhelming majority)

The platform was built around one abstraction that tennis satisfies exactly: **a
Betfair market is one mutually exclusive choice set whose outcome probabilities sum
to 1**. Everything keyed to that abstraction is sport-agnostic and untouched:

- **l0 capture / l1 reducer**: the Exchange Stream `mcm` format is identical across
  sports; the historical-data service, file format, `pt` semantics, BSP fields and
  tier structure are per-sport instances of the same product (DR-0001's structural
  findings carry over; only prices and liquidity characteristics are sport-specific).
- **l3 knowledge-time machinery**: publication-time discipline is sport-independent.
- **price_contracts**: the Betfair tick ladder and the three price types are
  exchange-level, not sport-level.
- **l4 pricing**: the conditional logit (SPEC-030) handles varying field size
  natively — a tennis MATCH_ODDS market is the N=2 case (it degenerates to logistic
  regression, still fitted by the same grouped-softmax MLE; sum-to-1 holds; the
  cross-fit (SPEC-031) and stage-two combiner (SPEC-032) are unchanged).
- **l5 decision / l5b risk / l6 broker (Phase 3A in progress) / l7 settle CORE**:
  EV at executable prices, one-position-per-market, FOK taker policy, commission on
  the net market result, order state machine — all market-level, sport-blind.
- **l8 evidence**: gates, trial ledger, lockbox, paired inference, predictor
  metrics, calibration, CLV — all operate on "one market choice set + its outcome".
- **governance / analytics contracts / research protocol / budget discipline /
  ADR 0015 exclusion block** (the Betfair account is sport-independent).

### Tennis-specific deltas (the actual sport adapter)

1. **Choice set**: match (MATCH_ODDS market, 2 players) replaces race (WIN market,
   N runners). Internal vocabulary keeps `race_id`/`runner_id` field names (renaming
   ~200 sites would be an architecture-adjacent rewrite the directive forbids); the
   mapping match→`race_id`, player→`runner_id` (selection ids) is documented once in
   the specification amendment. The trial ledger's `decision_unit` token is the one
   place the word "race" is ENFORCED in code — see SPEC changes / correction 0003.
2. **Settlement edge cases**: racing's dead heats and reduction factors do not
   occur; tennis's dominant edge case is **retirement/walkover**, which under
   Betfair's tennis rules typically VOIDS the Match Odds market. The l7 core already
   settles VOIDED markets to zero (SPEC-082's void path); what tennis needs is a NEW
   sport-settlement rule module (proposed SPEC-084) encoding retirement/walkover/
   partial-completion semantics — added alongside, never editing, the frozen racing
   SPEC-082 implementation.
3. **Clustering unit for inference (SPEC-090)**: meeting-day becomes **calendar day
   (UTC)** — matches on the same day share tournaments, conditions, and repeated
   players. Day-level blocks pool concurrent tournaments, which is statistically
   CONSERVATIVE (larger blocks, wider CIs, never anti-conservative). The
   `meeting_day: date` field carries this unchanged — no evidence-code change.
   A finer tournament×day key would need an API change (an evidence change the
   directive forbids) — revisit only by separate approval if day-level power proves
   insufficient.
4. **Withdrawal before start** (racing's non-runner) maps to market void/removal at
   the exclusion-funnel level: an explicit exclusion with knowledge-time, upstream of
   pricing. SPEC-030's non-runner renormalisation text remains valid for the frozen
   racing code and is simply unexercised at N=2 (a tennis withdrawal voids rather
   than renormalises) — documented, not edited.
5. **Liquidity/timing risk (the honest downside)**: tennis is an in-play-dominated
   sport. Pre-off (pre-match) liquidity is concentrated in main-tour and slam
   matches; qualifiers/challengers may be thin. The pre-off-only prohibition stands,
   so the frozen universe definition must select tour levels with adequate pre-match
   depth, and Gate 2's executable-price scenarios will be the binding test. This is
   a risk to EDGE FEASIBILITY, not to platform validity — and the platform's job is
   to establish infeasibility cheaply if that is the truth.
6. **Fundamental data (the strategic upside)**: racing form data was the project's
   cost blocker (DR-0002: no public price for any knowledge-time-capable source).
   Tennis fundamentals — rankings, results, surface, head-to-head — have strong
   open/cheap sources (official rankings are published on a documented weekly cycle;
   open research datasets exist with non-commercial licences). Knowledge-time and
   licence vetting still required (new DR-0004), but the fund-or-descope pressure
   very likely dissolves. SPEC-044's lineage machinery handles a non-commercial
   licence correctly (internal research eligible; publication/commercial ineligible).
7. **Pilot month selection** changes sport: the racing January-2026 rationale is
   superseded; tennis coverage peaks differ (e.g. January = Australian Open swing).
   Redone under the same rules: most recent complete representative month, portal
   metadata count first, no model performance inspected. Betfair tennis package
   prices are NOT yet established (DR-0001 priced horse racing only) → new DR-0003.

### What this does NOT change

Every hard prohibition (pre-off only, back only, no live learning, LLM never prices,
exclusion/no-bypass invariant), the Phase-2 freeze and attestation, the £499
reserve, ADR 0015's blocks, test-correction 0002's pending status, and the Phase 3A
broker scope — all sport-independent, all stand.

---

## 2. Migration plan (phased; every phase gated on your approval of this ADR)

- **T0 — Documentation switch (no behaviour change):** SPECIFICATION.md §22 sport
  profile amendment; CLAUDE.md retitle + "the match is the unit" phrasing (with the
  race_id/runner_id mapping note); .claude/rules/evidence.md same; manifest header
  note + SPEC-084 added as `planned`; EXP-0001 marked SUPERSEDED (kept) and
  EXP-0002-tennis draft created; racing procurement docs marked
  SUPERSEDED-FOR-SPORT (kept); Weatherbys/RDC + Timeform enquiries marked WITHDRAWN
  (racing-specific, unsent); research ledger updated; DR-0003 + DR-0004 requests
  authored for your ChatGPT Deep Research.
- **T1 — Governed correction 0003 (separate approval, touches a pinned test):**
  `l8_evidence/trial_ledger.py` `decision_unit` accepts exactly {"race", "match"}
  (closed two-token vocabulary; anything else still refused) + the pinned test
  updated accordingly. This is the ONLY evidence-adjacent code change the pivot
  needs, and it ships alone, citing SPEC-091.
- **T2 — Sport adapter code (after T0/T1):** new `l7_settle` tennis-rules module
  implementing SPEC-084 (retirement/walkover/void semantics), red-tests-first;
  ingestion/runbook filter constants switch to tennis MATCH_ODDS; tennis pilot-month
  selection doc. Racing modules remain in place, frozen, passing their tests.
- **T3 — Data (blocked on ADR 0015 resolution + DR-0003 + your purchase
  confirmation):** tennis pilot month purchase and local-only ingestion under the
  existing runbook discipline.
- **Freeze mechanics:** racing implementation stays exactly where the Phase-2
  attestation pinned it — nothing deleted, tests keep running green, SPEC-082 stays
  active over the frozen racing settlement code. The pivot is additive + doc-level.

---

## 3. Exact files affected

**T0 (docs only):** `CLAUDE.md`; `docs/SPECIFICATION.md` (§22 amendment);
`docs/spec-manifest.yaml` (add SPEC-084 planned + header sport-profile note — no
existing entry edited); `.claude/rules/evidence.md`; `docs/PROGRESS.md`;
`docs/experiments/EXP-0001-draft.md` (superseded banner) + new
`docs/experiments/EXP-0002-tennis-draft.md`; `docs/procurement/betfair-pilot-purchase.md`
+ `betfair-pilot-runbook.md` (superseded banners) + new tennis equivalents;
`docs/procurement/provider-enquiry-weatherbys-rdc.md` + `provider-enquiry-timeform.md`
(WITHDRAWN banners); `docs/research/ledger.yaml` (DR-0002 → SUPERSEDED_BY_SPORT_PIVOT,
DR-0003/0004 added) + new `docs/research/requests/DR-0003-betfair-tennis-data.md` and
`DR-0004-tennis-fundamental-data.md`; `docs/decisions/README.md` (0016 row).

**T1 (governed correction 0003):** `l8_evidence/trial_ledger.py` (decision-unit
token set) + `tests/unit/l8/test_trial_ledger.py` (the pinned race-only test).

**T2 (new code, nothing edited):** new `l7_settle/tennis_rules.py` (SPEC-084) + its
unit/property tests; tennis constants in the (still-unlanded) ingestion runbook/tool
configuration.

**Explicitly untouched:** all of l0/l1/l3, `price_contracts/`, all of l4_pricing,
l5_decision, l5b_risk, l6_broker (Phase 3A continues as scoped), l7_settle's existing
racing modules, every l8_evidence module, gates and gate specs, governance,
analytics_contracts, all Phase-2 attestation artifacts, the correction-0002 branch.

---

## 4. SPEC changes (minimal set)

1. **SPECIFICATION.md §22 (new amendment, additive):** sport profile = TENNIS.
   Decision unit: one MATCH_ODDS market (2 mutually exclusive players); internal
   `race_id`/`runner_id` field names retained as the market/selection identifiers
   with the documented mapping; clustering key = UTC calendar day (conservative
   pooling); withdrawal → void/exclusion (never renormalisation at N=2);
   retirement/walkover settlement per SPEC-084; racing implementation frozen and
   retained under its existing SPEC-IDs.
2. **Manifest — ONE new entry:** `SPEC-084` (component `l7_settle`, criticality
   `money`, `planned`): "Tennis settlement rules: retirement, walkover, and
   partial-completion outcomes settle per Betfair tennis market rules — Match Odds
   void semantics encoded explicitly; a completed-match result settles win/lose; an
   uncertain completion status blocks settlement (unknown blocks, SPEC-082
   semantics). Never edits racing settlement." Full `relevant_inputs`/
   `metamorphic_properties` declared at its implementing slice.
3. **Manifest header note (comment only):** sport profile tennis per ADR 0016;
   racing-specific requirement texts (e.g. SPEC-082's dead-heat/reduction-factor
   list) remain active over the frozen racing implementation.
4. **Governed correction 0003 (separate approval):** SPEC-091's `decision_unit`
   enforcement widens from exactly-"race" to the closed set {"race","match"}.
5. **No other spec text changes.** SPEC-030/090's "race" wording is interpreted via
   §22's mapping; editing active money/evidence requirement texts is avoided
   entirely.

**Approval needed to proceed:** (a) this ADR overall → unlocks T0; (b) correction
0003 → unlocks T1; (c) SPEC-084 activation happens per the normal slice convention
when T2 lands. Also still pending separately: test-correction 0002.
