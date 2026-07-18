# Build progress & session handover

**Living state for the build.** SPECIFICATION.md §16 requires durable state to live in files,
not the conversation. This is that file. Update it at the end of every slice.

**Branch:** `claude/project-files-followup-dif8al` · **Last updated:** 2026-07-16

---

## Status at a glance

| | |
|---|---|
| Active SPEC-IDs covered | **24 of 24 — the entire active surface** (SPEC-001–004, 010–012, 020–024, 050–054, 080/082, **093**, 100–103) |
| Tests | **525 passing** (unit + property + failure-injection + replay-regression; 349 -> 525 in the 2026-07-16 gate-evaluator slice) |
| Static checks | `mypy --strict` clean (139 files), `ruff` + `ruff --select ARG` clean, `pylint W0613` 10/10 |
| Commits on branch | 82 |
| Phase | 2 (offline research), first Phase-2 money slice landed |
| `make verify` overall | **GREEN** ✅ — all active IDs covered and consistent |
| `make mutants` | **`l8_evidence/gates` ENFORCED and 100% clean: 617 mutants, 617 killed, 0 survivors, 0 classifications needed.** `l7_settle` ENFORCED: 329/321/8 founder-approved equivalents (ADR 0010). `l5b_risk` report-only. |

The whole platform is a **research/measurement platform, not a betting bot**, conditionally
approved for **offline work through Phase 2 only** (no live credentials, no real money, no
Kelly, no passive execution). See `docs/HALT-CHECKLIST.md`.

---

## What is implemented

### Verification harness — `tools/` (support/evidence) · ADR 0001
The enforcement backbone ("status comes from CI"). Four scripts, each with unit tests in
`tests/unit/tools/`:
- `check_spec_coverage.py` — every enforced `active`/`verified` ID has a `@pytest.mark.spec`
  test; property test required for `money` IDs; causal-declaration completeness; unknown-ref
  and verification-loss (money-downgrade) detection.
- `check_facts_freshness.py` — stale/misconfigured facts (unpopulated entries pass).
- `check_import_quarantine.py` — transitive static import-graph (SPEC-100 mechanism).
- `emit_traceability.py` — SPEC-ID → tests matrix.
- `run_mutation.py` — **deferred** to the first money module to mutate (ADR 0001).

### L0 raw truth layer — `l0_raw/` (SPEC-001, 002, 003[money], 004) · ADR 0002
- `clock.py` dual wall+monotonic `ClockStamp`; `latency_ns` monotonic-only, cross-domain-safe.
- `records.py` frozen Pydantic contracts + verbatim framing + checksum-verified decode.
- `store.py` `AppendOnlyLog` — byte-for-byte payload, no update/delete API, fsync (file + dir).
- `capture.py` preserves duplicates/order; §6.2 provenance.
- `commands.py` `CommandGateway` persists the send event **before** the transport; fails closed.
- Tests: `tests/{unit,properties,failure_injection}/l0/`.

### L1 deterministic reducer — `l1_reduce/` (SPEC-010, 011, 012) · ADR 0003
- `mcm_v1.py` `reducer-mcm-v1` reduces Betfair MCM → book state (image/delta, batb/batl/atb/atl,
  ltp/tv, marketDefinition); pure, **Decimal not float**.
- `canonical.py` deterministic serialisation + sha256 canonical hash (representation-canonical).
- `reducer.py` registry keyed by immutable version; refuses unknown versions; old versions kept.
- `replay.py` reconstruct L2 from the L0 log; golden-hash regression enforces version bumps.
- Tests: `tests/unit/l1/`, `tests/properties/l1/`, `tests/replay_regression/l1/`.

### L3 knowledge-time & leakage — `l3_features/` (SPEC-020–024, all evidence) · ADR 0004
The evidence-integrity framework (no money logic; nothing stubbed). Concrete features await
the frozen `specs/prices/info-price-v1.yaml` and are intentionally not built.
- `knowledge_time.py` `KnowledgeStamps` (§6.3 stamps) + `SourceProvenance`; `assert_knowable_before_off`
  raises `LeakageError` (a build-time error, not a `ValueError` — propagates unwrapped past
  pydantic) unless first-usable is strictly before the off; coherence floors vs ingestion/publication;
  backfill must declare true publication time and cannot back-date knowability. SPEC-020, 023.
- `build_context.py` `FeatureBuildContext` with explicit `BuildMode`; actual-off unreachable in
  live mode — rejected at construction **and** in the derived method. SPEC-022.
- `leakage.py` + `l8_evidence/reconciled_bsp.py` two-mechanism BSP guard: a static import-graph
  gate (l3 ⇏ `l8_evidence.reconciled_bsp`, wired into CI + Makefile + CI-AND-TRUST.md) and a
  runtime taint-marker guard that never imports the grading-only module (anti-drift test pins
  the two literals equal). SPEC-021.
- `feature_set.py` reproducible, order-independent, float-free `feature_set_hash`; `build_feature`
  is the single guarded construction path. SPEC-024.
- Tests: `tests/unit/l3/`, `tests/properties/l3/`.

### L5 decision layer — `l5_decision/` (SPEC-050–054, all money) · ADR 0005 · **first money module**
The three rules in force: nothing stubbed, no test weakened, no LLM in any numeric path; every
money ID has a spec-marked **and** a property test.
- `ladder.py` canonical 350-tick Betfair ladder (exact `Decimal`); `price_of`/`index_of` exact
  inverses via value-keyed lookup; floats/bools rejected as indices, floats rejected as prices;
  off-ladder prices raise. **No float ever represents a price.** SPEC-053.
- `prices.py` `OddsExec` / `MarketInfoPrice` / `ClosePrice` — **unrelated** frozen strict types,
  so the type system prevents conflation; consumers also guard at runtime. SPEC-051.
- `ev.py` `expected_value = p·(O−1)·(1−c) − (1−p)` (exact `Decimal`); consumes a
  `WinProbabilityLowerBound` (conservative bound, never a point estimate — anticipates SPEC-034),
  `OddsExec`, `CommissionRate`; runtime guards reject `p_close`/`p_market_info`/bare probability.
  Declared monotonicities property-tested. SPEC-050.
- `one_runner.py` `select_market_position` (highest conservative net EV, lowest-id tie-break,
  rejected recorded, order-independent) + `MarketPositionLedger` refusing any second position.
  Identifiers bounded (`selection_id > 0`). SPEC-054.
