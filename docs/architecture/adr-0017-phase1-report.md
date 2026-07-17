# ADR 0017 — Sport-Agnostic Transition: Architecture Audit Report & Refactor Plan

**Date:** 2026-07-17 · **Head:** `0d6e8a8` · **Status:** S0–S8 landed and verified
(`make verify` 1,662 tests / 44 enforced SPEC-IDs / mypy clean over 249 files;
`make replay` green). S9 (approved vocabulary batch) and S10 (documentation pack)
remain.

This report synthesises the three audits the program produced:
1. **Phase 1 adversarial architecture audit** (`sport-agnostic-audit.md`) — the six
   seams and nine governed surfaces C1–C9 that shaped the refactor plan;
2. **The implementation record** (S0–S8, this branch) — what was actually built and
   what the build surfaced;
3. **The conceptual-coupling adversarial audit** (`conceptual-coupling-audit.md`,
   founder-directed, assumptions-not-names) — sixteen findings F-01..F-16 with
   full-file clearances.

---

## Output 1 — Audit

**Phase 1 verdict (audit #1):** the platform was ~80% sport-agnostic by
construction; racing coupling concentrated in six seams — decision unit,
correlation-cluster key, event-start vocabulary, settlement policy,
closing-diagnostic taints, choice-set construction — plus nine governed surfaces
(C1 close-v1/BSP, C2 info-price wording, C6 decision unit, C7 manifest vocabulary,
C8 mutation-survivor stability, C9 snapshot token guards, among them).

**Conceptual verdict (audit #3, post-build):** the seams that S0–S8 wired are
load-bearing — settlement policy, capability matrix, decision units, market-kind
policy, benchmark refusal all pass the tennis / football / binary-financial design
tests, and race-based settlement provably does not leak into generic layers (zero
`l7_settle` imports across `l8_evidence`, `analytics_contracts`, `governance`).
The audit found the next layer down:

- **1 leakage-class hole:** the knowability boundary assumes events are only ever
  delayed (F-01/F-02) — racing-true, tennis-false; must close before any tennis
  feature is built.
- **2 racing-agnostic defects found by the sport lens:** `ClosePrice` cannot
  represent either declared close benchmark (F-03 — a racing defect today);
  backfilled corpora silently replay to an empty universe (F-04).
- **2 declared-but-unconsumed seams:** the adapter's cluster key is decorative —
  crossfit and paired inference hardcode a `date` named `meeting_day` (F-05); the
  only honest out-of-fold producer is welded to conditional logit (F-06).
- **Enum/vocabulary dead ends with bounded fixes:** CLV benchmark enum sealed to
  racing's two (F-08); `int` vs `str` competitor identity between sport_core
  protocols and the tennis domain (F-07); `UpdateReason.NON_RUNNER` (F-10);
  void/dead-heat unrepresentable in training and metrics types (F-11/F-12);
  BSP-shaped taint guard (F-14); prose-only spec scoping (F-15).
- **1 founder design decision:** market reservation never releases on a
  zero-matched lapse (F-13) — possibly intended conservatism, disproportionately
  binding under tennis suspend/resume churn.

Full findings, severities, file:line anchors and clearances:
`conceptual-coupling-audit.md`.

## Output 2 — Refactor plan (remaining, in order)

| Slice | Content | Gate |
|---|---|---|
| **S9** (approved) | C7 vocabulary batch across ~15 active manifest texts; info-price-v2 vocabulary reissue (racing keeps v1) with F-15's `scope:` field; rename sweep (`one_runner.py`, races vocabulary, evidence-type names per the enriched worklist in the audit §3); CLAUDE.md/rules rewording; SPECIFICATION §22; F-16 cosmetics. Semantics byte-identical — proven by the untouched test suite. | make verify + replay |
| **S10** | Documentation pack: this report finalised, repo map, migration rationale, risk register, PROGRESS.md. | n/a (docs) |
| **A1** (new, from F-01/02) | Adapter-supplied knowability boundary; observed-market-state semantics; racing keeps scheduled-start as a declared safe floor. **Blocks all tennis feature work.** | red tests first; governed (SPEC-020/022 adjacent) |
| **A2** (new, from F-03) | `ClosePrice` → exact Decimal + benchmark identity. **Racing defect; independent of sport program.** | money-adjacent; red tests first |
| **A3** (new, from F-04) | Replay accepts/refuses backfill frames explicitly. **Blocks any purchased-data pilot.** | evidence; red tests first |
| **A4** (new, from F-05) | Opaque ordered `ClusterKey` threaded from adapter through crossfit + paired inference. Touches SPEC-031/090 pinned tests → governed test change, cited and isolated. | money/evidence |
| **A5** (new, from F-06/F-07) | `cross_fit` parameterised on a provider seam; tennis provider protocols keyed by `str` player id and relocated to `sport_tennis/`. | before first tennis model |
| **A6** (new, from F-10/F-11/F-12) | Explicit void/dead-heat/withdrawal vocabulary: outcome sum type or enforced exclusion path; `UpdateReason` governed extension. | before tennis snapshots/metrics |
| **Deferred by design** | F-08 (CLV benchmark parameterisation — after benchmark selection); F-09 (capability-enforced settlement fields — inside the SPEC-084 activation slice); F-14 (taint family — with benchmark selection); F-13 (awaits founder decision). | each cites this audit |

## Output 3 — Files changed (whole program, `c135ee5..HEAD`)

39 files, **+6,220 / −19 lines** — this is the CUMULATIVE S0–S8 implementation
footprint; the ADR 0017 audit commit itself is reports-only (two documents, zero code).
The 19 deletions are the entire footprint on pre-existing code (CLV deadband correction 0002, correction 0003's decision-unit
widening, MONEY-list wiring) — racing behaviour was not otherwise touched, and the
replay regression plus the untouched racing test suite pin that.

New packages: `sport_core/` (capabilities, adapter, interfaces, markets,
benchmarks), `sport_tennis/` (domain, adapter). New modules: `l4_pricing/
interfaces.py`, `l7_settle/tennis_rules.py`, `l7_settle/policy.py`,
`l3_features/feature_registry.py`, `l8_evidence/experiment_templates.py`,
`l6_broker/orders.py`, `l0_raw/backfill.py`, `tools/ingest_historical.py`. Modified:
`l8_evidence/clv.py` (+trial_ledger), manifest (SPEC-084 registered planned;
SPEC-070/071 activated), Makefile/CI (MONEY lists), 14 new/amended test files.

## Output 4 — New interfaces & abstractions

- **`SportCapabilities`** — the founder's 11-boolean matrix; no defaults, coherence
  refusals; core asks `supports_X`, never `if sport == ...` (structurally tested).
- **`SportAdapter` + registry** — one frozen declaration per sport of the six
  audited seams; decision unit validated against the governed ledger set.
- **Provider/model Protocol seams** — generic probability/feature/ranking seams in
  `sport_core/interfaces.py`; uncertainty-bearing seams in `l4_pricing/interfaces.py`
  (kept out of the ADR 0013 analytics boundary by construction).
- **`MarketKindPolicy`** — {WIN, MATCH_ODDS} enabled; everything else
  declared-but-refused; enablement only by governed constant edit.
- **Closing-benchmark interfaces** — `ClosingBenchmarkMethod` protocol, four
  reserved method ids, `selected_benchmark()` permanent refusal (no benchmark
  chosen).
- **`SettlementPolicy` seam** — racing by pure delegation (byte-identical, mutation-
  survivor paths stable); tennis whole-matrix refusal (SPEC-084 planned).
- **Tennis domain contracts** — closed enums, frozen Match with coherence refusals,
  thin market/settlement references; no invented data, no settlement rules.
- **Feature-declaration registry & experiment templates** — versioned declarations
  (fail-closed licensing, explicit-exclusion-only missing data); five all-string
  pre-registration templates structurally unable to hold a number.

## Output 5 — Blockers (unchanged by this audit)

ADR 0015 (account exclusion — no purchase until lawful access confirmed + month
confirmation); SPEC-084 policy matrix (blocked on Betfair tennis rules verification,
DR-TENNIS-SETTLEMENT-001); benchmark selection (DR-TENNIS-BENCHMARK-001,
evidence-driven post-pilot); all model building (no data, no models — templates
refuse to run without human-declared endpoints); Gate P1 and test-correction
proposal 0001 (await founder decisions); provider written answers outstanding.
New founder decision requested: **F-13** (reservation release semantics).

## Output 6 — Roadmap

S9 → S10 (close ADR 0017) → A2/A3 (racing-agnostic defects; small, high value) →
A1 (knowability boundary — the tennis-features gate) → A4/A5 (make the declared
seams load-bearing) → A6 (outcome vocabulary) → then the data-dependent track as
approvals land: tennis pilot purchase (ADR 0015 + month confirmation) → ingestion →
benchmark selection experiment → F-08/F-14/F-09 in their natural slices → first
pre-registered experiments via the S6 templates.

## Output 7 — Adversarial self-critique

- **The build validated its own seams; the audit had to be separate.** S0–S8 wired
  settlement, capabilities and market kinds correctly — but two other declared seams
  (cluster key, stage-one family) were decorative until audit #3 said so. Declaring
  a seam is not consuming it; the report treats only consumed seams as done.
- **Two defects (F-03, F-04) predate the program and were found only by the sport
  lens.** The close-price stack was wrong for racing itself; nothing in the racing
  test suite exercised an off-ladder close. That is a coverage smell, not merely a
  generality one.
- **The leakage hole (F-01) is the audit's most important result** precisely because
  it is invisible to grep and to racing: it only opens when an event can start
  early. Had tennis features been built first, SPEC-020's guarantee would have been
  silently false.
- **Protocol-only slices defer their contradictions** (F-07): nothing crashes while
  everything is `...`-bodied. The first concrete provider is where interface debt
  comes due; A5 pays it before then.
- **This report was produced by the same actor that built S0–S8.** The three
  auditors read code independently of the build rationale, and every finding carries
  file:line anchors a human can check — but independent human review remains the
  standard the manifest sets (`verified` state), and nothing here claims it.

## Output 8 — Pre-empirical recommendations

1. Land A2 and A3 before any data purchase — both corrupt or empty a pilot corpus.
2. Treat A1 as the hard precondition of tennis feature work; do not let feature
   authoring start on the racing boundary semantics.
3. Decide F-13 before Phase 3A resumes broker slices (it shapes SPEC-054's
   extension tests).
4. Keep S9 strictly wording; every semantic item the wording sweep uncovers is
   already scheduled above — resist folding fixes in.
5. When the SPEC-084 matrix activates, bind F-09's capability enforcement into that
   slice's red tests from the start.
6. No benchmark, no model, no probability, no stake anywhere until their evidence
   gates exist — the refusal surfaces landed in S7/S8 are the platform working, not
   gaps.
