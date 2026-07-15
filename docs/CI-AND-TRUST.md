# CI, Trust Boundary, and Anti-Degradation

This file specifies the only controls that actually prevent bad code reaching
production. Everything else in this repository is convenience.

---

## 1. What is not a control

**Project hooks are not a security boundary.** `.claude/settings.json` lives in the
same writable trust domain as the code, the tests, the fixtures, and any local token.
An agent that can edit the repo can edit the guard, the validator, and the evidence.

There is also a logical defect in the pattern "PreToolUse hook checks for a passing-test
artefact before allowing a protected edit": **tests that pass before an edit prove the
old code, not the edited code.** The artefact cannot attest the change it is gating.

A local HMAC approval token does not repair this. `Read()` deny rules do not stop a Bash
command from reading the file. A regex blocking `placeOrders.*live` is bypassable via
Python, an import, an env var, an alias, or a newly written script. A local timestamp
comparison is vulnerable to clock changes and attests nothing about the working tree.

**Hooks remain useful for workflow convenience and fast feedback. They must never be
described as the control preventing unsafe live code.**

## 2. What is a control

```
Unprivileged dev container
  (no Betfair credentials, no live network access)
        │
        ▼
Feature branch → Pull Request
        │
        ▼
Protected CI on a remote runner the agent cannot edit
  tests + replay + property + mutation + spec-coverage + import-graph
        │
        ▼
Attestation bound to exact commit / tree hash
        │
        ▼
Human approval in a protected deployment environment
        │
        ▼
Immutable signed live image
```

**Non-negotiable settings:**
- Protected `main`: required status checks, required PR review, required signed commits
- **"Do not allow bypassing the above settings" ENABLED (include administrators)**
- Bypass list **verified empty** — rulesets can contain bypass actors. Verify, don't assume.
- The agent's credentials **cannot push to `main` and cannot deploy**
- **PR CI carries no production secrets.** Deploy credentials exist only post-merge, in a
  protected environment, behind human approval.
- Live environment accepts only signed images built from a reviewed commit

## 2a. Defeating self-attestation

**The circular trust risk:** if the agent can modify `.github/workflows/` *and* the code
under test, the modified workflow can certify its own change. Required status checks do not
help when the check is authored inside the PR.

**Human-owned via CODEOWNERS:**
```
/.github/workflows/**   /docs/SPECIFICATION.md   /docs/spec-manifest.yaml
/docs/facts.yaml        /specs/**                /tests/**
/l5_decision/**         /l5b_risk/**             /l6_broker/**
/l7_settle/**           /l8_evidence/gates/**    /CODEOWNERS
```

**Plus one of** (preference order):
1. Organisation-level **required workflow**
2. **Reusable verification workflow in a separate, more tightly protected repo**, pinned by
   immutable commit SHA
3. Protected CI app whose verification logic lives **outside the PR's writable tree**

CODEOWNERS reviews use the **base** branch version — helpful — but CODEOWNERS itself and the
protection settings still need controlled ownership.

The one genuine on-machine boundary is **managed settings** at a root-owned path
(`/etc/claude-code/managed-settings.json`), with the agent running as an unprivileged
user. Managed settings take final precedence and survive `disableAllHooks`. But they
govern *permissions*, not *correctness* — they cannot stop a stub.

---

## 3. CI workflow

```yaml
name: verify
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  id-token: write
  attestations: write

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync

      # Spec coverage — ACTIVE ids only. `planned` must not block Phase 1.
      - name: Spec traceability (active + verified)
        run: uv run python tools/check_spec_coverage.py --manifest docs/spec-manifest.yaml --enforce-states active,verified

      # Money-critical ACTIVE IDs must declare causal inputs + have property tests
      - name: Causal declarations + property coverage for active money IDs
        run: uv run python tools/check_spec_coverage.py --manifest docs/spec-manifest.yaml --enforce-states active,verified --require-causal-declarations --require-properties-for money

      # An active ID must never silently lose a verification
      - name: No verification regressions
        run: uv run python tools/check_spec_coverage.py --manifest docs/spec-manifest.yaml --detect-verification-loss --base-ref origin/main

      # Facts registry must not be stale
      - name: Facts freshness
        run: uv run python tools/check_facts_freshness.py --registry docs/facts.yaml

      - name: Unit + integration
        run: uv run pytest tests/unit tests/integration -q

      - name: Property-based (Hypothesis)
        run: uv run pytest tests/properties -q

      - name: Stateful / model-based
        run: uv run pytest tests/stateful -q

      - name: Failure injection
        run: uv run pytest tests/failure_injection -q

      - name: Replay regression (bit-exact)
        run: uv run pytest tests/replay_regression -q

      # Static anti-stub
      - name: Unused arguments
        run: uv run ruff check --select ARG .
      - name: Pylint unused-argument on money modules
        run: uv run pylint --disable=all --enable=W0613 l4b_fill l5_decision l5b_risk l6_broker l7_settle l8_evidence
      - name: Ban escape hatches in money modules
        run: |
          ! grep -rnE '(NotImplementedError|TODO|FIXME|pass\s+#|raise\s+NotImplemented)' \
            l4b_fill l5_decision l5b_risk l6_broker l7_settle l8_evidence \
            --include='*.py'

      # Licensing quarantine
      - name: Scraping import-graph quarantine
        run: uv run python tools/check_import_quarantine.py --forbid research.scraping --from l5_decision l5b_risk l6_broker

      # BSP-leakage quarantine — reconciled BSP joins at grading only (SPEC-021, static half)
      - name: BSP import-graph quarantine
        run: uv run python tools/check_import_quarantine.py --forbid l8_evidence.reconciled_bsp --from l3_features

      - name: Typecheck
        run: uv run mypy --strict .

      - name: Traceability matrix artifact
        run: uv run python tools/emit_traceability.py > traceability.md
      - uses: actions/upload-artifact@v4
        with: { name: traceability, path: traceability.md }

  mutants-critical:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - name: Mutation — gates (100% of NON-EQUIVALENT mutants)
        run: uv run python tools/run_mutation.py --target l8_evidence/gates --require-kill-non-equivalent --survivors-must-be-classified
      - name: Mutation — risk & settlement (report survivors)
        run: uv run python tools/run_mutation.py --target l5b_risk l7_settle --report

  attest:
    needs: [verify, mutants-critical]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions: { id-token: write, attestations: write, contents: read }
    steps:
      - uses: actions/checkout@v4
      - name: Build artefact
        run: make build
      - uses: actions/attest-build-provenance@v1
        with:
          subject-path: 'dist/*'
```

