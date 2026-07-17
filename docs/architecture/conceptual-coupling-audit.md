# Conceptual-Coupling Adversarial Audit (ADR 0017, founder-directed)

**Date:** 2026-07-17 · **Scope:** entire platform at the ADR 0017 S0–S8 head
(`0d6e8a8`) · **Method:** three parallel deep-read auditors (capture/features,
pricing, decision/evidence), each testing every module's *behaviour* — not its
vocabulary — against three markets: (a) tennis Match Odds (binary, retirements, no
BSP, irregular suspend/resume), (b) football Match Odds (3 outcomes incl. a draw with
no competitor behind it), (c) a binary financial prediction market (no sport event,
no scheduled start, possibly days of pre-close trading). Per the founder's
instruction this audit hunted **assumptions, not names**: hidden horse terminology,
N>2 assumptions, animals-vs-competitors, single-scheduled-start, BSP-existence,
race-based settlement leaks, dead-heat/reduction-factor leaks, conditional-logit-
required, runner-vs-selection conflation.

Every in-scope file was read in full. Clearances are reported alongside findings so
absence of a finding is evidence, not silence.

Severity vocabulary: **BLOCKS-TENNIS** (breaks or corrupts the tennis program),
**DEFECT** (wrong for racing today, independent of sport), **DEGRADES-GENERALITY**
(tennis survives by convention; a further market breaks), **DESIGN-REVIEW** (founder
judgement needed), **COSMETIC / S9** (wording; semantics verified fine).

---

## 1. Findings

### F-01 · Knowability boundary encodes "events are only ever delayed" — BLOCKS-TENNIS (leakage)
`l3_features/build_context.py:80-92` — the LIVE knowability boundary is *always*
`scheduled_start`, safe only under racing's directional fact that the off is never
earlier than scheduled. Tennis matches are routinely brought **forward**; a feature
first-usable after the true start but before `scheduled_start` would pass
`assert_knowable_before_off` — a live and post-hoc leakage hole of exactly the class
SPEC-020 exists to make impossible. Symmetrically, a 3-hour-delayed match has
genuinely pre-off features rejected (silent evidence loss). The context never
consumes observed market state (`inPlay`/`status`/suspension) even though the L1
reducer tracks it.
**Fix (own governed slice, before any tennis feature building):** an explicit,
adapter-supplied knowability boundary — observed-market-state-based for live;
recorded in-play/close transition for post-hoc. "Scheduled start is a safe floor"
becomes a *racing-adapter declaration*, refused for sports where events start early.

### F-02 · `FeatureBuildContext` structurally requires `scheduled_start` — DEGRADES-GENERALITY
`l3_features/build_context.py:52`. A binary financial market with no scheduled event
start cannot construct a context without fabricating a timestamp (which then becomes
the leakage boundary — F-01). The general concept is "decision-validity horizon /
market close"; scheduled start is one adapter-specific derivation. Fold into the
F-01 slice.

### F-03 · `ClosePrice` is a tick index but no close benchmark is tick-valued — DEFECT (racing too)
`price_contracts/prices.py:64-83` vs `specs/prices/close-v1.yaml`. BSP is a
reconciled weighted average, generally **off-ladder**; `pre_suspension_wap` likewise.
`ClosePrice(tick_index=...)` cannot represent either declared benchmark and no
snapping rule is declared anywhere. Any future tennis/financial benchmark
(WAP/microprice per `sport_core/benchmarks.py`) is also off-ladder.
**Fix (own governed slice, priority independent of the sport program):**
`ClosePrice` carries an exact Decimal plus a benchmark-method identity; ladder tick
indices remain for *transactable* prices only (`OddsExec` unchanged).

### F-04 · Replay silently drops `backfill_market` frames — DEFECT
`l1_reduce/replay.py:9` filters `record_type == "market"` only. An L0 log produced by
`tools/ingest_historical.py` (all frames `backfill_market`) replays to an **empty
universe with no error** — a silent disappearance, contrary to the refuse-don't-
degrade posture, and it means no backfilled historical corpus (racing pilot or tennis
pilot) can flow through the SPEC-011 replay path.
**Fix:** accept both record types explicitly or refuse a log containing zero market
frames. Small, high-value, needed before any purchased-data pilot.