- `execution.py` `TakerV1Order`/`taker_v1` pinned to FOK + LAPSE + minFill==full stake +
  `market_version` (`>= 0`), back-only; passive posting unreachable; stakes are integer minor
  units. SPEC-052.
- Tests: `tests/unit/l5/`, `tests/properties/l5/`.

### Governance — `governance/` (SPEC-100–103) · ADR 0006
Cross-cutting guarantees; `governance/` is under money-module CI enforcement (pylint W0613 +
escape-hatch grep + `MONEY`). SPEC-102/103 are money.
- `app_key.py` (SPEC-102) `LiveAppKey`/`DelayedAppKey`; `RealMoneyPlacementAuthorization`
  constructable only from a `LiveAppKey` — enforced by mypy **and** a runtime `__post_init__`;
  factory refuses delayed keys. Real money impossible on a delayed key by construction.
- `budgets.py` (SPEC-103) three independent `BudgetAccount`s (exact integer minor units); **no**
  transfer/credit API, only per-account `debit`; `__post_init__` enforces field/kind + non-negativity.
- `licensed_sources.py` + `docs/licensed-sources.yaml` (SPEC-101) Gate-−1 check fails (fail-closed)
  if any `operational` source lacks verified rights; sources seeded `candidate`, rights unverified.
- SPEC-100 verified via the existing `tools/check_import_quarantine` mechanism (test only).
- Tests: `tests/unit/governance/`, `tests/properties/governance/`.

### L7 market-level settlement — `l7_settle/` (SPEC-080/082, money) · ADR 0007
Commission on the **net market result**, never per-order; exact integer minor units / `Decimal`.
- `pnl.py` per-position gross P&L: win/lose/void, Betfair reduction factors, dead-heat split,
  per-bet `ROUND_HALF_UP`.
- `settlement.py` `settle_market` → `MarketSettlement` (§6.8 schema); commission only on net
  winnings; unknown-status raises `SettlementBlocked`; void→0 P&L (but transaction charges still
  apply); scenario payoff matrix.
- `ledger.py` idempotent duplicate acks, versioned resettlements, conflict/stale refusal.
- Advisory-verified P&L arithmetic; hardened (void charges, hashability, scenario keys).
- Tests: `tests/unit/l7/`, `tests/properties/l7/`.

