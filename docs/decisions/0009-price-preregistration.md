# 0009 — Frozen price pre-registration (`specs/prices/*-v1.yaml`)

- **Status:** Accepted (pre-registration)
- **Date:** 2026-07-15
- **Scope:** `specs/prices/info-price-v1.yaml`, `exec-price-v1.yaml`, `close-v1.yaml`.
- **Spec:** SPECIFICATION.md §4 (the three prices), §11 Phase 0/1, §6.6.

## Context

§4 requires the three prices to have **versioned, frozen definitions committed before any
performance is examined**. "Changing `p_market_info` after seeing results is changing the model."
No historical data has been ingested or examined in this repository, so freezing a single,
documented definition now is the correct pre-registration posture — there is nothing to
cherry-pick against. Alternatives (microprice, size-weighting, …) are **separate future
pre-registered experiments** (`info-price-v2`, …), not edits to this file.

## Decisions (the frozen values, with rationale)

- **`info-price-v1`** — `p_market_info`, the model input:
  - Probability space is **implied probability** (explicit). The per-runner raw value is the
    **midpoint of the best-back and best-lay implied probabilities** (`(1/back + 1/lay)/2`), then
    **normalised across active runners to sum to 1** (removes the book overround).
  - **No size/spread weighting in v1** — spread and available size are retained as diagnostics/features
    but do not adjust the value (size-weighting is a v2 experiment).
  - Staleness: reject a book older than **5000 ms** at decision time. One-sided book → use the
    available side; crossed book → treat as unusable (skip that snapshot); a runner with no usable
    price is excluded with a knowledge-time and the field renormalised; a race is priceable only if
    **≥ 2 active runners** have a usable price. REMOVED runners are dropped before normalisation.
  - Timestamp tie-break: the last-applied update (highest `capture_sequence`) — deterministic per the
    reducer's append order.

- **`exec-price-v1`** — `odds_exec`, the transactable price. BACK only, fixed canary stake,
  `taker-v1` (FOK, full-size). The price is a **worst-acceptable bound** at the decision-time best-back
  tick with **zero adverse slippage tolerance** in v1; insufficient depth for the full size → **reject
  (no partial fill)**. A conservative **250 ms** decision→arrival latency assumption feeds Gate-2
  latency-adjusted scenarios (validated only at Gate 3).

- **`close-v1`** — `p_close`, diagnostic only: primary **BSP**; secondary **pre-suspension WAP over
  the final 60 s**, in-play updates excluded. Both retained (BSP is a strong benchmark, not an oracle).

## Consequences

- These files are frozen and human-owned (`specs/**` in CODEOWNERS). The Phase-2 `p_market_info`
  builder consumes `info-price-v1`; the decision layer's `odds_exec` follows `exec-price-v1`; grading
  uses `close-v1`. Changing any value is a new version + a new pre-registered experiment, never an
  in-place edit after results are seen.
- `specs/gates/v1.yaml` (pre-registered endpoints, §9/§10) remains to be authored with the L8 gate
  evaluator slice; it depends on the minimum-economically-meaningful-effect and power assumptions,
  which are a separate pre-registration.
