# ADR 0014 — Phase 3A: offline broker/risk construction (founder-authorised scope)

**Status:** accepted (founder decisions 6–7, 2026-07-16). **Scope is a ceiling, not a
target list to exceed.**

## Authorised scope → SPEC-ID mapping

| Founder item | SPEC-ID(s) | Notes |
|---|---|---|
| Order state machine | **SPEC-070** | CREATED→…→SETTLED/RESETTLED; illegal transitions raise; stateful model-based test REQUIRED by the spec text. marketVersion-lapse transitions (SPEC-072's state-machine half) are modelled as transitions; the live guard wiring stays out of scope. |
| Idempotency + duplicate-exposure prevention | **SPEC-071** | customerOrderRef-keyed; property test: exposure invariance under duplicated commands. |
| Unknown-state fail-closed logic | **SPEC-062** | Any order in unknown state blocks ALL placement until reconciled; no timeout-assumption of failure. |
| Reconciliation model | **SPEC-083** (+ **SPEC-081** semantics) | Differential comparison of local reducer state / listCurrentOrders / order stream / statement; unresolved difference blocks placement; statement wins. Offline model + simulated inputs only. |
| Market reservation | (SPEC-054 extension into broker) | One-runner-per-market reservation at the broker boundary: a market with any live or unknown order refuses a second intent. |
| Kill-switch / watchdog CONTRACTS | **SPEC-063**, **SPEC-064** | The seven SPEC-063 obligations as typed contracts + a simulated in-process harness; the real out-of-process watchdog deployment is Phase 3B (not authorised). |
| Simulated restart/disconnection tests | (test obligation) | failure_injection suites over the above. |
| Simulated / delayed adapters | **SPEC-102** | Real-money placement impossible BY CONSTRUCTION: the only adapters that exist are Simulated and DelayedKey types; no production endpoint, no live credential type exists in the codebase. |

## Explicitly NOT authorised (fail closed on all of these)

Live credentials; production networking; real placeOrders enablement; real-money
activity; passive execution; the fill model (SPEC-040–043); stake scaling / staking
logic beyond what SPEC-054 reservation needs (SPEC-060/061/065 stay planned and
untouched); Live App Key purchase; SPEC-073/074 (rate alarm / stream polling —
production-networking adjacent); SPEC-104 activation.

## Conventions

Money-critical (l6_broker, l5b_risk-adjacent contracts): the three rules bind; lead
reviews every line; red tests committed first; manifest flips planned→active only for
IDs whose offline obligations are fully implemented and covered — activation here
asserts CI enforcement of the offline contracts, NOT live readiness. Each money ID
needs `relevant_inputs` + `metamorphic_properties` declared at activation
(SPEC-062/083 currently lack them in the manifest — they will be added in the
implementing slice, enforcement-increasing). Mutation targets extend to l6_broker
when the slice lands.
