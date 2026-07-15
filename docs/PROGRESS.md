# Build progress & session handover

**Living state for the build.** SPECIFICATION.md §16 requires durable state to live in files,
not the conversation. This is that file. Update it at the end of every slice.

**Branch:** `claude/project-files-followup-dif8al` · **Last updated:** 2026-07-15

---

## Status at a glance

| | |
|---|---|
| Active SPEC-IDs covered | **21 of 23** (SPEC-001–004, 010–012, 020–024, 050–054, 100–103) |
| Tests | **231 passing** (unit + property + failure-injection + replay-regression) |
| Static checks | `mypy --strict` clean (91 files), `ruff` + `ruff --select ARG` clean, `pylint W0613` 10/10 |
| Commits on branch | 39 |
| Phase | 1 (walking vertical slice), offline only |
| `make verify` overall | **RED** by design — 2 active IDs (SPEC-080/082, L7) not yet implemented |

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

---

## Coverage map

**Covered (21):** SPEC-001–004 (L0) · SPEC-010–012 (L1) · SPEC-020–024 (L3) · SPEC-050–054 (L5) ·
SPEC-100–103 (governance).

**Remaining active (2):**
| IDs | Component | Notes |
|---|---|---|
| SPEC-080, 082 | `l7_settle` (money) | market-level settlement, settlement edge cases |

`planned` IDs (L4 pricing, L4b fill, L5b risk, L6 broker, L8 evidence, SPEC-104) are not yet
CI-enforced; activating a phase is a human-controlled change.

---

## Next slice (recommended) — the LAST active cluster

**L7 settlement — SPEC-080, 082** (`money`), the only remaining active IDs. Path-scoped rule
`.claude/rules/moneycritical.md` loads when you touch `l7_settle/`.
- **SPEC-080 market-level settlement.** `market_settlement` with `gross_pnl_by_selection_scenario`,
  `actual_net_market_pnl`, `commission_rate_effective`, `actual_commission`, `transaction_charges`,
  `final_net_pnl`, `statement_reference`, `settlement_version`, `resettlement_flag`. Commission is on
  the **net market result** — a per-order `commission_est` MUST NOT exist as an authoritative field.
- **SPEC-082 settlement edge cases.** Partial matches; multiple orders on one runner; multiple
  runners; dead heats; reduction factors (Betfair semantics, not bookmaker "Rule 4"); voided/abandoned
  races; resettlements; rounding to currency minor units; duplicate acks; unknown status after timeout.
- Both need property tests. Exact `Decimal`/integer minor units, never float.

**The mutation harness lands with this slice.** ADR 0001's `run_mutation.py` (and `make mutants` /
the CI `mutants-critical` job) targets `l8_evidence/gates`, `l5b_risk`, `l7_settle` — L7 is its first
real target. Build `tools/run_mutation.py` here (cosmic-ray wrapper: 100% of non-equivalent mutants
killed on gates; survivors classified) and add `cosmic-ray` to the dev deps. `l8_evidence/gates` and
`l5b_risk` are still `planned`, so mutation runs against `l7_settle` for now.

**After L7 all 23 active IDs are covered** — `make verify` should then go green (subject to the CI
still being red only where planned phases haven't been activated). At that point consider opening a PR
(not yet requested) and the human/platform actions in *Operational notes*.

**Still unwritten (deliberately):** `specs/prices/*-v1.yaml` and `specs/gates/v1.yaml` are frozen human
pre-registration decisions (§4, §10) — L7 does not need them.

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
