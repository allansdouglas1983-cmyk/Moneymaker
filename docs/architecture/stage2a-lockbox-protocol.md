# Stage 2A — Tennis Lockbox & Outcome-Governance Protocol

**Status:** DEFINED 2026-07-18 as part of the Stage-2A validity-protection slice
(baseline `specs/programme/baseline-v1.yaml`; ADR 0018 closed Stage 1). This protocol
governs how — and only how — outcome information becomes accessible to the tennis
probability programme. It is authored **before any model, feature or outcome read** so
that every later modelling result is credible. It extends, and does not weaken, SPEC-092
(lockbox integrity), SPEC-020/021/023 (knowledge-time / leakage), SPEC-091 (trial ledger)
and SPEC-094 (pre-registration).

The protocol's guarantee: **accidental outcome contamination is structurally impossible,
and any replay can prove no prohibited field was read.**

---

## 1. Two structural mechanisms (already in the tree)

The existing `l8_evidence.lockbox.LockboxRegistry` (SPEC-092) records WHO opened a holdout
and WHEN — a permission/audit log whose `is_uncontaminated` feeds GATE-1. Its own docstring
notes it defers **data-layer blocking**. Stage 2A supplies that missing layer with two
new, additive structural facts:

1. **Field-access guard** — `l8_evidence.outcome_fields` (+ human-owned classification
   `specs/evidence/outcome-field-classification-v1.yaml`). Every corpus field is classified
   `SAFE_BEFORE_LOCKBOX / OUTCOME_CONTROLLED / POST_SETTLEMENT_ONLY / UNKNOWN` (fail closed).
   `assert_pre_lockbox_readable` raises `OutcomeFieldAccessError` on anything not provably
   safe; `PreLockboxAccessRecorder` produces an append-only, order-independent, digestible
   manifest of exactly which safe fields a reader touched — which, because `record` routes
   through the guard, **cannot contain an outcome field**.

2. **Outcome quarantine** — `l8_evidence.tennis_outcomes` is the single reserved home for
   outcome extraction; it REFUSES until authorised, and `make verify` forbids
   `l3_features` / `l4_pricing` from importing it (`check_import_quarantine`, mirroring the
   SPEC-021 `reconciled_bsp` quarantine). Feature and pricing code cannot even import the
   winner.

Permission (WHO/WHEN) is the lockbox registry; prevention (WHAT can be read) is these two.
Both are required; neither replaces the other.

## 2. What counts as outcome information

Authoritatively, the `OUTCOME_CONTROLLED` + `POST_SETTLEMENT_ONLY` + value-sentinel sets of
`specs/evidence/outcome-field-classification-v1.yaml` (Stage-2A Task 2). In summary:

- `runner.status` values `WINNER` / `LOSER` / `REMOVED` — the result itself.
- `marketDefinition.settledTime` — present only post-settlement.
- `marketDefinition.bspReconciled == true` — reconciled closing benchmark computed.
- `runner.removalDate`, `runner.adjustmentFactor` — withdrawal / reduction, settlement-adjacent.
- **Value sentinels** on otherwise-safe fields: `marketDefinition.status == CLOSED`,
  `marketDefinition.inPlay == true`. A pre-lockbox reader refuses the whole line carrying any.
- Any **unclassified** field (fail closed) — e.g. a future `spn/spf` BSP price field.

Everything else (prices `batb/batl/trd/ltp/tv`, schedule `marketTime/openDate/suspendTime`,
identity, `numberOfActiveRunners`, market structure) is `SAFE_BEFORE_LOCKBOX`, subject to
the universal knowledge-time line rule.

**Universal knowledge-time line rule.** Even a safe field may be read only from a stream
line whose `pt` is at/before the governed decision boundary (a horizon-instance crossing
from the marketTime state machine) and whose status is OPEN/SUSPENDED with `inPlay == false`.
A safe field read from a post-off line is a contamination.

## 3. Accessible before the lockbox opens

- The entire `SAFE_BEFORE_LOCKBOX` surface, subject to the line rule: reconstructed
  pre-off books, spreads, depth, matched volume, schedule/marketTime behaviour, horizon
  instances — i.e. the whole Stage-1 substrate and all Stage-2 **features** and
  `p_market_info`.
- All frozen Stage-1 evidence (`docs/evidence/pilot-2026-06-tennis/`), manifests, digests.
- Model training and cross-fitting on `p_fundamental`, calibration of predicted
  probabilities against **held-in** folds, and every proper-scoring computation whose label
  is NOT an outcome (there are none — see §5: no scoring against results before opening).

