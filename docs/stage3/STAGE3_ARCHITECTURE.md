# STAGE 3 ARCHITECTURE — plug-in information layers

Status: ACTIVE (founder directive STAGE3-0001). Architecture only — **no implementation
code, no model families, no code changes** are authorised by this document.

## Purpose

Stage 2 concluded. The active sporting baseline for all future research is **Frozen
F2-v1** (global Elo; `specs/programme/f2-global-elo-registration-v1.yaml`,
`specs/programme/f2v1-closure-record-v1.yaml`). F3 surface Elo is FAIL_HARM; DP1 dynamic
Glicko-2 is STOP_DP1_HARM — both permanent programme history, both reproducible and
executable but retired from active development.

Stage 3's objective is **not** "build a better prediction model." It is **"discover
information that is genuinely independent of Frozen F2."** F2 represents exactly one thing:
the win/loss history of governed competitor identities in chronological order. A layer
earns its place only by carrying information F2 **structurally cannot** hold. The
architecture below exists to force that question to be answered *before* any code, and to
let independent information layers plug in and be judged on identical governance to
Stage 2 — never to make a model easier to pass.

## The five questions every candidate layer must answer (gate zero)

No layer is registered, and no implementation is authorised, until the hypothesis (see
`STAGE3_HYPOTHESIS_REGISTER.md`) answers, in writing and in advance:

1. **The exact new information introduced** — the specific signal, named and bounded.
2. **Why Frozen F2 cannot already represent it** — the structural argument that a global
   Elo over identity/outcome/chronology cannot encode this signal even in principle.
3. **Whether it is knowable at prediction time** — provably available strictly before the
   market off, under the knowledge-time registry (§Knowledge-time interface).
4. **Whether it is lawful** — permitted by the source-rights and field-use registries for
   the intended use (research vs any future publication/automation).
5. **Whether it can be prospectively validated** — a pre-registered, post-freeze
   measurement exists that could distinguish "adds independent information" from "noise."

A layer that cannot answer all five is not a Stage 3 candidate.

## Design invariants (inherited from Stage 2, non-negotiable)

- The **market choice set is the unit of analysis** (race/match), never the selection.
- **Time-respecting, out-of-fold** production of every fundamental fed downstream
  (SPEC-031); a contaminated row is refused at *consumption*, not only production.
- **Three prices stay distinct types**: `p_market_info` (model input), `odds_exec`
  (transactable now), `p_close` (diagnostic only) — SPEC-051. `p_close` never reaches a
  decision or a training target.
- **Frozen F2 is immutable.** Stage 3 layers compose *around* it; none may retune it.
- **An LLM never estimates a probability, prices, sizes, or decides a gate.** Every
  number is deterministic tested code.
- **June is development evidence forever.** Confirmation is only on post-freeze
  observations.

---

## Interfaces

Each interface is a **contract**, described here at the level of responsibilities,
inputs, outputs and prohibitions. Ports named `l4_pricing.stage_one.StageOneFamily`,
`l4_pricing.crossfit.cross_fit`, `l5_decision.ev.WinProbabilityLowerBound`,
`l3_features.feature_registry`, `l8_evidence.trial_ledger`, `l8_evidence.gates` already
exist and are the anchor points; Stage 3 adds *contracts*, not code, in this document.

### 1. Sporting baseline interface

**Responsibility.** Expose Frozen F2-v1 as the single, immutable reference fundamental
`p_baseline` for a choice set, produced through the existing model-independent
chronological cross-fit orchestrator (`cross_fit`, SPEC-031) — no special path.

- **Input:** the governed choice set (competitor identities, UTC-day chronology, active
  set), nothing else. The baseline sees no name, odds, surface, or post-event field.
- **Output:** `p_baseline` per selection, summing to 1 within the choice set, with
  provenance (`trained_through`, training-race-id digest, horizon) proving it is strictly
  out-of-fold for the priced set.
- **Prohibitions:** no retuning of K or any F2 policy; no alternative baseline; the
  baseline is *frozen*. A Stage 3 layer consumes `p_baseline` as a fixed input, never a
  parameter. The interface refuses to emit a baseline for a set it trained on.

### 2. Residual interface

**Responsibility.** This is the heart of Stage 3. A candidate layer does **not** predict
the winner from scratch; it proposes a **residual** — the information it claims to add
*beyond* `p_baseline`. The interface makes "independent of F2" a typed, testable object.

