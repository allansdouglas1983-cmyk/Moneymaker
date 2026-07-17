# ADR 0017 Phase 1 — Architecture audit: what still assumes horse racing

**Date:** 2026-07-17. Synthesis of three exhaustive read-only sweeps (production code;
tests + specifications; documentation + governance). Nothing was changed. This is the
founder's Required Output #1 (full architecture audit) and #2 (refactor plan).

## Executive summary

**The platform is ~80% sport-agnostic already.** Its load-bearing abstraction — *a
Betfair market is one mutually exclusive choice set whose outcome probabilities sum
to 1* — is sport-neutral, and everything keyed to it works for tennis unchanged: the
capture/reduce layers, knowledge-time machinery, the tick ladder and three price
types, the conditional-logit core (no true N>2 dependence — N=2 is native), EV and
execution policy, the broker/risk designs, the gate/statistics machinery, snapshots,
exports, explanations, calibration, CLV math, governance, and all CI tooling.

Racing lives in **six concrete seams** plus **naming**. Production code contains
**14 structural racing findings, 33 naming-only, 1 mis-homed, 7 correctly
racing-specific** — and zero hard-coded track names, going/surface enums, or horse
vocabulary anywhere in production logic.

## The six SportAdapter seams (where racing actually lives in code)

1. **Choice-set + outcome mapping** — `l4_pricing/races.py` (`Race`/`RunnerRow`/
   `non_runner`/`winner_id`) and `l7_settle/outcomes.py` (`RunnerResult` incl.
   `REMOVED`). The adapter supplies the mutually exclusive set, the winner, and
   removed/void selections.
2. **Settlement policy** — reduction factors, dead-heat divisor, REMOVED handling in
   `l7_settle/{pnl,settlement}.py`, behind an already-generic net-commission/void/
   ledger core. Racing keeps these unchanged; tennis gets retirement/walkover/void
   (SPEC-084).
3. **Correlation-cluster key** — `meeting_day` in `l4_pricing/{races,crossfit,
   stage_two}.py` and `l8_evidence/paired_inference.py` (block-bootstrap cluster,
   cross-fit fold ordering). Generalises to an adapter-declared cluster key
   (racing: meeting-day; tennis: UTC calendar day per ADR 0016).
4. **Closing/grading diagnostics + taint set** — `l8_evidence/reconciled_bsp.py`,
   the BSP taint literal duplicated in `l3_features/leakage.py` (the one MIS-HOMED
   finding: two layers share a racing constant that belongs in one adapter-owned
   taint registry), and `ClosingBenchmark.BSP` in `l8_evidence/clv.py`. The guard
   MECHANISM (settlement-time benchmarks never pre-off) is generic; the taint VALUES
   are per-sport.
5. **Event-start semantics** — `l3_features/build_context.py` scheduled-vs-actual
   "off". The principle (actual start unknowable live) is universal; "off" is racing
   vocabulary.
6. **Decision unit** — `l8_evidence/trial_ledger.py` line ~110/307:
   `_DECISION_UNIT = "race"` is actively ENFORCED — a tennis registration
   (`decision_unit="match"`) is refused at construction, and a pinned test asserts
   the refusal. **The single hardest concrete coupling in the platform.**

## The nine governed-correction surfaces (frozen/pinned — each needs founder-level handling)

