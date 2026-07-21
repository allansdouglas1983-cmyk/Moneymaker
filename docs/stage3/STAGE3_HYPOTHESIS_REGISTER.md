# STAGE 3 HYPOTHESIS REGISTER — append-only

Status: ACTIVE (founder directive STAGE3-0001). **Append-only.** A hypothesis is never
edited to look better after evidence; a superseding entry is added and the old one keeps
its status. No implementation is authorised by an entry here — registration is *gate
zero*, not a build order.

## Purpose

Stage 3 seeks information **genuinely independent of Frozen F2-v1**. This register is the
single place a candidate information layer is written down and forced to answer the five
gate-zero questions *before* any code. A hypothesis that cannot answer all five is not a
Stage 3 candidate. Entry here confers no priority, no approval, and no authorisation to
implement.

## Required fields (every entry)

| field | meaning |
|---|---|
| **Identifier** | `H3-NNNN`, immutable, never reused |
| **Title** | one line |
| **Information introduced** | the exact new signal, named and bounded (gate-zero Q1) |
| **Independence from F2** | why Frozen F2 cannot already represent it, structurally (Q2) |
| **Data required** | the exact fields/sources, with their registry classes |
| **Knowledge-time risks** | why it might NOT be knowable strictly pre-off; the live floor it relies on (Q3) |
| **Lawfulness** | source-rights / field-use position for the intended use (Q4) |
| **Expected complexity** | rough money-module surface, mutation burden, new registries |
| **Validation method** | the pre-registered, post-freeze measurement that could confirm/deny independent information (Q5) |
| **Promotion criteria** | the exact frozen thresholds that would justify progression (paired non-harm + independent-information gain, calibration, coverage) — declared before observation |
| **Failure criteria** | the exact conditions that retire it (no independent information; not knowable; unlawful; unstable) |
| **Current status** | one of the lifecycle values below |

## Lifecycle status values

`PROPOSED` → `GATE_ZERO_PASSED` → `TRIAL_REGISTERED` → `IN_DEVELOPMENT` →
`AWAITING_PROSPECTIVE` → `PROMOTED` | `FAILED_*` | `WITHDRAWN`.

- A hypothesis moves past `PROPOSED` only when all five gate-zero questions are answered
  and recorded.
- A hypothesis reaches `TRIAL_REGISTERED` only via `l8_evidence.trial_ledger` with
  pre-registered endpoints and multiplicity debited (SPEC-091/094).
- `PROMOTED` requires post-freeze prospective confirmation on the same governance as
  Stage 2, and a future founder directive.
- `FAILED_*` is permanent programme history (like F3 / DP1); the entry stays, reproducible.

## Programme history anchors (closed; not Stage 3 candidates)

These are recorded here only so a new hypothesis cannot silently re-propose a closed idea
without citing why the closure does not apply.

| ref | disposition |
|---|---|
| F2-v1 global Elo | PROMOTED HISTORICAL BASELINE (the reference every Stage 3 layer must beat, independently) |
| F3 surface Elo | FAIL_HARM (surface as a rating input is closed) |
| DP1 dynamic Glicko-2 | STOP_DP1_HARM (dynamic RD/volatility/inactivity did not add information over F2) |

A Stage 3 hypothesis that reintroduces surface, or reintroduces "richer own-history
dynamics," must explicitly distinguish itself from F3 / DP1 and pass gate zero on Q2
(independence) — the burden is on the new entry.

## Entries

*(none yet — this register opens empty. The first entries are added when candidate
information layers are proposed; each must complete every required field before it may
advance beyond PROPOSED. No entry authorises implementation.)*

### Template (copy for a new entry; do not edit existing entries)

```
### H3-0001  <Title>
- Information introduced:
- Independence from F2 (why F2 cannot represent it):
- Data required (with registry classes):
- Knowledge-time risks (live floor relied upon):
- Lawfulness (source-rights / field-use for intended use):
- Expected complexity:
- Validation method (pre-registered, post-freeze):
- Promotion criteria (frozen thresholds, declared before observation):
- Failure criteria:
- Current status: PROPOSED
```

## Standing expectation

Most candidate layers are expected to carry **no** information independent of Frozen F2 —
that is the null and the likely truth. A hypothesis that looks strong on development data
is a suspected artefact until a pre-registered post-freeze measurement says otherwise.
Registering a hypothesis is cheap; promoting one requires the full Stage-2 evidence spine.