- **Input:** `p_baseline` (frozen), the candidate layer's own signal(s), and the
  knowledge-time attestation for each signal.
- **Output:** a residual contribution on the logit (or a governed monotone) scale, plus
  the **combined** fundamental `p_combined` (baseline ∘ residual). The residual carries:
  (a) the named information it encodes, (b) a machine-checkable claim that it is not a
  deterministic function of `p_baseline`'s inputs, and (c) its own out-of-fold provenance.
- **Independence obligation:** the interface requires an *orthogonality artefact* — a
  pre-registered measurement of how much of the residual is explained by `p_baseline`
  alone. A residual that is (statistically or structurally) reconstructable from F2's
  inputs is refused: it introduces no independent information by definition.
- **Prohibitions:** no residual may read the outcome of the priced set; no residual may
  use `p_close` or any reconciled closing benchmark; a residual that only helps when
  composed with the market (not with the baseline) is a *market* layer, not a residual,
  and belongs on interface 3. One registered combination form per programme (no formula
  search). λ / weights fitted strictly out-of-fold, frozen before prospective use.

### 3. Market interface

**Responsibility.** Expose the frozen, versioned `p_market_info` as a *separate* input,
never conflated with the fundamental. Market-relative work (does a layer add information
*beyond the observed market*, not beyond F2) lives here and is judged separately.

- **Input:** the governed information price `p_market_info` (versioned, as-of, side- and
  size-agnostic model input) and, where a decision layer is in scope, `odds_exec`.
- **Output:** market-anchored quantities only through a single registered formula (the
  Stage 2G `MARKET_ANCHORED_RESIDUAL` shape is the reference pattern; any Stage 3 use is a
  new registration). Disagreement is a signed logit gap, never a profitability claim.
- **Prohibitions:** `p_market_info` never enters a *fundamental* (F2 or any residual);
  the market is never treated as outcome truth; `p_close` is diagnostic only; no bookmaker
  odds enter any fundamental (field-use registry). No pre-off passive execution assumption.

### 4. Feature registry interface

**Responsibility.** The single authority on which raw fields any layer may read, and for
which use. Extends the existing `l3_features/feature_registry` and the frozen
`specs/evidence/tennis-data-field-registry-v1.yaml` /
`specs/programme/stage2g-field-use-policy-v1.yaml` overlays.

- **Contract:** every field is classified APPROVED-CENTRAL / APPROVED-DIAGNOSTIC /
  DEFERRED / PROHIBITED per intended use; anything unlisted is UNCLASSIFIED ⇒ not usable
  (fail closed). A Stage 3 layer declares exactly which registry entries it reads; a read
  of an unlisted field is a hard build-time error, not a warning.
- **Prohibitions:** no field moves class by convenience (governed version + review only);
  bookmaker odds stay QUARANTINED from fundamentals; surface stays prohibited *as an F2/DP1
  rating input* (F3 precedent) unless a wholly new, separately governed design justifies it
  and passes gate zero and the Stage-2 gates.

### 5. Knowledge-time registry interface

**Responsibility.** Enforce SPEC-020/022/023 for every signal a layer uses: prove it is
usable strictly before market off, in *live* knowability, not merely backfilled.

- **Contract:** each signal carries event time, source publication time, provider
  timestamp, ingestion receive time, first-usable time, decision time, correction time,
  and a provenance mode (live-captured vs backfilled). A signal whose first-usable time is
  not provably before the off is **rejected at build time** (error, not warning).
- **Adapter-declared boundaries:** the live knowability floor is adapter-declared, never
  assumed (racing's "only ever delayed" floor is NOT valid for tennis; F-01). "Seconds to
  actual start" is post-hoc-only and mode-explicit.
- **Prohibitions:** no reconciled closing benchmark, no post-event data, no actual-off
  time as a live feature; backfill confers no historical validity.

### 6. Uncertainty registry interface

**Responsibility.** Register, per layer, the *exact* uncertainty quantity it emits, its
nominal level, its type (parameter / latent-strength / predictive), and the exact test
that would measure its calibration — *before* results. This closes the Stage 2G governance
gap where an interval was reported with no frozen empirical coverage gate.

- **Contract:** a layer's uncertainty output is a typed object (cf. the edge-distribution
  lower bound `l5_decision.ev.WinProbabilityLowerBound`, SPEC-034, and DP1's analytic
  `WinProbabilityDistribution`, SPEC-106). Structural properties are mandatory and
  property-tested (widens with stated uncertainty inputs; never narrows without evidence;
  ordering and finiteness always hold). An *empirical* coverage claim is a gate **only** if
  a valid coverage test was frozen in advance; otherwise coverage is DIAGNOSTIC and a
  governance gap is recorded — never a post-result threshold.