### F-05 · Cluster key is hardcoded as a `date` named `meeting_day`; the adapter declaration is decorative — DEGRADES-GENERALITY
Two independent sightings, one design flaw:
- `l4_pricing/races.py:92` (`meeting_day: date`), `l4_pricing/crossfit.py:100,127-142`
  (fold blocking and the SPEC-031 `trained_through_day >= race.meeting_day`
  contamination check);
- `l8_evidence/paired_inference.py:138` (`PairedRace.meeting_day: date`) and the
  SPEC-090 block bootstrap.

`SportAdapter.cluster_key_name` (tennis: `calendar_day_utc`) is consumed by
**nothing**. Tennis works only by punning a UTC calendar day into a field named
`meeting_day`; a financial market whose correlation block is not a calendar date
(per-underlying, per-expiry) cannot be expressed at all.
**Fix (one governed slice):** an opaque, totally ordered `ClusterKey` supplied by the
adapter, threaded through crossfit and paired inference so the declared seam is
load-bearing. The type widening touches SPEC-031/090 test expectations → governed
test change, cited and isolated.

### F-06 · Out-of-fold production is welded to conditional logit — DEGRADES-GENERALITY
`l4_pricing/crossfit.py:144,158,184` call `fit_conditional_logit`/`predict_race`
directly; `cross_fit()` accepts no provider. The S5 seams (BradleyTerry,
RegularisedLogistic, GradientBoosting…) have no route through the only honest OOF
producer, so any new family must re-implement the fold discipline — precisely the
duplication SPEC-031 exists to prevent. (`OOFFundamental`/`StageOneProvenance` are
already family-agnostic; only the producer is welded.)
**Fix:** parameterise `cross_fit` on a fit/predict pair satisfying a seam, provenance
unchanged; `assert_out_of_fold` already validates independently of family.

### F-07 · Competitor identity: `int` in sport_core protocols vs `str` in sport_tennis domain — BLOCKS-TENNIS at implementation time
`sport_core/interfaces.py` (SurfaceRating/FitnessSignal/ServeStrength/ReturnStrength
providers, SurfaceElo/WeightedElo models) key players by `int`;
`sport_tennis/domain.py:131` declares `player_id: str` (external ATP/WTA-style
identity), with the int↔player translation living in `MarketSelection` where it
belongs. The first concrete tennis provider must violate one contract. This is
runner-vs-selection conflation in protocol form.
**Fix:** `player_id: str` in those protocols and relocate all four tennis-flavoured
provider protocols to `sport_tennis/` (their own docstrings already recommend it).

### F-08 · CLV type family is sealed to racing's two benchmarks — BLOCKS-TENNIS (CLV diagnostics only)
`l8_evidence/clv.py:172-177` seals `ClosingBenchmark` at {BSP, PRE_SUSPENSION_WAP}
("exactly two members" enforced) and every CLV type requires it, while
`sport_core/benchmarks.py` correctly forbids retrofitting that enum. Today this is an
honest refusal (tennis has no benchmark), but when a tennis benchmark IS selected the
CLV family cannot accept it without parallel types — a structural dead end.
**Fix (deferred until benchmark selection):** parameterise `ClosingPrice.benchmark`
over an adapter-declared versioned benchmark identity (the `ClosingBenchmarkMethod`
method_id/version shape); racing's two become the racing adapter's declared
instances; never-averaged/same-observation guards intact.

### F-09 · Settlement-seam vocabulary carries racing-only fields without capability enforcement — DEGRADES-GENERALITY
`l7_settle/policy.py` types the seam on `MatchedPosition`/`RunnerOutcome`, which
carry `applicable_reduction_factors`/`dead_heat_count`. Defaults are semantically
neutral and tennis is not forced to fabricate anything — but nothing rejects a tennis
`MarketOutcome` carrying `dead_heat_count=3` despite `TENNIS_CAPABILITIES` denying
dead heats. Unreachable today (tennis refuses all settlement).
**Fix:** bind into the SPEC-084 activation slice — the seam (or the tennis policy)
refuses non-default racing-only fields for sports whose capabilities deny them.

