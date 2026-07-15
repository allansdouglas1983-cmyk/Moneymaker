# 0006 — Governance guarantees (SPEC-100–103)

- **Status:** Accepted
- **Date:** 2026-07-15
- **Scope:** `governance/`, `docs/licensed-sources.yaml`, `tests/{unit,properties}/governance/`,
  plus CI/CODEOWNERS wiring. SPEC-100/101 `evidence`, SPEC-102/103 `money`.
- **Spec:** SPECIFICATION.md §11, §12.2, §13.1–§13.2; spec-manifest SPEC-100–103.

## Context

These four active IDs are cross-cutting governance guarantees (`component: governance`) that do
not belong to a single L-layer. SPEC-100's mechanism already exists in `tools/`; SPEC-101/102/103
need real constructs. They are Phase-0/foundational and must be covered now.

## Decisions

1. **A `governance/` package** houses the cross-cutting guarantees (SPEC-101/102/103). This dir
   is not in SPECIFICATION.md §14's illustrative tree, but it matches the manifest `component`
   and keeps these concerns cohesive rather than forcing them into unrelated (and mostly
   `planned`) L-layers.

2. **`governance/` joins the money-module CI enforcement.** SPEC-102/103 are `money`, so
   `governance` is added to the `pylint W0613` target, the escape-hatch grep, and the `Makefile`
   `MONEY` list. Money-grade anti-stub lint on the whole package is stricter, never weaker.

3. **SPEC-100 (scraping quarantine) is verified, not re-implemented.** The static import-graph
   check (`tools/check_import_quarantine.py`, wired into CI + Makefile) is the mechanism. The
   slice adds a `@pytest.mark.spec("SPEC-100")` test that (a) asserts the real repo has no
   `research.scraping` path reachable from `l5_decision`/`l5b_risk`/`l6_broker`, and (b) proves
   the check is non-vacuous by catching a planted violation.

4. **SPEC-101 (licensed data) = a registry + a deterministic gate check.** `docs/licensed-sources.yaml`
   (§13.2 schema) is the registry; every source is `candidate` with unverified rights until a
   human reviews it (rights are a legal decision, never agent-fabricated). `assert_operational_sources_licensed`
   fails if any source flagged `operational: true` is not `permitted` with the required rights.
   With no operational source yet (Phase 1 is offline), the check passes — and it will fail the
   moment a source is marked operational without verified rights. The registry is added to
   CODEOWNERS as a human-owned governance file (like `docs/facts.yaml`).

5. **SPEC-102 (no Delayed-key real money) is enforced by the type system.** `LiveAppKey` and
   `DelayedAppKey` are distinct frozen types. `RealMoneyPlacementAuthorization` can only be
   constructed from a `LiveAppKey` (its field is typed `LiveAppKey`, so `mypy --strict` rejects
   passing a `DelayedAppKey`), and the single factory `authorize_real_money_placement` raises
   `DelayedKeyRealMoneyError` for a delayed key. Real-money placement therefore requires an
   authorization a delayed key cannot produce — impossible by construction, not by policy. (Python
   cannot make a constructor truly private; the type distinction + single factory + property test
   are the practical realisation.)

6. **SPEC-103 (budget separation) is enforced by absence.** `SeparatedBudgets` holds three
   independent `BudgetAccount`s (research-infrastructure, betting-bankroll, max-experiment-loss),
   each an exact integer minor-unit balance (never float). There is **no** transfer/credit API —
   only `debit(kind, amount)`, which returns a new immutable `SeparatedBudgets` with only the named
   account reduced. One budget cannot fund another because no code path moves value between them;
   the property test pins that a debit on one leaves the other two byte-identical.

## Consequences

- SPEC-100/101 (evidence) get marked tests; SPEC-102/103 (money) get spec-marked property tests
  under `tests/properties/governance/`.
- `governance/` is now money-lint-enforced; `run_mutation.py` remains for the L7 slice (governance
  is not a `mutants-critical` target in CI-AND-TRUST §3).
- The licensed-source *rights* stay unverified (`candidate`) — a human/legal action, tracked by
  `recheck_by` and the CODEOWNERS review requirement.
