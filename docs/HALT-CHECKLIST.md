# Final Halt Checklist — v1.1

**Approval posture:**

> **Version 1.1 — Conditionally approved for offline implementation through Phase 2.**
> This approval authorises NO live Betfair credentials, NO API order submission, NO
> real-money activity, NO passive-execution claims, NO dynamic model updates, NO Kelly
> sizing, and NO production deployment. Those remain HALTED until their corresponding
> gates are satisfied and separately approved.

---

## Gate −1A — before Phase 1 (research authorisation)
- [ ] Every source in the licensed-source registry, provisionally lawful for offline research
- [ ] Sources not yet reviewed are labelled `candidate`, not `permitted`
- [ ] Maximum research spend explicitly capped
- [ ] Maximum sunk cost acceptable **even if the edge is zero**
- [ ] No live credential, no placement capability, no betting bankroll exists
- [ ] Scenario analysis: what edge/frequency/stake would justify later live access
- [ ] `specs/prices/*-v1.yaml` frozen **before** any performance examined
- [ ] `docs/facts.yaml` populated and in date

## Gate 0A — before pricing research (offline measurement truth)
- [ ] Raw historical market messages retained (application bytes, pre-parse)
- [ ] Deterministic reducer implemented and versioned
- [ ] **Canonical** replay: same env digest → same canonical output hash
- [ ] Historical state and derived features reproducible
- [ ] Simulated settlement fixtures cover every case in §6.8
- [ ] **Universe ledger frozen before outcomes known**; full exclusion funnel present
- [ ] Every eligible market accounted for; no silent disappearances
- [ ] Failure-injection and replay-regression tests pass

## Gates 1 & 2 — before the £499 decision
- [ ] Cross-fitted, time-respecting, strictly out-of-fold — α not spuriously inflated
- [ ] Race-level paired inference, block-bootstrapped by meeting-day
- [ ] Lockbox consumed **once**, never inspected during development
- [ ] Every trial in the ledger; multiplicity accounted for
- [ ] Gate 2 uses **latency-adjusted, size-aware scenarios** — not "actual" historical prices
- [ ] Policy-value lower bound (race-day-block), including no-bets and failed executions
- [ ] Positive conservative value at crossable prices **before** any passive credit

## Gate −1B — before paying £499
- [ ] Gate 2 produced a policy-level lower bound on net executable value
- [ ] Opportunity frequency measured from the frozen universe
- [ ] `N_eligible × r_select × r_fill × S̄ × ROI_lower − C_recurring` computed
- [ ] Conservative payback horizon fits the precommitted maximum
- [ ] Three budgets separate: research capital / bankroll / experiment-loss
- [ ] All volatile facts re-verified; none stale

## Gates 0B & 3 — before real money
- [ ] Live operational-readiness spec implemented (§12.8); fails closed on every listed condition
- [ ] Raw live order stream captured; API commands reconciled
- [ ] `listCurrentOrders`, cleared orders, account statements reconciled
- [ ] Unknown order state blocks all placement
- [ ] Actual commission and settlement agree with the account statement
- [ ] Process restart and reconnect recovery pass
- [ ] `taker-v1` verified against **current live API semantics**: FOK, full-size minFill,
      no resting remainder. If unachievable, the cancellation/reconciliation mechanism is
      specified and tested.
- [ ] One position per market enforced by transactional reservation **and** a storage
      uniqueness constraint
- [ ] Retry invariant: no blind retry after timeout; reconcile by customer reference first

## Gate 4 — before any passive claim
- [ ] Eligibility frozen before randomisation
- [ ] Randomisation before future book movement observed
- [ ] Stratified allocation; every arm has non-zero probability; seed recorded
- [ ] Propensities logged
- [ ] Primary analysis is randomised ITT; IPS/DR secondary only
- [ ] Envelopes labelled **stress scenarios**, not statistical bounds
- [ ] Benefit does not exist only under the optimistic scenario

## Always true
- [ ] Claude's environment has no live Betfair credentials
- [ ] Project hooks are not treated as the deployment trust boundary
- [ ] CI cannot self-attest: workflows human-owned; verification outside the PR's tree
- [ ] Bypass list verified empty (not assumed)
- [ ] Model lineage carries source IDs; unapproved lineage rejects the build
- [ ] No automatic live learning of any deployed parameter
- [ ] Kill switch handles irreducible matched exposure; no auto-hedge
- [ ] Watchdog outside the trading process
- [ ] Production loads no models or config from a writable path
- [ ] Gates return PASS | CONTINUE | FAIL_HARM | FAIL_FUTILITY — never a boolean