### F-10 · `UpdateReason.NON_RUNNER` is a racing-only member of a closed enum — DEGRADES-GENERALITY
`l8_evidence/prediction_snapshots.py:101-114`. A tennis pre-off withdrawal has no
honest member and would have to be mislabelled. **Fix:** governed enum extension
(e.g. `SELECTION_WITHDRAWN`) before tennis snapshots exist; SPEC-037 manifest wording
moves with the S9 batch.

### F-11 · Predictor metrics cannot represent dead heats or voids — DEGRADES-GENERALITY (inverse coupling)
`l8_evidence/predictor_metrics.py:310-315` requires exactly one winner; dead-heat
races (racing's own case) and voided markets (the normal tennis walkover outcome)
must leave the evaluated set, and only caller discipline keeps them in the
denominator. **Fix:** documented/enforced explicit-exclusion path for tied/voided
choice sets, with knowledge-time — same slice as F-12.

### F-12 · `Race.winner_id` cannot distinguish "not yet known" from "no sporting winner exists" — DEGRADES-GENERALITY
`l4_pricing/races.py:94`. Void/walkover/dead-heat corpora can only be handled by
silent upstream omission — colliding with "explicit exclusion, never a
disappearance". **Fix:** an explicit outcome type (WINNER(id) | VOID(reason) |
PENDING) or a hard requirement that such markets enter `ExcludedRace` accounting with
a knowledge-time.

### F-13 · Market reservation never releases on a zero-matched lapse — DESIGN-REVIEW
`l6_broker/orders.py:203-205,524-528`: a FOK miss (LAPSED, matched=0) reserves the
market until settlement. Not racing-coupled — it binds racing equally — but tennis's
repeated pre-off suspend/resume churn makes it far more visible: one suspension-
induced lapse forfeits the market. This may be intended SPEC-054 conservatism
(refuse re-entry after any order activity). **Founder decision requested**; if
relaxation is wanted it is a money-module change with its own red tests.

### F-14 · Reconciled-close taint guard is BSP-shaped, not concept-shaped — DEGRADES-GENERALITY
`l3_features/leakage.py:20` — the single literal taint marker
`l8_evidence.reconciled_bsp:RECONCILED_BSP`. For sports with no BSP the SPEC-021
runtime guard is a structural no-op; the general concept is "post-close reconciled
quantity" (final result, retirement reason, settlement value, reconciled benchmark).
**Fix:** a taint *family* (`reconciled_close:` prefix, per-benchmark suffixes); BSP
stays one member; tennis's adapter taint set stops being empty the day a benchmark is
selected.

