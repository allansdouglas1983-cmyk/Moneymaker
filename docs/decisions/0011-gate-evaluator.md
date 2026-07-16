# 0011 — Deterministic gate evaluator (SPEC-093) + specs/gates/v1.yaml — DRAFT

**Status: design complete, implementation NOT started.** Designed 2026-07-16 from the §9/§10
source text; the retrospective audit (ADR 0010) pre-empted the implementation. The next
session implements this slice: freeze `specs/gates/v1.yaml` FIRST (pre-registration posture,
as ADR 0009 did for prices), then failing tests in their own commit, then the implementation.

## Context

SPEC-093 (`planned`, money): a deterministic evaluator bound to data/model hashes; an LLM
never decides a gate. Binding inputs: §10 pins the CLI (`gate evaluate --spec
specs/gates/v1.yaml --experiment <id> --data-manifest sha256:... --model-manifest sha256:...
--facts-registry docs/facts.yaml` — the `--facts-registry` flag is pinned in
`l8_evidence/gates/README.md`); §10.1 fixes the four outcomes; §10.2 defines nine gates
(−1A, 0A, 1, 2, −1B, 0B/3, 4, 5, 6); §13.5 makes stale facts fail the gate; §9.3 forbids
borrowed thresholds; §9.7 defines the pre-registration record; SPEC-091 requires multiplicity
accounting; §12.4 demands the insufficient-evidence-never-PASS property. CI's
`mutants-critical` already enforces `--require-kill-non-equivalent` on this directory the
moment code lands.

## Decisions

1. **Structure/number split.** `specs/gates/v1.yaml` holds decision STRUCTURE only — a unit
   test asserts the parsed document contains **no numeric leaves at all** (§9.3). Every
   number comes from the experiment's pre-registration record; volatile economics come only
   from `docs/facts.yaml`.
2. **Gate ids** match `facts.yaml` `used_by` keys: `GATE--1A`, `GATE-0A`, `GATE-1`,
   `GATE-2`, `GATE--1B`, `GATE-3` (alias `GATE-0B`), `GATE-4`, `GATE-5`, `GATE-6`.
3. **Two gate kinds.** `checklist` (−1A, 0A, −1B, 3, 6) and `evidence` (1, 2, 4, 5; each may
   also carry precondition items, e.g. Gate 1's `lockbox_uncontaminated`). Item semantics:
   PASS requires every item attested true; an item attested **false** produces its declared
   `on_false` ∈ {FAIL_HARM, FAIL_FUTILITY, CONTINUE}; a **missing** attestation is CONTINUE
   (premature evaluation, not a demonstrated violation — matches §10.2's CONTINUE column).
   Items are transcribed from the §10.2 rows and §10.3–10.8 requirement bullets.
4. **Evidence decision `anytime_valid_bounds_v1`.** Inputs: anytime-valid lower/upper bounds
   at a declared `confidence_level`, sample size `n`, optional loss-budget state. Boundaries
   from pre-registration: `minimum_economic_effect`, `harm_threshold`, `alpha_budget`,
   `max_n`. **Multiplicity (SPEC-091/trial_count):** PASS additionally requires
   `(1 − confidence_level) × (number_of_prior_trials + 1) ≤ alpha_budget` — exact Decimal
   **multiplication only**, no division, so the check is exact.
5. **Precedence (safety-first, property-tested):** stale/misconfigured facts → FAIL_HARM;
   critical-false item → its declared flavour; loss-budget breach → FAIL_HARM;
   `upper < harm_threshold` → FAIL_HARM; PASS only when every precondition holds, the
   multiplicity check holds, and `lower > minimum_economic_effect`; `n ≥ max_n` →
   FAIL_FUTILITY; else CONTINUE. Harm dominates efficacy.
6. **Facts (§13.5).** Registry-wide: ANY populated fact past `recheck_by` — or populated with
   no `recheck_by` — → FAIL_HARM with the fact id in the reasons. A fact **required by the
   gate under evaluation** (its `used_by` names the gate id or alias) that is unpopulated →
   CONTINUE (cannot honestly evaluate; not a demonstrated violation). `as_of` is an explicit
   parameter of the pure core (determinism); the CLI resolves today-UTC once and echoes it.
7. **GATE--1B `payback_v1` computed item** (§10.4, exact Decimal):
   `annual = N_eligible × r_select × r_fill × S̄ × ROI_lower − C_recurring`; `annual ≤ 0` →
   never amortises → item false; else `T = C_fixed / annual ≤ max_payback_years`.
   `on_false: FAIL_FUTILITY`. Property: increasing `C_recurring` never shortens payback.
8. **Types.** `GateOutcome` is a 4-valued enum; `GateResult` frozen. **Both define
   `__bool__` raising `TypeError`** — "never a boolean" is enforced by construction, and a
   property test asserts `bool(result)` raises. All quantities are Decimal-from-string or
   int; no float anywhere.
9. **Binding.** `--data-manifest`/`--model-manifest` must match `^sha256:[0-9a-f]{64}$`
   (violation = evaluator error, never a verdict). The result embeds both manifests, sha256
   digests of the gate-spec bytes and the facts-registry bytes, the spec version, evaluator
   version (`gate-evaluator-v1`) and `as_of`. Output is canonical JSON (sorted keys);
   identical inputs → byte-identical output (property).
10. **CLI.** `gate evaluate` exactly per the README contract. `--experiment <id>` resolves
    `<root>/<id>.yaml` with `--experiment-root` defaulting to `ledger/experiments`
    (SPEC-091 later formalises the ledger; the record is a §9.7 superset with `gate:`,
    `evidence:` and `attestations:` blocks). Exit codes: PASS 0, CONTINUE 1, FAIL_HARM 2,
    FAIL_FUTILITY 3, evaluator error 4. Console script `gate = l8_evidence.gates.cli:main`
    added to `[project.scripts]`.
11. **Frozen.** Any change to `specs/gates/v1.yaml` is `gates-v2` plus a new
    pre-registration; a gate formula and the evidence evaluated by it never change together
    (§0 Rule 2).
12. **Module layout.** `outcomes.py` (enum + result), `spec.py` (loader + digest),
    `experiment.py` (record parsing), `facts.py` (evaluator-side freshness — deliberately
    self-contained in the money module and mutation-tested; `tools/check_facts_freshness.py`
    stays the registry lint; duplication risk accepted and documented), `evaluator.py`
    (pure `evaluate()`), `cli.py`.
13. **Properties** (manifest metamorphic set plus): constructed insufficient evidence never
    PASS; verdict always 4-valued and never truth-testable; any stale fact defeats even
    overwhelming efficacy evidence; determinism; harm dominance; trial-count
    downward-closure (if PASS at `t+k` trials then PASS at `t`); no-numerics-in-yaml.
14. **Activation.** After implementation + coverage, flip SPEC-093 `planned → active` per
    the standing progression plan (enforcement-increasing only), recording the rationale.

## Consequences

The gates directory becomes the second real `--require-kill-non-equivalent` mutation target
(design avoids redundant branches and singleton comparisons where an observable alternative
exists — the ADR 0010 lessons). SPEC-091's ledger later reads the same record schema. The
evaluator is the tool named in `docs/CI-AND-TRUST.md` §5's audit-subagent toolbox.