## 4. Accessible only after the lockbox opens (and only for the opening's declared purpose)

- Any join of predictions to results: choice-set log score, multiclass Brier,
  calibration-in-the-large/slope against realised winners, SPEC-090 paired inference,
  coverage-with-exclusions against settled markets.
- The `OUTCOME_CONTROLLED` / `POST_SETTLEMENT_ONLY` fields, via `l8_evidence.tennis_outcomes`
  (once that module is authorised and implemented in the outcome-opening slice).

## 5. Which analyses are legal before opening; which require authorisation

**Legal before opening (no outcome, proper statistical criteria only):**
- feature construction and feature-hash reproducibility (SPEC-024);
- fitting `p_fundamental` families and the stage-two combiner (parameters fit on
  winner-labels are NOT permitted — see below — so pre-opening fitting uses only
  out-of-fold structure that does not read the realised winner; the market-implied and
  structural-null baselines need no outcome at all);
- internal consistency checks: sum-to-1 within choice set, monotonicity properties,
  refusal on separated/unidentified data (SPEC-030), determinism/replay of feature and
  price artefacts;
- everything in the Stage-1 feasibility report.

> Note on fitting: conditional-logit / Bradley–Terry MLE fits parameters to the **winner**
> of each training-fold choice set — that IS an outcome read. Therefore model *training*
> consumes outcomes and is only legal on the **training/validation partition**, never on
> the lockbox partition, and only after the outcome-opening protocol authorises reading the
> training partition's results. The lockbox holds a DISJOINT partition (SPEC-092: never
> inspected during development). "Legal before opening" analyses are those needing no
> result at all; anything needing a result reads only the non-lockbox partition under the
> outcome-opening protocol, and the lockbox itself is read once, by GATE-1, at evaluation.

**Requires authorisation (opening event):**
- any read of the lockbox partition — permitted only for GATE-1 evaluation (SPEC-092);
- the first activation of outcome access on the training/validation partition (the
  outcome-opening slice: a governed protocol design + human sign-off, not a code default).

## 6. Who / what may open

- **The lockbox partition:** only `GATE_1_ID = "GATE-1"` via `LockboxRegistry.access(...)`,
  which grants AND burns in one logged step. Any other accessor burns it as
  `UNAUTHORIZED_ACCESS` and raises. No human "peek", no agent, no config override.
- **Training-partition outcome access:** the outcome-opening slice, authorised by the
  founder, implemented in `l8_evidence.tennis_outcomes` (which refuses until then). An LLM
  never opens outcome access and never reads a result.

## 7. How every opening is recorded

- Lockbox: `LockboxRegistry` appends a `LockboxEvent` (DEFINED / ACCESSED / BURNED) with
  dual-clock timestamp, accessor, purpose, gate_id, burn_reason — **log-then-grant** (the
  event is written before the grant/refusal), so a crash cannot hide an access.
- Trial ledger (SPEC-091): every evaluation that reads outcomes is a numbered
  `TrialRegistration` → `TrialCompletion`, prior-trial count recomputed from history
  (the caller cannot understate multiplicity), digest-anchored.
- Pre-lockbox readers carry a `PreLockboxAccessRecorder` whose manifest digest is written
  alongside the produced artefact.

## 8. How replay proves no prohibited field was accessed

A pre-lockbox producer (feature builder, price reconstructor) reads the corpus **only**
through `PreLockboxAccessRecorder.record(level, field)`. Because `record` calls
`assert_pre_lockbox_readable`, the run **cannot** touch an outcome field — an attempt is a
hard `OutcomeFieldAccessError`, not a silent read. The recorder emits a
`content_digest()` over the SET of fields accessed. Replay determinism (SPEC-010/011) means
the same inputs reproduce the same digest; a reviewer (or CI) asserts:

1. the manifest's field set ⊆ `SAFE_BEFORE_LOCKBOX` (true by construction, re-checked); and
2. the produced artefact's recorded access-digest reproduces on independent replay.

Together these turn "we were careful" into "the artefact carries a reproducible proof of
exactly which safe fields built it, and outcome fields were unreachable."

## 9. What this protocol does NOT do

- It does not open any outcome (the outcome-opening slice does, later, under authorisation).
- It does not select a benchmark, build a model, or engineer a feature.
- It does not weaken SPEC-092: the lockbox registry remains the sole permission authority;
  this protocol adds the data-layer block the registry deferred.
- It sets no numeric threshold (those live in the pre-registration record, PENDING founder).
