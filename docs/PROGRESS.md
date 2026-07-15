# Build progress & session handover

**Living state for the build.** SPECIFICATION.md §16 requires durable state to live in files,
not the conversation. This is that file. Update it at the end of every slice.

**Branch:** `claude/project-files-followup-dif8al` · **Last updated:** 2026-07-15

---

## Status at a glance

| | |
|---|---|
| Active SPEC-IDs covered | **7 of 23** (SPEC-001–004, 010–012) |
| Tests | **73 passing** (unit + property + failure-injection + replay-regression) |
| Static checks | `mypy --strict` clean (46 files), `ruff` + `ruff --select ARG` clean |
| Commits on branch | 15 |
| Phase | 1 (walking vertical slice), offline only |
| `make verify` overall | **RED** by design — 16 active IDs not yet implemented |

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

---

## Coverage map

**Covered (7):** SPEC-001, 002, 003, 004 (L0) · SPEC-010, 011, 012 (L1).

**Remaining active (16):**
| IDs | Component | Notes |
|---|---|---|
| SPEC-020–024 | `l3_features` (evidence) | knowledge-time, BSP-leakage guard, actual-off exclusion, backfill provenance, feature hash |
| SPEC-050–054 | `l5_decision` (money) | EV at odds_exec, three-price types, taker-v1, tick index, one-runner |
| SPEC-080, 082 | `l7_settle` (money) | market-level settlement, settlement edge cases |
| SPEC-100–103 | governance (evidence/money) | scraping quarantine, licensed data, no-delayed-key, budget separation |

`planned` IDs (L4 pricing, L4b fill, L5b risk, L6 broker, L8 evidence, SPEC-104) are not yet
CI-enforced; activating a phase is a human-controlled change.

---

## Next slice (recommended)

**L3 features — SPEC-020–024** (all `evidence`), the next layer in the §11 vertical slice.
Implement the knowledge-time / leakage **framework** guards:
- SPEC-020 six knowledge-time stamps; reject a feature whose first-usable-time is not provably
  before market off (build-time error, not warning).
- SPEC-021 BSP-leakage guard: static import-graph check **and** a runtime assertion.
- SPEC-022 actual-off time unavailable in live mode; post-hoc mode explicit.
- SPEC-023 backfill provenance (live-captured vs backfilled; true publication time).
- SPEC-024 feature-set hash reproducibility.

**Dependency note:** the *actual* `p_market_info` computation needs
`specs/prices/info-price-v1.yaml`, which is a **frozen Phase-0 human decision** deliberately not
fabricated (§4 — setting p_market_info is a model choice, not an implementation choice). The
SPEC-020–024 guards do not need it and can land first. Path-scoped rule `.claude/rules/evidence.md`
loads automatically when you touch `l3_features/`.

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
  land with the first money module.
- **`specs/prices/*-v1.yaml` and `specs/gates/v1.yaml` are intentionally unwritten** — frozen
  human pre-registration decisions (§4, §10), not agent-fabricated.
- **No PR opened yet** (not requested).
