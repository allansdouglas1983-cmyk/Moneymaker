---
paths:
  - "analytics_contracts/**"
  - "l8_evidence/prediction_snapshots.py"
  - "l8_evidence/predictor_metrics.py"
  - "l8_evidence/explanation_inputs.py"
  - "l4_pricing/probability_outputs.py"
  - "governance/output_rights.py"
---
# Analytics-consumer rules (SPEC-036-039, 044-048 · ADR 0013)

You are editing the READ-ONLY analytics consumer of the probability platform.

## Never
- Import or depend on l5_decision, l5b_risk, l6_broker, l7_settle, order/account/execution
  state, risk budgets, or credentials (CI import-quarantine enforced).
- Write into pricing models, features, trading decisions, execution, risk, settlement or
  gate results.
- Alias one probability as another; substitute a missing probability silently; let
  p_combined overwrite p_fundamental; label p_market_info a model prediction.
- Mutate a prediction snapshot; write results/BSP/future prices into a pre-off snapshot;
  select a forecast vintage after the result.
- Let an LLM create/alter/smooth/repair a probability, assign recommendation status, or
  invent an explanation reason.
- Emit a TIP/BET/selection state — recommendation status is NOT_EVALUATED until a future
  gated specification.
- Introduce any paid dependency or service (authorised external budget: £499, reserved for
  the Live App Key).

## Always
- Append-only snapshots; new information mints a NEW prediction_id with a supersedes link
  and deterministic update reasons; "latest" is derived from the chain.
- Carry transitive source lineage; publication eligibility fails closed; internal research
  eligibility and publication eligibility stay separate.
- Version benchmarks and evaluation policy; refuse horizon-mismatched comparisons; keep
  missing forecasts in the coverage denominator.
- Race-level proper scores; the race is the unit of analysis.
- Publication is forbidden until Gate P1 (SPEC-046) is activated by a human and passed.
