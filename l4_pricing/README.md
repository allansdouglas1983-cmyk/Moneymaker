# l4_pricing — L4 Pricing (two-stage)

**Layer:** L4 · **Spec:** SPECIFICATION.md §6.4 · **Criticality:** money
**Requirements:** SPEC-030…SPEC-035 · see `docs/spec-manifest.yaml` · **Phase 2 (`planned`)**

Stage one: conditional logit on the race as one mutually-exclusive choice set. Stage two:
`score_i = α·log(p_fundamental_i) + β·log(p_market_info_i)`, softmax within race. Cross-fitting
is mandatory and strictly time-respecting/out-of-fold, or α is spuriously inflated. Output
is a *distribution* over edge, never a point estimate reaching the decision layer.

> ⚠️ **No stubs, no LLM-produced numbers** (CLAUDE.md rules 1 & 3). Declared
> `relevant_inputs` + `metamorphic_properties` need property-based tests.
> **Status: not yet implemented** — Phase 2 IDs are `planned`, not yet CI-enforced.