| # | Surface | Nature | Handling |
|---|---|---|---|
| C1 | `specs/prices/close-v1.yaml` (`primary: BSP`) | STRUCTURAL — tennis has no BSP | NOT reusable. New pre-registered `close-v2` — but benchmark selection is DATA-DEPENDENT (DR-TENNIS-BENCHMARK unresolved) → Phase 10 builds interfaces only; close-v1 stays racing-adapter-scoped |
| C2 | `specs/prices/info-price-v1.yaml` | NAMING (semantics generic: best-back/lay midpoint works for N=2) | Governed `info-price-v2` re-word (vocabulary only, formulas identical) |
| C3 | `specs/prices/exec-price-v1.yaml` | NONE — zero racing tokens | Reusable as-frozen. No action |
| C4 | `specs/gates/v1.yaml` ("race-day blocks") | NAMING inside a frozen gate spec | Do NOT churn: gates-v1 stays frozen for the racing adapter; sport-agnostic wording authored as gates-v2 only when a non-racing experiment actually needs gate evaluation |
| C5 | `specs/gates/predictor-p1.yaml` (meeting-day clustering) | NAMING + one STRUCTURAL (cluster key) | Same posture: predictor-p2 only when needed |
| C6 | `tests/unit/l8/test_trial_ledger.py` decision_unit=="race" refusal (+ mirrors) | STRUCTURAL + PINNED | **Governed correction 0003**: closed set of adapter-declared decision units ({"race","match"}), validator + pinned test together, own slice |
| C7 | ~15 ACTIVE manifest requirement texts with racing wording (021,022,023,030,031,032,035,036,037,038,080,082,090,095,097) | Mostly NAMING; STRUCTURAL: 022 (off-time), 031/090 (meeting-day), 030 (non-runner), 082 (dead heats/RF — correctly racing) | One batched, founder-approved **wording amendment**: race→event/choice-set, runner→selection, meeting-day→cluster key, with 022/030/082 explicitly marked racing-adapter-scoped rather than reworded. Semantics never change; CI coverage never drops |
| C8 | `specs/mutation-survivors.yaml` (8 pinned l7 survivors keyed to racing enums) | PINNED coupling | Avoid invalidating: the settlement-policy seam (slice S3) keeps `l7_settle` module paths and enum names stable; racing enums stay in place as the racing adapter's settlement vocabulary |
| C9 | `tests/unit/l8/test_prediction_snapshots.py` forbidden-substrings ("bsp","actual_off") + `UpdateReason.NON_RUNNER` | Guard generic; tokens racing | Keep the racing tokens IN the guard (they remain forbidden — correct for any sport on Betfair racing data) and ADD sport-generic tokens; NON_RUNNER stays as a racing-adapter update reason, tennis adds its own members via the enum extension slice |

## What is already fully sport-agnostic (verified, no action)