**Required status checks on `main`:** `verify`, `mutants-critical`.

---

## 4. Detecting plausible stubs

The specific fear: code that exists, looks right, has a passing test, and does not do
the specified thing.

| Defect | Caught by | Limitation |
|---|---|---|
| Parameter declared, never used | ruff `ARG001`, pylint `W0613`, Vulture | **Trivially evaded** by `_ = param`, a log line, a dead branch, or a `_`-prefix |
| Parameter read, no effect on output | — | **Not soundly decidable by any mainstream Python linter.** Semgrep taint mode is intra-procedural, tracks flow not numerical dependence, cannot distinguish `f*1` from `f*0` |
| Function returns a constant | **Property-based test only** | Only if you write the property |
| Gate always returns pass | Property test on constructed insufficient-evidence inputs | — |
| Weak tests hiding a stub | Mutation testing | Proves test strength, not code correctness |

**Property-based tests are the primary defence — but not the naive form.**

> ❌ **`assert f(a) != f(b)` for all distinct inputs is INVALID here.** Exhausted budget must
> always REJECT regardless of edge. A suspended market gives a constant decision regardless
> of price. A duplicate command must add no exposure though fields differ. Guard branches
> legitimately dominate; a rule forbidding that forces bad code.

**Instead — test the declared causal relations from the manifest:**

```python
# Declared relevant input affects behaviour IN THE SPECIFIED REGION
@given(edge=st.floats(0.01, 0.5))
def test_stake_monotonic_in_edge_when_guards_pass(edge):
    ctx = healthy_context()                  # all guards passing
    assert stake(ctx, edge + 0.01) >= stake(ctx, edge)

# Guard dominates — the correct constant-output case
@given(edge=st.floats(0, 1))
def test_exhausted_budget_always_rejects(edge):
    assert decide(exhausted_budget_context(), edge) == REJECT

# Declared IRRELEVANT input must NOT affect the decision
@given(meta=st.text())
def test_metadata_does_not_change_decision(meta):
    assert decide(ctx_with_meta(meta)) == decide(ctx_with_meta(""))

# Boundary
def test_zero_edge_zero_action():
    assert stake(healthy_context(), 0.0) == 0
```

A Kelly sizer ignoring `fraction` dies on the monotonicity property. A fill model returning
a constant dies on its declared relevant-input relations.

---

## 5. Agent tooling

**"Read-only with Bash" is not read-only.** Bash writes files, alters git state, reads
blocked paths, invokes network clients, executes arbitrary programs.

Audit subagents get **dedicated deterministic tools only**, no general Bash:

```
audit-data --manifest <id>
audit-leakage --experiment <id>
run-evaluation --spec <signed-spec>
reconcile-session --session-id <id>
gate evaluate --spec <spec> --experiment <id> --data-manifest <sha> --model-manifest <sha>
```

The LLM interprets structured output. It does not construct shell pipelines.

**Gate decisions are deterministic.** An agent may explain a gate result. It may never
decide one.

**MCP:** no connection to Betfair, account state, live order state, production secrets,
or writable production databases. Anthropic does not security-audit MCP servers. Agents
read a delayed, sanitised, read-only analytics snapshot, or generated reports. An
allowlisted analytics CLI is easier to audit than an MCP server.

---

## 6. Where hooks legitimately help

- PostToolUse running `ruff`/`pytest` on save — instant local signal
- PreCompact writing session state to disk — survives lossy compaction
- SessionStart injecting the manifest reminder
- PreToolUse blocking edits to `docs/spec-manifest.yaml` or `.github/workflows/` as a
  **speed-bump that surfaces intent** — not as a control

None of these are the boundary. The boundary is CI on a runner the agent cannot edit,
plus credentials it does not hold.

---

## 7. Human verification checklist

- [ ] CI green **on the PR head commit** (not a stale run)
- [ ] Traceability matrix: every `money` SPEC-ID has a passing **property-based** test
- [ ] `git diff` on test files reviewed — no test weakened or deleted
- [ ] Mutation: 100% kill on gates; every survivor in risk/settlement investigated
- [ ] Grep diff for `NotImplementedError`, `TODO`, `pass  #`, bare `return None`,
      suspicious literal returns in money modules
- [ ] **Manual spot-check:** change a parameter the spec says the output depends on.
      Does the output actually change?
- [ ] Attestation verifies against the merged commit SHA
- [ ] No import path from `research/scraping/` to anything that can place a bet
- [ ] Claude Code version matches the pinned approved container

---

## 8. Claude Code version policy

Do not embed a static version floor as an architectural constant. Instead:
- Pin an approved container version for reproducibility
- Monitor releases for security-relevant changes
- Document an upgrade SLA
- Use `requiredMinimumVersion` in managed settings
- Run regression tests before each upgrade