### F-15 · Frozen price specs carry no machine-readable scope — DEGRADES-GENERALITY
`specs/prices/*.yaml` have no `applies_to:` field; close-v1 presumes BSP and a single
terminal suspension; info-price-v1's `max_age_ms: 5000` encodes racing's cadence.
Nothing selects them unconditionally today (mitigated by `selected_benchmark()`'s
refusal), but scoping is prose, and consumers are not obliged to route through the
refusing module. **Fix:** explicit `scope:` field + consumer-side scope-mismatch
refusal (mirrors SPEC-033's horizon-mismatch pattern). The approved info-price-v2
vocabulary reissue (S9) is the natural carrier.

### F-16 · Minor / cosmetic
- `price_contracts/ladder.py`: Betfair-ladder-locked with no `ladder_version`
  identity — acceptable ("Betfair-scoped by design") but should say so (S9 banner).
- `l4_pricing/_newton.py:87-107`: within-race-constant features (tennis: surface,
  best-of — race-level by construction) surface as `SingularHessianError` blamed on
  separation/collinearity; behaviour correct (refusal, never regularisation), the
  diagnosis is racing-tuned. Improve the message / add a zero-within-race-variance
  schema check.
- SPEC-040 (planned, no code) lists "runner removal" as a universal fill-model
  terminal event; must be capability-conditioned when implemented.
- `l8_evidence/trial_ledger.py:43-46` docstring still says decision_unit must be
  exactly `'race'`, contradicting the implemented `{race, match}` (correction 0003).
  S9 batch.

## 2. Clearances (read in full; genuinely sport-agnostic)

- **l0_raw entirely** (records/store/capture/commands/clock/backfill) and
  `tools/ingest_historical.py`: bytes/clock/checksum/provenance only; clean for all
  three markets.
- **l1_reduce** mcm_v1/state/canonical/reducer: a faithful generic MCM fold; racing
  fields (`adjustmentFactor`, `removalDate`) are pass-through payload, never
  load-bearing; N=2/N=3 reduce identically; suspend/resume cycles are status
  overwrites. (Except F-04 in replay.py.)
- **l3_features** knowledge_time (semantics generalise; naming is S9),
  feature_registry, feature_set (inherits F-01/02 via the context, adds none).
- **l4_pricing** _newton (arity-free MLE; honest refusals at N==2),
  conditional_logit (non-runner drop optional/inert), races (>=2 admits binary;
  football's draw is just another selection id; no biology fields anywhere),
  stage_two, horizon (opaque labels, no cadence), objectives, distribution,
  interfaces, manifest, probability_outputs.
- **sport_core** capabilities (the 11 booleans cover football + binary financial
  with no new fields; no default arity; refusals structural, never sport-named),
  adapter (no identity branching; governed decision-unit set is the intended
  extension mechanism for football), markets, benchmarks (no BSP assumption, no
  fallback, int-tick/int-minor discipline runtime-enforced).
- **sport_tennis** adapter + domain: adapter-scoped by design; the two-selection
  MarketSnapshot is Match Odds-correct, not a leaked core assumption.
- **l5_decision** ev (valid per single position at any N incl. football), one_runner
  (already "one selection per market" in code), execution (exchange-generic).
- **l6_broker** orders: marketVersion opaque; no runner-removal assumption; tennis
  suspend/resume representable (F-13 is a conservatism question, not coupling).
- **l7_settle boundary holds:** dead-heat/reduction-factor semantics exist only in
  outcomes/pnl/settlement, reached exclusively through `RacingSettlementPolicy`;
  ledger.py sport-neutral; **zero imports of l7_settle anywhere in l8_evidence,
  analytics_contracts, governance** — race-based settlement does not leak into
  generic layers.
- **l8_evidence** gates (n = decision units; racing references are comments),
  predictor_metrics cohorts caller-supplied (no hardcoded odds-band/track/field-size),
  calibration N-agnostic, SPEC-037 snapshots carry no BSP/result field and
  `active_runner_set_hash` is well-defined at N==2.
- **specs/mutation-survivors.yaml** correctly keyed to stable racing paths; the S3
  seam preserved them deliberately.

## 3. S9 wording worklist (semantics verified fine; approved C7 batch, enriched)

Manifest active-ID texts: SPEC-020/021/022/030/031/032/035/036/037/038/054 (title →
"one selection per market")/082/090/095/097. Rules files: `.claude/rules/evidence.md`,
`.claude/rules/analytics.md`, `.claude/rules/moneycritical.md`, `CLAUDE.md` structural
facts + prohibitions. Code naming (rename-only): `l5_decision/one_runner.py`,
`paired_inference` (PairedRace/race_id/meeting_day — name half of F-05),
`predictor_metrics` (RaceEvaluationInput/RaceMetrics/races_evaluated/
total_universe_races), `calibration` docstrings, `prediction_snapshots` (race_id,
number_of_active_runners, active_runner_set_hash), `analytics_contracts/
export_contract.py` (RunnerProbabilityExport/race_id/runner_id), `l4_pricing/races.py`
vocabulary, gate YAML comment text (`specs/gates/v1.yaml`, `predictor-p1.yaml`),
trial_ledger stale docstring (F-16), ladder Betfair banner (F-16).

## 4. Bottom line

The adapter/capability/policy seams landed by S0–S8 are genuinely load-bearing where
they were wired (settlement, capabilities, decision units, market kinds, benchmark
refusal). The audit found **two places where a declared seam is not yet consumed by
the code it governs** (cluster key — F-05; stage-one family — F-06), **one live
leakage-class hole that must close before any tennis feature exists** (knowability
boundary — F-01/02), **two defects that bite racing today** (close-price
representation — F-03; backfill replay — F-04), and a set of enum/vocabulary dead
ends (F-07..F-12, F-14, F-15) each of which has a bounded, governed fix. Nothing
found contradicts the S0–S8 design; everything found is the next layer down.