`l0_raw` (whole package), `l1_reduce` (logic; Betfair's own "runner" field naming
retained deliberately — it is the exchange's cross-sport term), `governance` (whole),
`tools` (whole), `l8_evidence/gates/` (whole tree), `l5_decision` logic (EV,
execution, ladder, prices), `l5b_risk`/`l6_broker` designs, `price_contracts`
(Betfair-specific, sport-neutral), `analytics_contracts` logic, `sample_size`,
`explanation_inputs` logic, calibration/predictor-metrics math, CLV math (minus the
BSP benchmark member), `docs/facts.yaml`, Phase 3A work in flight.

## Invariant generalisation (docs layer — every racing "platform invariant" judged)

| Stated invariant | Generalises? | Sport-agnostic restatement |
|---|---|---|
| One runner per market | YES | One position per market |
| The race is the unit of analysis, not the runner | YES | The market/choice-set is the unit, not the selection |
| Cluster by meeting-day | YES | Cluster by the sport's shared-conditions block |
| Reconciled BSP never a pre-off feature | YES | Settlement-time benchmarks never pre-off features |
| No actual-off time; live knows scheduled start | YES | No actual-start leakage; live knows scheduled start |
| Non-runner drop + renormalise | PARTIAL | Exclusion-funnel handling of pre-start withdrawals; renormalisation is the racing mechanism, void is the tennis mechanism |
| Reduction factors, dead heats | NO | Racing-adapter settlement semantics (preserve) |
| Going/jockeys/pace/field-size vocabulary | NO | Racing-adapter feature vocabulary (preserve) |
| Commission on net market result; three prices; taker-v1; queue-latency facts | ALREADY AGNOSTIC | verbatim |

Identity changes: CLAUDE.md / SPECIFICATION.md / README titles → "Betfair Exchange
Research Platform". Gap found: ADR 0016's referenced SPECIFICATION §22 sport-profile
amendment was never authored — it gets written in slice S9.

## Refactor plan (Required Output #2) — slices, mapped to ADR 0017 phases

Ordering principle: additive contracts first (no governed surface touched), renames
and governed corrections after approvals, racing adapter extraction last (it is the
riskiest because it touches money modules and the pinned mutation surface).

- **S0 — Green baseline (BLOCKING, needs founder):** decide test-correction 0002;
  then land the two held, reviewed implementations (SPEC-070/071 broker; ingestion
  tool) whose red tests are already committed. Without S0 every later slice lands on
  a red verify and the refactor cannot be honestly gated.
- **S1 — Sport core package (Phase 2):** new `sport_core/` defining the
  SportAdapter protocol: decision-unit token, cluster-key extractor, event-start
  vocabulary, settlement-policy hook, closing-diagnostic taint set, choice-set
  construction. Plus `sport_racing/` adapter capturing CURRENT behaviour verbatim
  (delegating to existing modules — no logic moves yet). Additive; verify-gated.
- **S2 — Governed correction 0003 (needs founder approval):** decision_unit widens
  to the adapter-declared closed set; validator + pinned test in one slice.
- **S3 — Settlement policy seam (Phase 2, money-critical, lead-reviewed):**
  extract the racing policy (RF/dead-heat/REMOVED) behind the generic core INSIDE
  `l7_settle` with stable module paths and enum names (protects C8's pinned mutation
  survivors). Racing behaviour byte-identical, proven by the untouched test suite.
- **S4 — Tennis domain contracts (Phase 3):** `sport_tennis/domain.py` — immutable,
  versioned contracts only (Match, Player, Tournament, Surface, Round, BestOf,
  RetirementStatus, WalkoverStatus, QualificationStatus, MarketSelection,
  MarketSnapshot, SettlementOutcome, ExecutionOutcome). No algorithms, no data.
- **S5 — Probability + model interfaces (Phases 4–5):** `sport_core/interfaces.py`
  protocols (FundamentalProbabilityProvider, MarketProbabilityProvider,
  CombinedProbabilityProvider, Calibration/Uncertainty providers, FeatureGenerator,
  Ranking/SurfaceRating/FitnessSignal/ServeStrength/ReturnStrength providers) +
  named model-contract stubs-as-protocols (SurfaceElo, WeightedElo, BradleyTerry,
  RegularisedLR, future Bayesian/GBM/Ensemble). Contracts only; constructing any of
  them without an implementation is a typed refusal, never a silent stub.
- **S6 — Feature + evidence registries (Phases 6–7):** versioned FeatureRegistry
  (name, description, knowledge-time requirements, licensing status, source,
  missing-data behaviour, deterministic definition, version, evidence status —
  reusing SPEC-044 licensing vocabulary) and experiment templates (market-only,
  SurfaceElo, WeightedElo, BradleyTerry, combined) that plug into the EXISTING
  SPEC-091/093 ledger/gate framework unchanged.
- **S7 — Tennis settlement contracts (Phase 8):** SPEC-084 types — completed /
  walkover / retirement-before-set-1 / retirement-after-set-1 / disqualification /
  cancelled / postponed / surface-change outcomes — with the empirical policy as an
  EXPLICIT `PolicyPendingPilotError` refusal (never a TODO literal; the escape-hatch
  ban stands). Manifest: SPEC-084 added `planned`.
- **S8 — Market + benchmark abstractions (Phases 9–10):** MarketKind enum
  (MATCH_ODDS enabled; SET_WINNER/CORRECT_SCORE/GAME_MARKETS declared-but-refused)
  and ClosingBenchmark interfaces (final midpoint / windowed midpoint / WAP /
  microprice as named future implementations, none selected — selection stays
  evidence-driven post-pilot).
- **S9 — Naming + docs (Phases 11–12):** the (B) rename sweep where it
  unnecessarily embeds racing (l4 `races.py` → market choice-set vocabulary with
  history-preserving moves; `one_runner.py` → market-position naming; "off" →
  event-start), CLAUDE.md/rules/SPECIFICATION invariant rewording per the table
  above, §22 authored, titles changed, racing docs banner-scoped to the adapter,
  C7 manifest wording amendment (founder-approved batch). Mechanical test renames
  ride with their production renames, documented per slice.
- **S10 — Final documentation pack + adversarial self-critique (Phase 12 /
  Required Outputs #3–9):** repo map, architecture diagram, migration rationale,
  open/blocked decisions, data-dependent work list, risk register, licensing
  questions, roadmap, and the self-critique.

## Approvals this plan needs from the founder (nothing proceeds past S1/S4–S8 without them)

1. **Test-correction 0002** (already packeted, branch isolated) — unblocks S0/green baseline.
2. **Governed correction 0003** — decision_unit closed set {"race","match"} (S2).
3. **C7 wording amendment batch** — race→event vocabulary in ~15 active manifest texts, semantics untouched (S9).
4. **info-price-v2 re-word** (C2) — vocabulary-only new version of the frozen info price (S9; racing keeps v1).

## Risks

- Renames touching active tests are mechanical but wide; mitigated by slice-per-rename, verify-gated, riding with their production change.
- C8 mutation-survivor invalidation if l7 paths/enums move — mitigated by the S3 stable-path design.
- Close-benchmark (C1) and tennis settlement policy (S7) are data-dependent and stay contracts-only — any pressure to "just pick one" is refused per the directive.
- The biggest non-technical risk is proceeding on a red verify baseline — hence S0 first.
