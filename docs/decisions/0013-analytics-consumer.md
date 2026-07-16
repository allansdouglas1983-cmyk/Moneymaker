# 0013 — Prediction & analytics consumer foundations (SPEC-036–039, 044–048)

**Status: accepted 2026-07-16.** Founder-supplied specification (session chat) plus
Amendment A (same day, received before any implementation — all items incorporated; no
committed-test conflicts existed). This ADR is the product-strategy record the task requires.

## The strategic decision

The platform is an **evidence and probability engine with multiple possible downstream
consumers**. The private trading research system is the first consumer. A future prediction
and racing-analytics product may consume approved probability outputs through a separate,
versioned export contract. This is an **additional layer, not a pivot**: nothing in the
trading validation chain (Gates 1/2, EV, risk, execution, settlement) is weakened, altered,
or made publication-aware; the analytics path is a strictly read-only consumer.

- **Shared components:** L0–L3 capture/replay/features, the L4 probability engine, model
  manifests and lineage, the evidence machinery (race-level proper scores, calibration),
  the licensing registry, the deterministic gate evaluator.
- **Private components (never exported):** EV/decision logic, execution policy, risk
  budgets, order/settlement state, account state, any Betfair credential or live state.
- **Why trading edge and predictor value are different questions:** a trading edge requires
  beating the market *after* costs at executable prices; predictor value requires
  calibrated, honest, well-explained probabilities that beat approved baselines on proper
  scores. The second can exist without the first — that is exactly the optionality this
  layer preserves.
- **Gate P1 (SPEC-046)** may be activated only by explicit human approval after Gate 1
  results exist. No product, UI, API, tips, or publication are authorised by these
  foundations; recommendation status is pinned to NOT_EVALUATED.
- **Publication may be deferred or restricted even if predictor value exists** — if private
  trading alpha is present, publishing calibrated probabilities could erode it; the
  publication decision is a separate, human-owned call behind Gate P1.

## SPEC-ID collision and remapping

The founder's task numbered the new requirements SPEC-036–042 (+ Amendment A's 043/044),
but **SPEC-040–043 already exist as the l4b_fill money requirements**. Per the task's own
change-management rule (report, never silently change an earlier requirement), the new
specs are renumbered onto free IDs; the founder's documents map as:

| Founder task | Manifest ID | Subject |
|---|---|---|
| SPEC-036 | **SPEC-036** | Separate probability outputs (p_fundamental / p_market_info / p_combined) |
| SPEC-037 | **SPEC-037** | Immutable prediction snapshots + forecast vintage/revision chains (Amendment A §1) |
| SPEC-038 | **SPEC-038** | Predictor performance ledger + versioned benchmark/evaluation-policy registry (Amendment A §3) |
| SPEC-039 | **SPEC-039** | Deterministic explanation inputs |
| SPEC-040 | **SPEC-044** | Commercial-output licensing lineage |
| SPEC-041 | **SPEC-045** | Exportable prediction contract + three independent statuses (Amendment A §2) |
| SPEC-042 | **SPEC-046** | Gate P1 — predictor product evidence (planned; human-activated after Gate 1) |
| Amendment 043 | **SPEC-047** | Forecast issuance/abstention policy (planned) |
| Amendment 044 | **SPEC-048** | Transparent scorecard & claims governance (planned) |

## Design decisions

1. **Placement reuses existing boundaries:** `l4_pricing/probability_outputs.py` (036);
   `l8_evidence/prediction_snapshots.py`, `predictor_metrics.py`, `explanation_inputs.py`
   (037–039); `governance/output_rights.py` (044); a new read-only `analytics_contracts/`
   package (045); `specs/gates/predictor-p1.yaml` (046). No UI/delivery directories.
2. **Import boundary, CI-enforced:** `analytics_contracts` and the predictor evidence
   modules must not reach `l5_decision`, `l5b_risk`, `l6_broker`, or `l7_settle` —
   additional `check_import_quarantine` invocations in Makefile + CI (the checker already
   handles transitive and literal dynamic imports, fail-closed). Reading official results
   for scoring goes through the approved evidence boundary.
3. **Statuses land `planned` and flip `planned → active` inside each implementing slice**
   (the repo's standing convention; the founder's "active" recommendation is honoured at
   implementation time so CI never asserts coverage that does not yet exist). SPEC-046/047/
   048 stay `planned` until their own human-approved activation.
4. **Amendment A is folded in from the start:** vintage/revision chains inside SPEC-037;
   the three independent statuses (availability / publication / recommendation) inside
   SPEC-045 with recommendation hard-pinned to NOT_EVALUATED; the versioned benchmark and
   evaluation-policy registry inside SPEC-038; `research_basis_ids` provenance accepted as
   an optional field on manifest entries, ADRs, and benchmark/gate definitions (a research
   report informs a decision — it never proves a gate).
5. **Budget constraint (£499):** no paid dependency, service, API, or infrastructure —
   already true by construction (runtime deps: pydantic + pyyaml) and kept true; any
   proposed expenditure is a BLOCKING escalation plus Gate −1 authorisation.
6. **The three-rules discipline is unchanged:** no LLM creates/alters/smooths/repairs any
   probability, assigns recommendation status, or produces explanation reasons;
   explanations are deterministic attributions over approved features (exact signed
   coefficient contributions for the v1 linear model), versioned and reproducible.
7. **Trading behaviour is untouched:** no file in l5_decision/l5b_risk/l6_broker/l7_settle
   changes in this task; the probability engine gains read-only output wrappers only.
