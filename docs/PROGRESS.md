# Build progress & session handover

**Living state for the build.** SPECIFICATION.md §16 requires durable state to live in files,
not the conversation. This is that file. Update it at the end of every slice.

**Branch:** `claude/project-files-followup-dif8al` · **Last updated:** 2026-07-15

---

## Status at a glance

| | |
|---|---|
| Active SPEC-IDs covered | **17 of 23** (SPEC-001–004, 010–012, 020–024, 050–054) |
| Tests | **210 passing** (unit + property + failure-injection + replay-regression) |
| Static checks | `mypy --strict` clean (78 files), `ruff` + `ruff --select ARG` clean, `pylint W0613` 10/10 |
| Commits on branch | 32 |
| Phase | 1 (walking vertical slice), offline only |
| `make verify` overall | **RED** by design — 6 active IDs not yet implemented |

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

---

## Coverage map

**Covered (17):** SPEC-001–004 (L0) · SPEC-010–012 (L1) · SPEC-020–024 (L3) · SPEC-050–054 (L5).

**Remaining active (6):**
| IDs | Component | Notes |
|---|---|---|
| SPEC-080, 082 | `l7_settle` (money) | market-level settlement, settlement edge cases |
| SPEC-100–103 | governance (evidence/money) | scraping quarantine, licensed data, no-delayed-key, budget separation |

`planned` IDs (L4 pricing, L4b fill, L5b risk, L6 broker, L8 evidence, SPEC-104) are not yet
CI-enforced; activating a phase is a human-controlled change.

---

## Next slice (recommended)

Two active clusters remain. Recommended: **governance SPEC-100–103** (Phase-0, foundational, no
new heavy machinery), then **L7 settlement SPEC-080/082**.

**Governance — SPEC-100–103.** These are the "no live / lawful / budget-separated" guarantees.
- SPEC-100 (`evidence`) scraping quarantine — the import-graph **mechanism already exists**
  (`tools/check_import_quarantine.py`, CI-wired). It needs a `@pytest.mark.spec("SPEC-100")` test
  (assert `find_violations(...)==[]` from a test, plus a vacuity/would-catch check) to count as
  covered. Cheapest win.
- SPEC-101 (`evidence`) licensed data — Gate -1 fails if any operational source lacks rights.
- SPEC-102 (`money`) no Delayed-key real money — real-money placement on the Delayed App Key must
  be **impossible by construction**, not policy. Needs a property test.
- SPEC-103 (`money`) budget separation — research / bankroll / max-experiment-loss are three
  separate budgets; code must not let one fund another. Needs a property test.

**L7 settlement — SPEC-080, 082** (`money`). Market-level settlement (`market_settlement` with
net-market P&L, effective commission, transaction charges; **per-order `commission_est` must not
exist as authoritative**) and settlement edge cases (partial matches, multiple runners, dead
heats, reduction factors, voids/abandonments, resettlements, rounding to minor units, duplicate
acks, unknown-after-timeout). Both need property tests. Commission is on the **net market result**.

**Notes carried forward:**
- **Mutation harness still deferred.** ADR 0001's `run_mutation.py`/`make mutants` targets
  `l8_evidence/gates`, `l5b_risk`, `l7_settle` — none built yet. It should land **with the L7
  settlement slice** (its first real target), not before. L5 was NOT a mutation target.
- `specs/prices/info-price-v1.yaml` and `specs/gates/v1.yaml` remain unwritten frozen human
  decisions (§4, §10) — none of the remaining active IDs need them.

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

---

## Decisions (ADRs)

| ADR | Title |
|---|---|
| `docs/decisions/0001-verification-tooling.md` | marker-based SPEC coverage; run_mutation deferred; checker/pytest division of labour |
| `docs/decisions/0002-l0-raw-truth-layer.md` | dual clock; append-only framing; two-event API command; persist-before-send; dir fsync |
| `docs/decisions/0003-l1-reducer.md` | Decimal-not-float; canonical hash; reducer registry/versioning; MCM-v1 scope |
| `docs/decisions/0004-l3-knowledge-time.md` | knowledge-time stamps; LeakageError-not-ValueError; two-mechanism BSP guard; live actual-off exclusion; no-float feature hash |
| `docs/decisions/0005-l5-decision.md` | canonical tick ladder; three distinct price types; exact-Decimal EV; conservative-lower-bound typing; one-runner selection+ledger; taker-v1 pinned order; mutation harness deferred to L7 |

---

## Operational notes / open items (need a human or the platform)

- **Commit signing is impossible in this environment.** `commit.gpgsign=true`, `gpg.format=ssh`,
  but `/home/claude/.ssh/commit_signing_key.pub` is a 0-byte placeholder and there is no
  `allowedSignersFile`; even `-S` yields "No signature". All commits are therefore *Unverified*
  on GitHub (committer identity is correct). CIANDTRUST §2 requires signed commits on protected
  `main` — real signing infrastructure is a **platform action** before any merge.
- **Branch protection not verifiable from here** — required checks (`verify`, `mutants-critical`),
  required review, "do not allow bypassing (include administrators)", bypass list verified empty
  (SPECIFICATION §12.2). Human/platform action.
- **CODEOWNERS owner is a default** (`@allansdouglas1983-cmyk`) — replace with a dedicated
  reviewer/team before any live phase.
- **CI is red until the active surface is covered** — expected. `run_mutation.py`/`make mutants`
  land with the **L7 settlement** slice — the first module the CI `mutants-critical` job actually
  targets (`l8_evidence/gates`, `l5b_risk`, `l7_settle`). L5 decision, though the first money
  module, is not a mutation target, so the harness was correctly not stood up for it (ADR 0005).
- **`specs/prices/*-v1.yaml` and `specs/gates/v1.yaml` are intentionally unwritten** — frozen
  human pre-registration decisions (§4, §10), not agent-fabricated.
- **No PR opened yet** (not requested).