- **Prohibitions:** no fabricated percentage around a point estimate; a point estimate is
  never consumable by a decision layer where a distribution is required (type-enforced).

### 7. Evaluation interface

**Responsibility.** One model-independent, chronological, out-of-fold evaluation path for
every layer — the same `cross_fit` orchestrator and the same paired, day-clustered proper
scoring used in Stage 2, so no layer gets a bespoke scoreboard.

- **Contract:** choice-set-level log score and multiclass Brier; calibration-in-the-large
  and slope (SPEC-097); reliability by band; coverage-with-exclusions; **paired,
  chronology-aware** comparison against Frozen F2 (block bootstrap clustered by the
  adapter's correlation-cluster key, SPEC-090). Evidence roles are frozen and labelled:
  RAW_HONEST / IN_SAMPLE_CALIBRATION_DIAGNOSTIC / CALIBRATED_HONEST. Determinism/replay is
  required; raw output must reproduce byte-identically across runs.
- **Prohibitions:** no unpaired aggregate substituted for the paired comparison; no
  selection-level independence assumptions anywhere; no ROI/P&L/CLV as a selection or
  training criterion; ROI at most a clearly-secondary frozen-policy diagnostic. No metric
  value is read before artefacts are finalized and hashed.

### 8. Evidence interface

**Responsibility.** Bind every layer to the immutable evidence spine: the trial ledger
(SPEC-091, multiplicity debited), the deterministic gate evaluator (SPEC-093 — an LLM
never decides a gate), the lockbox discipline (SPEC-092), immutable prediction snapshots
(SPEC-037) and the mutation gate on any money-critical module it introduces.

- **Contract:** a candidate is a *registered trial* before it is scored, with
  pre-registered endpoints, minimum economically-meaningful effect, power, primary
  endpoint and stopping rule (SPEC-094) — borrowed constants forbidden. Gate evaluation is
  `gate evaluate --spec … --data-manifest sha256:… --model-manifest sha256:…`, returning
  PASS | CONTINUE | FAIL_* from a versioned spec bound to data and model hashes. Every
  money-critical module is 100%-non-equivalent-mutant-killed or has per-ID founder-approved
  equivalents; approvals are fingerprint-bound and environment-tagged where identity-bound.
- **Prohibitions:** no promotion on development evidence; confirmation only on post-freeze
  observations; no re-use of a spent lockbox; no threshold changed after result opening.

---

## Composition (how the interfaces fit)

```
              ┌─────────────────────────┐
 choice set ─▶│ 1. Sporting baseline    │─ p_baseline (frozen F2, OOF) ─┐
              └─────────────────────────┘                               │
              ┌─────────────────────────┐   ┌──────────────────────┐    ▼
 signals ────▶│ 4. Feature registry     │──▶│ 5. Knowledge-time    │─▶ 2. Residual ─▶ p_combined
              │    (what may be read)    │   │    (usable pre-off)  │   (independence-obligated)
              └─────────────────────────┘   └──────────────────────┘        │
                                                                            ▼
 market ─────────────────────────────────────────────────▶ 3. Market interface (separate; p_market_info)
                                                                            │
 every layer's uncertainty ─▶ 6. Uncertainty registry (typed, pre-frozen test)
                                                                            │
 all of the above ─▶ 7. Evaluation (one OOF paired path) ─▶ 8. Evidence (ledger, gates, lockbox, snapshots)
```

The baseline is fixed; a residual must prove independence from it; the market is a
separate axis; features are gated by lawfulness and knowledge-time; uncertainty and
evaluation and evidence are shared, frozen, and identical for every candidate.

## What this document deliberately does NOT do

- It defines **no** model family, feature, formula, threshold, or parameter.
- It authorises **no** code. The named modules are existing anchor points; Stage 3 adds
  contracts here, implementation only under a future founder directive that names the
  specific layer and its registered trial.
- It does not reopen F2/F3/DP1. Those are closed history.

Implementation of any Stage 3 layer begins only when a hypothesis in
`STAGE3_HYPOTHESIS_REGISTER.md` has passed gate zero and a future founder directive
authorises that specific layer under `STAGE3_IMPLEMENTATION_POLICY.md`.