### L8 gate evaluator — `l8_evidence/gates/` (SPEC-093, money) · ADR 0011 · **first Phase-2 money module**
Deterministic four-valued promotion-gate verdicts; an LLM never decides a gate. Built in the
ADR 0011 order: `specs/gates/v1.yaml` frozen FIRST (structure only — a test pins zero numeric
leaves; boundaries live in each experiment's §9.7 record, economics in `docs/facts.yaml`),
failing tests committed separately, then the implementation without touching them.
- `outcomes.py` `GateOutcome`/`GateResult` — four-valued, frozen, `bool()` raises by
  construction; canonical sorted-key JSON (byte-identical for identical inputs).
- `spec.py` structure-only loader (numeric leaves refused), alias resolution (GATE-0B→GATE-3),
  sha256-bound to the spec bytes; singleton-free validation (frozenset membership, dict
  dispatch, seen-set duplicate walks — zero equivalent-mutant surface).
- `experiment.py` §9.7 record loader — Decimal-from-string or int only, floats refused.
- `facts.py` §13.5 join: any populated fact past/without `recheck_by` → FAIL_HARM
  registry-wide; a gate-required unpopulated fact → CONTINUE.
- `evaluator.py` pure `evaluate()` (no clock, no I/O): severity aggregation — harm (stale
  facts, false-harm items, budget breach, upper<harm) dominates futility dominates continue;
  PASS needs every item true, fresh facts, exact-multiplication multiplicity
  `(1-confidence)x(trials+1) <= alpha`, and lower > minimum effect; max_n without efficacy →
  FAIL_FUTILITY. `payback_v1` compares `c_fixed <= max_years x annual` (multiplication only).
- `cli.py` + `__main__.py` — pinned contract via `uv run python -m l8_evidence.gates
  evaluate …`; exit codes PASS 0 / CONTINUE 1 / FAIL_HARM 2 / FAIL_FUTILITY 3 / error 4
  (an error is never a verdict). No console script: the workspace root is unpackaged
  (deviation recorded in ADR 0011).
- **Mutation: 617/617 killed, zero survivors, zero classifications** — annotation mutants
  die via a `get_type_hints` sweep (the l7 pattern), plus ~40 targeted killers.
- Advisory spec-verifier pass on the slice: clean; its forward-dependency note (attestation
  provenance belongs to SPEC-091's ledger schema) is recorded in ADR 0011.
- Tests: `tests/unit/l8/`, `tests/properties/l8/`.

### Mutation harness — `tools/run_mutation.py` (ADR 0008)
Discharges ADR 0001's deferral. Drives `cosmic-ray` (init/exec/dump) per target; enforces a
human-approved classification file `specs/mutation-survivors.yaml`. `--require-kill-non-equivalent`
fails on unclassified/`test-deficiency` survivors; `--report` lists; empty targets skipped. The
CI `mutants-critical` job runs it (gates enforced but `planned`/empty; `l7_settle` report-only).
`cosmic-ray` is now a dev dep. **Caution:** never run a full mutation foreground and interrupt it —
cosmic-ray leaves a mutant applied if killed mid-test (`git checkout -- <module>` to recover).

---

## Coverage map

**Covered (24 — the entire active surface):** SPEC-001–004 (L0) · SPEC-010–012 (L1) ·
SPEC-020–024 (L3) · SPEC-050–054 (L5) · SPEC-080/082 (L7) · SPEC-093 (L8 gates) ·
SPEC-100–103 (governance).

**Remaining active: none.** `make verify` is green.

`planned` IDs (L4 pricing, L4b fill, L5b risk, L6 broker, the rest of L8 evidence,
SPEC-081/083/104) are not yet CI-enforced. Per the standing progression plan each Phase-2 ID is
activated (`planned → active`, enforcement-increasing only) once implemented and covered —
SPEC-093 was activated this way with its rationale in ADR 0011.

---

## 2026-07-16 retrospective audit (founder-requested) — ADR 0010

Six clause-by-clause component audits + git-history integrity scan + fresh CI-grade runs.
**Verdict: no rule-2 violations, no stubs, no silent trims; spec/manifest/facts/rules
untouched since bootstrap.** All findings were verification-net gaps or structural
hardenings; every one is remediated on this branch (see ADR 0010 for the full table):

- l3: leakage guards are now structural on the `Feature` type (context-required mint);
  build mode wired into the single path; aware datetimes normalise to UTC so equal instants
  hash identically.
- l0/l1: `config_digest` + `container_digest` recorded (all four §6.2 digests now exist,
  outside canonical bytes — golden hashes unmoved); reducer source pinned (SPEC-012 now
  mechanical); `stream_clock` widened to the opaque string token Betfair actually sends;
  order-corruption + per-append-fsync tests added.
- l7: SPEC-082 holes closed (multi-runner, ABANDONED, multi-factor RF, dead-heat×RF,
  rounding discriminators, pnl property suite, field whitelists, post-resettlement ledger
  edges); two semantics-identical mutation-hostile restructures (pnl fast path removed,
  ledger.apply reordered).
- governance/tools: nominal budget account types (mypy layer + exact-type runtime backstop);
  quarantine checker sees literal dynamic imports and fails closed on non-literal ones and
  unparseable reachable files; standalone SPEC-101 licensing check in verify + CI;
  escape-hatch grep broadened (case-insensitive, synonyms, bare `pass`) and extended to the
  evidence layers; SPEC-080/082 causal declarations added to the manifest.
- Recorded (no code): the mutation-harness slice violated tests-first ordering (support
  tool, one commit, nothing weakened); SPEC-082's "unknown order status after timeout"
  order-level half belongs to SPEC-070/l6_broker (phase 3); platform branch-protection
  settings remain unverifiable from inside the repo.

**Founder approval received (2026-07-16, session chat):** the eight equivalent-mutant
classifications are live in `specs/mutation-survivors.yaml` with `approved_by`, the pin test
was corrected in the same human-approved change, and `l7_settle` mutation is now ENFORCED in
Makefile + CI. No founder actions pending.

---

## Next — autonomous progression into Phase 2 (offline)

The active Phase-1 surface is complete and `make verify` is green. The project is **founder-hands-off**:
implementation, verification, docs, and progression are the agent's job, not the founder's. The
approval posture (`docs/HALT-CHECKLIST.md`) **pre-approves offline implementation through Phase 2**,
so the next work proceeds autonomously on this feature branch:

- **Phase 2 build order (offline):**
  1. ✅ **Done (ADR 0009)** — froze `specs/prices/{info,exec,close}-v1.yaml` before any data
     was read (correct pre-registration).
  2. ✅ **Done (ADR 0011, this session)** — `specs/gates/v1.yaml` frozen + L8 gate evaluator
     (SPEC-093, money, `active`, 617/617 mutation kill). Continue at step 3.
  3. ✅ **Done (ADR 0012, this session)** — L4 pricing framework (SPEC-030–035, all `active`):
     pure-Python deterministic conditional logit, meeting-day cross-fit with typed OOF provenance
     (verified at production AND consumption), stage two on OOFFundamental + MarketInfoPrice,
     WinProbabilityDistribution -> l5 lower bound only, grouped-softmax-only objectives, §6.12
     manifest. Synthetic closed-form fixtures; real fitting stays data-gated.
  4. ✅ **Done (ADR 0013 + addendum, this session)** — analytics-consumer foundations
     (founder's SPEC-036–042 remapped to 036–039 + 044–048; Amendment A folded in).
     `active`: SPEC-036 probability outputs, SPEC-037 immutable snapshots with vintage
     lineage + knowledge-time/backdating guards, SPEC-038 predictor metrics + versioned
     benchmark registry, SPEC-039 deterministic explanation inputs (self-verifying digest),
     SPEC-044 output-rights lineage (fail-closed), SPEC-045 export contract (three
     independent statuses; recommendation hard-pinned NOT_EVALUATED). `planned`: SPEC-046
     Gate P1 (structure pre-registered in specs/gates/predictor-p1.yaml + pin tests;
     activation human-only after Gate 1 results), SPEC-047/048 manifest-only. Also:
     price_contracts/ shared neutral package (MarketInfoPrice/OddsExec/ClosePrice + ladder
     relocated from l5_decision, pure re-export shims + purity test) and the continuously
     enforced analytics→trading import-boundary test. £499 constraint held — no paid deps.
  5. ✅ **Mostly done (this session)** — L8 evidence core, all `active`: SPEC-091 trial
     ledger (ledger-derived prior-trial count, registration-digest tamper guard, attestation
     provenance closing the ADR 0011 forward dependency, round-trip into the SPEC-093
     evaluator's multiplicity arithmetic), SPEC-092 lockbox (event-sourced, log-then-grant,
     Gate-1 read consumes, burns absorbing), SPEC-090 race-level paired inference (d_r,
     meeting-day block bootstrap, no runner-level surface), SPEC-094 derived sample size
     (Acklam inverse CDF, borrowed-constant scanner over both gate specs), SPEC-095 CLV
     diagnostic family (four structurally distinct types; realised-fill CLV unconstructable
     without a fill; BSP/pre-suspension-WAP benchmarks never merged; not a training target
     by import direction), SPEC-097 calibration extensions (Wilson-CI reliability curves,
     adaptive equal-count bins, race-renormalised temperature scaling, non-comparable ECE
     diagnostic). **Every Phase-2 evidence ID is now active.** Remaining planned in l8:
     SPEC-096 anytime-valid monitoring (Phase 5, live-adjacent, stays planned).
- Activate each Phase-2 ID (`planned → active` in the manifest) **only once it is implemented and
  covered**, so `make verify` stays honest/green. Record the activation rationale in the ADR.
- Later: Phase 3 (L5b risk, L6 broker, reconciliation SPEC-081/083, SPEC-104) and Phase 5 (L4b fill,
  SPEC-096) — but those cross toward live execution and stay HALTED by the approval posture until their
  gates are met.

**What is genuinely not an agent action (and is NOT blocking offline work):**
- **Deciding a gate** — SPEC-093/CLAUDE.md: an LLM may explain a gate result, never decide one. The
  evaluator is deterministic; Gate 1/2/… PASS/FAIL are read from evidence, not authored by the agent.
- **The live trust boundary** — protected `main`, PR review, a second CODEOWNERS reviewer, signed
  images. By design these are not the agent's to self-configure (self-attestation would defeat them),
  and they only matter at the **live** boundary (Phase 3+), which is halted regardless. Offline research
  does not need them; work continues on the feature branch without a PR.
- **Commit signing** — the environment's SSH signing key is a 0-byte placeholder, so every commit is
  *Unverified*. This is an environment fact, fixable by neither the founder nor the agent here; it is a
  live-boundary prerequisite, not a current blocker.

---

## How to resume a session

1. Read `docs/spec-manifest.yaml`, this file, and the path-scoped rule for the layer you touch
   (`.claude/rules/`).
2. `uv sync` (installs the dev toolchain into `.venv` via the proxy).
3. Pick **one spec slice** (a handful of related IDs — SPECIFICATION §16).
4. TDD to the letter: write failing tests → **commit them separately** → implement without
   editing tests → verify. Commit an ADR first if the design has non-obvious choices.
5. Verify with the real toolchain (what CI runs):
   ```
   uv run pytest tests -q
   uv run mypy --strict .
   uv run ruff check .            # and: uv run ruff check --select ARG .
   uv run python tools/check_spec_coverage.py --manifest docs/spec-manifest.yaml \
       --enforce-states active,verified --require-causal-declarations --require-properties-for money
   uv run python tools/check_facts_freshness.py --registry docs/facts.yaml
   uv run python tools/check_import_quarantine.py --forbid research.scraping --from l5_decision l5b_risk l6_broker
   ```
   `check_spec_coverage` reporting the remaining active IDs as uncovered is the harness
   **working**, not failing.
6. Before claiming done, run the advisory spec-verifier subagent (§16.4) on the diff and act on
   its findings. It is advisory only — never a gate.
7. Commit (tests separate from implementation), push, then update this file.

**Conventions established:**
- Tests declare coverage with `@pytest.mark.spec("SPEC-0XX")` (function/class/module `pytestmark`);
  skipped/xfail tests do not count. Money IDs need a property test under `tests/properties/`.
- Golden/replay fixtures pin canonical hashes; a logic change must bump the reducer/artifact
  version or the regression fails.
- Hypothesis' wall-clock deadline is disabled suite-wide (`tests/conftest.py`) because the
  fsync-bound L0 property tests would otherwise flake under load. Keep new I/O-bound property
  tests aware of this; it is not a licence to write slow tests.

---

## Decisions (ADRs)

| ADR | Title |
|---|---|
| `docs/decisions/0001-verification-tooling.md` | marker-based SPEC coverage; run_mutation deferred; checker/pytest division of labour |
| `docs/decisions/0002-l0-raw-truth-layer.md` | dual clock; append-only framing; two-event API command; persist-before-send; dir fsync |
| `docs/decisions/0003-l1-reducer.md` | Decimal-not-float; canonical hash; reducer registry/versioning; MCM-v1 scope |
| `docs/decisions/0004-l3-knowledge-time.md` | knowledge-time stamps; LeakageError-not-ValueError; two-mechanism BSP guard; live actual-off exclusion; no-float feature hash |
| `docs/decisions/0005-l5-decision.md` | canonical tick ladder; three distinct price types; exact-Decimal EV; conservative-lower-bound typing; one-runner selection+ledger; taker-v1 pinned order; mutation harness deferred to L7 |
| `docs/decisions/0006-governance.md` | governance/ package + money-lint; SPEC-100 via existing quarantine; licensed-source registry; no-delayed-key by type + runtime backstop; budget separation by absence of transfer |
| `docs/decisions/0007-l7-settlement.md` | commission on net market result; per-position P&L (RF, dead heat); per-bet ROUND_HALF_UP; unknown-blocks; idempotent versioned ledger |
| `docs/decisions/0008-mutation-harness.md` | cosmic-ray driver; survivor identity + classification file; report vs enforce; empty targets skipped |
| `docs/decisions/0009-price-preregistration.md` | specs/prices/{info,exec,close}-v1.yaml frozen before any data read |
| `docs/decisions/0010-retrospective-audit.md` | 2026-07-16 clause-by-clause audit; equivalent-mutant classifications; worktree/green-baseline mutation lessons |
| `docs/decisions/0011-gate-evaluator.md` | frozen structure-only gate spec; four-valued never-boolean verdicts; severity-aggregation precedence; exact-multiplication multiplicity; facts join; python -m CLI; SPEC-093 activation |
| `docs/decisions/0012-l4-pricing.md` | pure-Python deterministic two-stage pricing; typed OOF cross-fit provenance; edge-distribution type boundary; grouped-softmax-only objectives (SPEC-030–035) |
| `docs/decisions/0013-analytics-consumer.md` | analytics consumer: SPEC-ID remapping (040–044→044–048); read-only import boundary; Amendment A vintage/status/benchmark rules; price_contracts relocation addendum; Gate P1 planned |

---

## Operational notes / constraints

The project is founder-hands-off; the agent progresses the work. The items below are facts and
constraints, not chores routed to the founder.

- **`make verify` is green** (all active IDs covered). `make mutants`/CI `mutants-critical` runs the
  live `tools/run_mutation.py` (ADR 0008): `l8_evidence/gates` is `--require-kill-non-equivalent` but
  still `planned`/empty (vacuous pass); `l7_settle` is report-only. When gates are built, classify their
  surviving mutants in `specs/mutation-survivors.yaml` or kill them with tests — an agent task.
- **`specs/prices/*-v1.yaml` are frozen (v1, ADR 0009).** `specs/gates/v1.yaml` remains to be
  authored with the L8 gate-evaluator slice — its pre-registered endpoints (§9/§10) are a
  separate pre-registration, done before that slice examines any data.
- **Commit signing** — the environment's SSH signing key is a 0-byte placeholder, so every commit is
  *Unverified* (committer identity is correct). Neither founder nor agent can fix this here; it is a
  live-boundary prerequisite, not a current blocker. Work continues on the feature branch.
- **Live trust boundary** (protected `main`, PR review, second CODEOWNERS reviewer, signed images):
  by design not the agent's to self-configure, and only relevant at the **live** boundary (Phase 3+,
  halted). CODEOWNERS currently points at `@allansdouglas1983-cmyk` by default. No PR is open (offline
  research does not need one).

## ADR 0017 program record (2026-07-17)

The sport-agnostic transition landed as slices S0–S9 on `claude/project-files-followup-dif8al`
(head green: `make verify` 1,662 tests / 44 enforced IDs / mypy clean; `make replay` green):
S0 baseline (correction 0002 merged; SPEC-070/071 broker core activated; historical ingestion),
correction 0003 (decision units {race, match}), S1 `sport_core` (capability matrix + adapter
registry), S4 `sport_tennis` domain contracts, S5 provider/model protocol seams (uncertainty
seams pricing-side per the ADR 0013 boundary), S7 tennis settlement contracts (SPEC-084
registered `planned`, whole-matrix typed refusal), S8 market-kind policy ({WIN, MATCH_ODDS}
only) + benchmark interfaces (none selected), S3 settlement-policy seam (racing pure
delegation, byte-identical), S6 feature-declaration registry + five numeric-free experiment
templates, S9 founder-approved vocabulary batch (manifest texts, info-price-v2 reissue with
scope block, SPECIFICATION §22, CLAUDE.md/rules; symbol renames deferred — no aesthetic churn).
Cumulative S0–S8 code footprint: 39 files, +6,220/−19; the audit commit is reports-only.

**Closing evidence:** `docs/architecture/conceptual-coupling-audit.md` (F-01..F-16, full-file
clearances) + `adr-0017-phase1-report.md` (required outputs 1–8). **Ownership register:**
`docs/architecture/adr-0017-findings.yaml`. **Founder-fixed follow-on order:** A2 ClosePrice →
A3 backfill replay → A1 knowability boundary → A6 outcome vocabulary → A4 cluster key → A5
provider seam/OOF orchestrator. Hard gates: A2+A3 before any data purchase; A1 before any
tennis feature work. F-13 ruled (zero-fill FOK release; see ADR 0017 addendum). Standing
blocks unchanged: ADR 0015, SPEC-084 refusal, no benchmark, no models, no live orders.

## Stage-1 closure: June-2026 tennis market-feasibility pilot (2026-07-18)

The pilot ran under the ADR 0015 carve-out (one historical month, no live activity) and is
formally CLOSED. Evidence frozen at `docs/evidence/pilot-2026-06-tennis/` (corpus manifest
`d6d2f44b…`, universe `ce9a147e…`, canonical replay `be2ae21a…`, deterministic reconstruction
`3c1b64ab…` — proven byte-identical across independent runs, zero errors, zero off-ladder
prices). **Gate M0 (market adequacy): PASS**, scope-bounded to the June regime
(`specs/gates/market-m0.yaml`); profitability explicitly out of scope and no outcome ever
opened. Programme review: ADR 0018 (questions answered/unanswered, assumptions disproved —
incl. the placeholder `earliest marketTime` anchor, corrected mid-pilot by governed founder
decision to the as-of-published-marketTime horizon state machine; critical failure-mode
ranking: M2 futility most likely). Baseline frozen machine-readably at
`specs/programme/baseline-v1.yaml`: tennis / MATCH_ODDS / singles; June universe (2,876;
strict 2,287 sensitivity tier; doubles descriptive); T-10m→T-5m horizon target; benchmark
UNSELECTED; models NOT_STARTED; live PROHIBITED (ADR 0015 unaffected). Stage 2 (probability
engine → P(model), NOT betting) defined at `docs/architecture/stage2-probability-programme.md`
with the F0–F7 family roadmap and the M0→M1→M2→M3→M4→canary→production gate ladder (one
question per gate; M4 the only profitability gate; canary unschedulable while ADR 0015
stands). Stage-2 slice activation remains human-controlled; first slices are outcome-opening
protocol, tennis lockbox freeze, and pre-registration — before any result is read.

## Stage 2A: lockbox, outcome governance & pre-registration (2026-07-18)

Validity-protection slice BEFORE any probability model. Landed on
`claude/project-files-followup-dif8al` (full `make verify` green: 272 files mypy-strict,
+23 tests, import-quarantine incl. the new l8_evidence.tennis_outcomes boundary).
**Structural anti-contamination (completes SPEC-092's deferred data-layer block):**
`specs/evidence/outcome-field-classification-v1.yaml` (every corpus field classified
SAFE/OUTCOME_CONTROLLED/POST_SETTLEMENT/UNKNOWN, fail-closed, human-owned) + `l8_evidence/
outcome_fields.py` (assert_pre_lockbox_readable, value sentinels, replay-provable
PreLockboxAccessRecorder) + `l8_evidence/tennis_outcomes.py` (single refusing outcome home,
import-forbidden from l3_features/l4_pricing). **Governance:** `.claude/rules/
stage2-evidence-discipline.md` (no modelling decision from returns/ROI/CLV/hindsight/winner
inspection pre-opening); `docs/architecture/stage2a-lockbox-protocol.md` (full protocol,
Task 1); `docs/experiments/STAGE2-tennis-preregistration.md` (master pre-registration,
numeric boundaries PENDING FOUNDER, Task 4); `docs/architecture/
reschedule-operational-policy.md` (RECOMMENDED stability-window policy vs rejected first/
latest/refresh, outcome-blind, Task 5); `docs/architecture/
stage2a-readiness-and-stage2b-plan.md` (readiness = YES WITH BLOCKERS in dependency order,
Task 6; Stage 2B = F0 market baseline + F1 null first, then F2 Elo, Task 7). No model,
feature, parameter or outcome read; no governance weakened; no numbers invented. Blockers
before outcome modelling: (1) founder resolves pre-reg numbers + dwell W; (2) define/seal
tennis lockbox; (3) authorise outcome-opening (implement tennis_outcomes); (4) license
longitudinal results (Gate -1); (5) competitor-identity resolution.

## Stage-2A acceptance executed: seal, extractor, packets (2026-07-18)

Founder decisions 1-5 executed on `claude/project-files-followup-dif8al` (make verify
green, 273 files mypy-strict). **Sealed:** the ENTIRE June-2026 primary singles universe
(2,876 members, 2,287 strict-tagged; doubles excluded) — `specs/evidence/
lockbox-june-2026-tennis-v1.yaml`, seal digest `sha256:24df4bd2…`; alpha_total=0.05
family-wise + power=0.80 recorded as a dated pre-registration amendment; training data
must end before 2026-06-01, never solved by opening part of June. **Implemented (tests
first):** the governed outcome extractor `l8_evidence/tennis_outcomes.py` — pre-June
scope ONLY (June structurally unrepresentable in the scope vocabulary), sealed-membership
refusal, data-level marketTime>=June refusal, manifest-bound OutcomeAccessAuthorisation
(experiment/model/feature/data/gate) stamped on every extraction; unauthenticated path
still refuses; unambiguous exactly-one-WINNER pattern only, anything else refuses
(SPEC-084 not re-invented). **Evidence packets (outcome-blind, digest-pinned,
`docs/evidence/stage2b-planning-packets/`):** A (candidate delta grid: diffuse 1-point
signal invisible+cost-blocked; candidates 1e-4..1.3e-3 nats), B (planning sigma_d p90 =
0.04075; N table at power .80, family-wise alpha .05: ~15k..millions), C (dwell W 15-120s
indistinguishable; ~82-88% of decisions see a LATER revision at every (W,L) — the real
policy question is the governed response to post-decision revisions). **DR-TENNIS-
RESULTS-001** filed (11-point longitudinal-results licensing; silence never permission;
non-commercial never deployable). Readiness: YES WITH BLOCKERS — remaining: founder
declares delta/sigma_d/W(+revision-response policy); DR-TENNIS-RESULTS-001 returns +
Gate -1; F0/F1 harness authorised and unblocked. NO June outcome was read at any point.

## Zero-cost-first results routing prepared (2026-07-18)

Founder direction executed as preparation only — nothing purchased, downloaded, or
subscribed; all portal interaction remains founder-only (ADR 0015). Prepared:
(1) Betfair BASIC May-2026 GBP-0 sufficiency pilot runbook + exact portal selections +
stop-if-not-zero rule + the 8-point verification protocol (terminal WINNER/LOSER,
void handling, May-June selection-id stability, singles classification, chronological
completeness, extractor compatibility, M-only dedup, exclusion retention) — outcome
reads via the governed extractor under a pilot authorisation, pre-June scope, June
sealed throughout; BASIC scope-capped to global Elo / outcome-only BT / recency counts;
proposed backfill 2021-01..2026-05 with cold-start audit gating anything earlier.
(2) Tennis-Data.co.uk permission email draft (8 explicit permissions; silence never
permission; nothing ingested until rights registry entry). (3) Paid fallbacks prepared
not purchased: SportsDataAPI free/$19.99 + API-Tennis $40/mo (8+2 written questions,
trial needs founder approval). (4) Updated Gate -1 decision tree
(docs/procurement/results-data-gate-minus1-decision-tree.md). F0/F1 harness work
remains authorised and unblocked in parallel.

## Tennis-Data approved & executed: acquisition, audit, identity bridge (2026-07-18)

Founder approved Tennis-Data.co.uk as primary longitudinal results source (single-user
personal scope; no further provider search; paid fallbacks not required). Executed:
**acquisition** — 47 raw files (ATP 2000-2026, WTA 2007-2026) with per-file provenance
(URL, timestamp, provider headers), sorted manifest digest `d9af2525…`, vintage
discipline (no overwrites), raw outside repo, archive bundled for founder private
storage (`8c7e715c…`). **Acceptance audit** (§3, boundary 2026-06-01 strict): 117,276
pre-June singles (ATP 70,631 / WTA 46,645); 620 post-boundary rows counted-never-read;
comment vocabulary fully enumerated (3,624 RETIRED, 691 WALKOVER, 3 AMBIGUOUS); surfaces
COMPLETE (zero missing — F3 field validated); 1 winner-conflict excluded; rankings
present but DEFERRED on knowledge-time; odds columns catalogued by name only +
QUARANTINED. **Field registry frozen** (`specs/evidence/tennis-data-field-registry-v1.yaml`).
**Identity bridge implemented** tests-first (`sport_tennis/identity_bridge.py`, 12 tests):
td-norm-v1, namespaced td-atp/td-wta CompetitorIds, homonym/cross-namespace refusal,
append-only corrections, unresolved ledger; June-vs-TD run (names only): 657/1,471
players, per-market both-mapped 1,218/2,876 (42.4%; strict 50.5%) — lower-tier gap is
explicit abstention, kept in denominators. **Corpus design proposed**
(`docs/architecture/pre-june-development-corpus-design.md`). **Gate −1: CONDITIONAL
PASS** — blocked only on ingesting the written approval evidence file
(`docs/procurement/tennis-data-rights-and-gate-minus1.md`; matrix drafted; recheck =
provider date else +12 months). No June outcome read; no odds value in any pipeline.

## Gate −1 PASS on founder attestation (2026-07-18)

Founder decision: the written Tennis-Data approval stays private to the founder
(security); Gate −1 for tennis-data-couk marked PASS ON FOUNDER ATTESTATION within the
exact single-user personal scope — no evidence fields fabricated, no digest recorded;
registry entry permitted/verified_by-founder/recheck 2027-07-18; residual-risk record:
PASS is void-forward if the provider's terms are ever found narrower. F2 blockers now:
ONLY the founder declarations (delta, sigma_d, W/L + post-decision-revision response).

## Pre-registration COMPLETE; policy frozen; 0003 landed; CI green (2026-07-18)

Founder declarations frozen (specs/programme/preregistration-constants-v1.yaml):
alpha_total=0.05 family-wise, power=0.80, delta=0.0007 nats (paired mean per-match),
sigma_d=0.04075 (explicit planning assumption), W=60s, L=300s; derived N (platform
code): 26,600 @ a=.05 / 41,039 @ a=.05/6. Reschedule policy frozen:
COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE (9 founder rules; F-13 retries are execution, not
new decisions; time passage never material). Test-correction 0003 applied per founder
conditions (representability guard, 128-ULP anchored, examples pinned; production
untouched) — **full make verify GREEN repo-wide (275 files)**. Label policy: completed-
only primary (retirements/walkovers/awarded/DQ excluded, visible); cold-start rule NOT
activated (governed prior + banded reporting 0/1-4/5-9/10-19/20+). June F2/F3
eligibility manifest FROZEN (digest 96bd1f12..., derived from rules not hard-coded):
2,876 -> F2-eligible 1,218 (strict 1,155 / primary-only 63); bands 1-4:422, 5-9:138,
10-19:134, 20+:524; F3 June emission 0 (JUNE_SURFACE_SOURCE_MISSING, governed source
needed); 1,658 EXCLUDED_IDENTITY visible in the coverage ledger. Development design
SELECTED: Design B (warm<=2018; OOF 2019-01..2025-05 = 29,111; validation
2025-06..2026-05 = 4,935; eval 34,046 — adequate @ a=.05 single, NOT @ .05/6; COVID-2020
inside OOF recorded as regime cohort). Gate -1 CLOSED (attestation scope); Gate 1/M1
NOT evaluated; June sealed; no odds in fundamental pipeline; no paid provider. F2
implementation + pre-June training AUTHORISED (all four §9 preconditions met).

## Stage 2B executed: F0, F1, F2 first evaluation (2026-07-18)

Gate-role clarification + pre-reg amendment 3 (no pre-June market-relative claims).
F0 June yardstick RUN: 2,518/2,876 committed decisions (manifest 90b80100...), typed
refusals, info-price-v2, no outcome read. F1 structural null + harness-leakage suite
through the REAL orchestrator (row-order cannot create information; ignoring-inputs
detected; byte-identical reruns). F2 registered (f2-global-elo-registration-v1) and
evaluated under Design B via cross_fit + additive score_only_after warm-up threshold
(fixes OOM 137; default byte-identical, test-pinned): ATP K*=24 OOF ll .62645 / val
.6256; WTA K*=32 OOF .62123 / val .6199 (null ln2=.69315; slopes .83-.85 = measured
overconfidence, no calibration fitted per registration; cold-start benign, 10-19 band
weakest in validation ~.70-.72). Same-day policy frozen: batch-update (12,182 affected
matches counted first; 911 OOF / 88 val). Alpha map: two confirmatory trials at .975
exhaust the .05 budget (F3-vs-F2 powered: 32,212<=34,046; June M2 CONTINUE by design).
No June outcome, no odds in F2, no ROI/CLV/P&L anywhere. make verify green (280 files).

## Stage 2B confirmatory-integrity slice (2026-07-18)

F3 authorised as the sole confirmatory challenger; scoring NOT run (frozen first).
Confirmatory-evaluation integrity audit (docs/architecture/...): F2's K was OOF-selected,
so nested chronological cross-fitting is REGISTERED (Design A) — warm-up <=2018 selects
the 2019 block, each outer year re-selects on its past; confirmatory-eligible = ALL 34,038
matches 2019-01..2026-05 (ATP 17,686 / WTA 16,352) >= required N 32,212 -> powered at
planning sigma_d. (Nested-drop-2019 = 29,183 and validation-only = 4,935 are BOTH
underpowered; recorded.) F3 surface Elo implemented (dual global+surface rating, shrinkage
seed, unknown->global fallback, same-day batch; 6 tests) + immutable registration
(K_surface in {16,24,32}, nested eval, decision rule frozen: PASS/CONTINUE/FAIL_FUTILITY/
FAIL_HARM at delta 0.0007, conf 0.975, alpha 0.025). M1 gate spec frozen
(specs/gates/probability-m1.yaml) — adequacy AND-gate, must NOT pass merely because F3
beats F2; numeric bands ⟨PENDING FOUNDER⟩ (returned for review, never agent-derived).
Calibration policy frozen (one-param temperature scaling, fold-safe, finalization only, no
alpha). June-surface source policy PREPARED / EXECUTION REFUSED (unordered-pair projection
proofs). Identity-correction ledger frozen (append-only, 0 auto-corrections — agent never
guesses; 54 ambiguities documented unresolved, affect only June M2, not pre-June). Alpha
ledger: F0/F1/F2 zero; F3-vs-F2 0.025; June M2 0.025; budget exhausted; F4+ none. make
verify green (283 files). No June outcome; no odds in F2/F3; NO F3-vs-F2 confirmatory
result computed or inspected.

## Stage 2B F3 confirmatory + M1: F3 FAILS, F2 selected, M1 CONTINUE (2026-07-18)

Ran the registered nested chronological F3-vs-F2 confirmatory trial (34,038 paired preds,
0 refusals; UTC-day block bootstrap via l8_evidence.paired_inference, seed 20260718).
Result: F2 0.62393 vs F3 0.63345; mean_d -0.00952; 97.5% CI [-0.01199,-0.00708] entirely
negative -> **FAIL_HARM** (surface Elo materially WORSE; ATP -0.0066, WTA -0.0127). Per
registered rule F3 NOT promoted; F2 global Elo retained as selected family. M1 scorecard on
calibrated F2 (per-fold temperature scaling): slope 0.83->1.005, log_loss 0.622<ln2, Brier
0.217, coverage 100%, temporal val<=oof, reliability<=0.017, cold-start fine, ATP/WTA pass;
**one band CONTINUE** (overall calibration-in-the-large +0.0233 vs +-0.02; one-param
temperature has no intercept, method contest forbidden) -> **M1 = CONTINUE** (Gate 1 not
closed). Alpha: F3-vs-F2 0.025 SPENT; June M2 0.025 reserved; F4+ none. June sealed; no odds
in F2/F3; no ROI/CLV/selection. Evidence docs/evidence/stage2b-f3-confirmatory/.

## Stage 2C governance + preparation: affine remediation, M2 gate, June intersection (2026-07-18)

Governance/preparation slice — NO June opened, NO data purchased, NO SPEC-032 fit, NO M2
computed. §1 F3 CLOSED FAIL_HARM permanently (specs/programme/f3-closure-record-v1.yaml; no
further surface-family trial authorised; alpha ledger finalised — June-M2 0.025 the sole
remaining allocation). §2 F2 frozen as SELECTED model (selected-model-record-v1.yaml). §3
registered AFFINE_LOGIT_CALIBRATION_V2 (calibration-policy-v2: z_cal = intercept + z/temperature,
temperature>0; ONE intercept + ONE temperature; ATP/WTA separate params — permitted because
frozen F2 policy already runs the tours as independent models; supersedes temperature-only v1,
which is retained as a diagnostic vintage). §3/§4 nested fold-safe affine remediation scorecard
(REMEDIATION/DEVELOPMENT evidence; does NOT close M1): overall calibration-in-the-large
+0.02328 -> **+0.00406** (in ±0.02 band), slope 1.0028, log_loss 0.62217<ln2, all 15 bands met
on pre-June data; final pre-June params ATP intercept 0.025399/T 1.218638, WTA 0.029204/1.150681;
digest sha256:6001657753… (docs/evidence/stage2c-affine-remediation/). §5 M1 remediation
amendment PROPOSAL (returned for approval; preserves every band; June = external transfer check).
§6 May-2026 ADVANCED procurement PROPOSAL (returned; no purchase; 10 items; outcome-blind month).
§7 market-development block protocol (prepared). §8 SPEC-032 combination REGISTERED not fitted
(spec032-combination-registration-v1.yaml + 8 binding tests, no fit). §9 M2 gate frozen
(specs/gates/probability-m2.yaml: market-only vs pre-fitted combined; d=ll_market-ll_combined;
δ0.0007, α0.025, conf0.975, UTC-day clustered; PASS/CONTINUE/FAIL_HARM/FAIL_FUTILITY). §10
prospective June M2 intersection **1,027 markets / 30 UTC-day clusters** (F0-committed ∧ F2-valid;
underpowered by design; ATP/WTA split reported as a gap, not fabricated; digest sha256:9f747bfa…).
§11 staged June opening runbook (Stage A M1 transfer -> if PASS Stage B M2; not authorised).
Identity ledger frozen; F3 closed; June-surface extractor still refused. make verify: 1853
unit+property tests pass. June sealed; no odds; no ROI/CLV/P&L/selection.

## Stage 2D governance: calibration frozen, M1 amendment approved, June M1 manifest, M2 alpha review, May purchase authorised (2026-07-18)

Founder ACCEPTED Stage 2C; Stage 2D executes the doable governance and prepares the rest.
NO June opened, NO May data present yet (agent never purchases — ADR 0015; founder purchases
personally). §1 separate ATP/WTA affine calibration params APPROVED + FROZEN in
calibration-policy-v2 (ATP intercept 0.025399/T 1.218638; WTA 0.029204/1.150681; scorecard
digest 6001657753…; no player/surface/band/tournament/other-method additions). §2 M1
remediation amendment APPROVED + FROZEN (probability-m1.yaml remediation_amendment_v1): all
bands unchanged; min_supported_predictions=500 (ATP/WTA/cohorts/reliability/overall);
cal-in-large PASS [-0.02,0.02] / CONTINUE (±0.02,±0.05] or unsupported / FAIL_HARM |cil|>0.05
AND cluster-aware evidence not noise; ±0.05 is a harm boundary only, not a widened PASS band;
unsupported June submetrics -> CONTINUE. §3 prospective June M1 transfer manifest (outcome-blind;
tour from governed identity-namespace provenance, mixed->typed refusal): 2,876 -> 1,213
calibrated-F2-valid (ATP 592, WTA 621 — both ≥500 supported; 5 MIXED_TOUR refusals reconcile
1,218 both-mapped = 1,213 + 5), 30 calendar-day clusters; digest d192b4e3…
(docs/evidence/stage2d-june-m1-transfer/). §4 May-2026 ADVANCED purchase AUTHORISED (£49 cap,
one month, MATCH_ODDS singles; agent does not purchase — founder executes, then provides files;
docs/procurement/advanced-may-2026-purchase-authorization.md). §8 M2 alpha-preservation review:
Option A one-shot (zero cost, ~CONTINUE, exhausts budget) vs Option B anytime-valid sequential
e-process (SPEC-096 unimplemented/planned; material engineering + years of monthly blocks for
δ=0.0007) — returned for founder selection; one-shot gate untouched. §10 wording: F3 closure
"paired races" -> "paired matches/decision units" (no number/verdict/digest change). §5/§6/§7
(May ingest, F0/F2 dev block, SPEC-032 fit) BLOCKED pending founder-provided May data. June sealed;
no odds; no ROI/CLV/P&L/EV/selection. make verify: gate/governance tests + spec coverage green.

## Stage 2E: June re-sequenced (M1 transfer -> SPEC-032 dev -> future M2); May purchase WITHDRAWN (2026-07-18)

Founder rejected the May purchase on budget/sequencing; NO further historical-data purchase.
Programme AMENDED (outcome-blind, before any June result): June is NO LONGER the M2 confirmation
block. New stages (june-evidence-plan-amendment-v1, digest 94f37c2a…): STAGE A = open June ONCE
as GATE-1 for the M1 external transfer of the frozen affine-calibrated F2 (burns the lockbox);
STAGE B = only if M1 PASS, June becomes the SPEC-032 combination DEVELOPMENT block (nested OOF
diagnostic + final pooled alpha,beta; no confirmatory alpha); STAGE C = FUTURE unseen matches
become the M2 confirmation stream (0.025 preserved). Continuation rule: M1 PASS->Stage B;
FAIL_HARM/substantive FAIL->stop; CONTINUE-on-support->stop+founder decision. May procurement +
authorisation marked WITHDRAWN. Alpha ledger reclassified June-M2 -> future-prospective-M2. v2
seal spec authorises the Stage A opening (lockbox-june-2026-tennis-v2, digest f552c7bf…): adds
governed scope JUNE_M1_TRANSFER; one logged burning GATE-1 read; no M2/EV/ROI on June; no
param change after opening; seal never reused. Future-prospective M2 protocol drafted
(one-shot vs anytime-valid e-process; SPEC-096 unimplemented). NOTE: the actual Stage A opening
(seal-code change + irreversible GATE-1 burn + M1 scorecard) is the next discrete step — the
seal-invariant test correction is a Rule-2 separate change and the burn is irreversible, so it is
NOT bundled here. Governance green (spec coverage 44 IDs; gate/outcome tests pass). June still sealed.

## Stage 2E pre-burn (part 1): seal-scope, use-policy, reconciliation, M1 join-harness (2026-07-18)

Founder approved the REVERSIBLE pre-burn work; the GATE-1 read stays withheld until the complete
pre-burn checkpoint is returned AND the founder issues "BURN JUNE STAGE A". Delivered so far
(June still SEALED; no outcome read):
- §1 governed seal-scope correction: test-correction committed SEPARATELY (Rule 2), then impl —
  OutcomeAccessScope.JUNE_M1_TRANSFER (one digest-bound June opening); authorisation carries an
  additive seal_authorisation_digest (required for June, forbidden else); extractor permits a
  sealed/after-boundary June market ONLY under scope JUNE_M1_TRANSFER + exact v2 seal digest
  (f552c7bf…) + explicit authorised set. All other scopes/markets still refuse; unauthenticated
  path still refuses. 27 governed+quarantine tests; ruff+mypy clean.
- §2 june-outcome-artifact-use-policy-v1 (digest 84efd4a2…): one immutable hash-bound artifact,
  read once; permitted M1; conditional Stage-B SPEC-032 dev ONLY on M1 PASS reusing the artifact
  (never reopening raw lockbox); M2/EV/ROI/etc prohibited.
- §3 reconciliation 1,213 vs 1,218: the 5-market gap is cross-tour homonym mis-resolution
  (female name collides with a male ATP surname+initial: Black B./Britton D./Johnson S.),
  correctly refused REFUSED_TOUR_PROVENANCE:MIXED_TOUR; no outcome used, not a defect. Frozen
  M1-valid 1,213 (ATP 592, WTA 621; 30 day-clusters).
- §4 (core) l8_evidence/june_m1_harness.py: the outcome-blind scoring JOIN (winner selection-id
  -> designated competitor by ID not order; unknown/mismatched refuse; exclusions visible;
  deterministic scorecard with 500-support flags), proven with 9 synthetic tests. 1872 unit+
  property tests green.
REMAINING before the checkpoint is complete: build the real 1,213-market outcome-blind prediction
bundle (F2 prequential + selection-id↔identity from pre-off June streams); atomic one-time
extraction + restart-safety; full dry-run + make verify/mutation; then the §7 checkpoint return.
