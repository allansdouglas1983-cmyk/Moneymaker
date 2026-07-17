"""L6 — Broker layer (money-critical). Order state machine + idempotent book of record.

SPEC-070 (order state machine, illegal transitions raise) and SPEC-071 (idempotent
placement, duplicate commands add no economic exposure). Phase 3A OFFLINE construction
(ADR 0014, founder decisions 6-7): no live credentials, no networking, no real
placement — this package is the deterministic order-domain core only. The real
out-of-process watchdog, the fill model, and staking logic are explicitly out of scope
here (see ADR 0014's "not authorised" list).
"""
