---
paths:
  - "l4b_fill/**"
  - "l5_decision/**"
  - "l5b_risk/**"
  - "l6_broker/**"
  - "l7_settle/**"
  - "l8_evidence/gates/**"
---
# Money-critical module rules

You are editing code that decides or moves real money.

## Never
- Stub, placeholder, constant-return, or "simplified for now". If you cannot implement
  the SPEC-ID fully, STOP and report which one is blocked and why.
- `NotImplementedError`, `TODO`, `pass  #`, bare `return None`, literal return where a
  computation is specified. CI greps for these and fails.
- Weaken, delete, or alter a test to make an implementation pass. A test correction is a
  separate, human-approved PR citing the SPEC-ID.
- Let an LLM produce a number that reaches this code.

## Always
- Each money SPEC-ID declares `relevant_inputs` and `metamorphic_properties`. Test those.
- **Do NOT assert "every output varies with every input"** — it is invalid here. Exhausted
  budget must always REJECT regardless of edge. A duplicate command must add no exposure
  regardless of differing fields. Guard branches legitimately dominate.
- Test instead: declared relevant inputs affect behaviour **in the specified regions**;
  irrelevant inputs do **not**; guards dominate correctly; domain invariants hold.
- Every documented monotonicity needs a property test.
- Tick index is an integer. Stake is integer minor units or exact Decimal. Never float.
- Timestamps carry UTC and monotonic.

## Structural facts — do not "simplify" these away
- Queue position is latent and unrecoverable from historical data. Fill model outputs
  probabilities, not positions.
- Three envelopes (pessimistic / optimistic / calibrated) always computed together.
  Optimistic-only profitability is a rejection.
- `odds_exec` is not `p_market_info` is not `p_close`. Distinct types.
- Commission is on the NET MARKET RESULT. Per-order commission is not authoritative.
- One runner per market in v1. If several clear the threshold: highest conservative net EV,
  explicit deterministic tie-break, never inspect outcome or future market move, record all
  rejected candidates.
- `taker-v1` = FILL_OR_KILL, minFillSize = full stake, price is the WORST ACCEPTABLE bound.
  No resting remainder. Any unexpected partial fill is an execution incident.
- No automatic live learning. Ever.
