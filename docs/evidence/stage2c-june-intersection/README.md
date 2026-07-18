# Stage 2C — prospective June M2 intersection manifest (OUTCOME-BLIND)

**June remains SEALED (SPEC-092).** This is prospective planning metadata derived only from
SAFE_BEFORE_LOCKBOX fields (pre-off Betfair prices, schedule, identity + pre-June history
existence). **No sporting outcome is read.** `scripts/june_intersection.py` joins the two
frozen per-market June manifests by `market_id`:

- `docs/evidence/stage2b-f0-f2-runs/F0_MARKET_YARDSTICK_MANIFEST.jsonl` — committed
  `p_market_info` (F0 COMMIT_ONCE state machine over pre-off books).
- `docs/evidence/tennis-data-2026-07-18/JUNE_F2F3_ELIGIBILITY_MANIFEST.jsonl` — governed
  identity + pre-June history existence (whether F2 can emit a probability).

## The M2 unit needs BOTH a fundamental and a market price

M2 compares *market-only* vs *pre-fitted combined*; the combined probability needs both an
F2 fundamental **and** a committed F0 market price. So the relevant June count is the
**intersection**, not the F2-eligible count alone:

| Quantity | Count |
|---|---|
| Total June primary singles (frozen universe) | 2,876 |
| F0 committed `p_market_info` | 2,518 |
| F2-valid (emits from pre-June history) | 1,218 |
| **Final prospective M2 intersection (F0-committed ∧ F2-valid)** | **1,027** |
| — strict cohort | 968 |
| — primary-only tier | 59 |
| UTC calendar-day clusters in the intersection | 30 (min 3 / median 34 / p90 52 / max 63) |

Prior-history cohorts in the intersection: `1-4`: 351, `5-9`: 118, `10-19`: 111, `20+`: 447.

Exclusion funnel (outcome-blind): F0 uncommitted — `NO_VALID_COMMIT_WINDOW` 332,
`NO_TWO_SIDED_BOOK_AT_COMMIT` 26. F2-ineligible — dominated by `NO_SOURCE_MATCH` (1,431) plus
homonym/cross-namespace refusals. Of the 1,218 F2-valid markets, **191 had no committed F0
price**; of the 2,518 F0-committed markets, 1,491 were F2-ineligible.

## What this means

The prospective M2 sample is **~1,027 markets across only 30 calendar-day clusters** — far
below the ~32,212 paired units the planning σ_d implies for a decisive test at δ = 0.0007. **A
June M2 result is expected to be CONTINUE / INCONCLUSIVE by design** (`probability-m2.yaml`);
δ, confidence, and clustering must not be changed to force a decision.

## Gates applied (all outcome-blind) and the deferred gate

Applied now: in-universe · F0 committed · both identities governed · F2 emits from pre-June
history · final affine calibration available (global). **Deferred to June opening:** the
selected-outcome-policy scoring gate (completed singles, `label-policy-v1`) — evaluable only on
opening and can **only reduce** the count. So 1,027 is the **prospective maximum**.

## Known gap (reported, never fabricated)

The **ATP/WTA split** of the intersection is **not derivable** from these two frozen per-market
manifests (neither carries a tour tag). Producing it requires a governed join of the June market
catalogue competition/tour tag (a SAFE_BEFORE_LOCKBOX field) added at manifest finalization
before opening. It is left as an explicit gap, not fabricated (Stage 2C §10).

Manifest digest:
`sha256:9f747bfae843401d44ce9c7388e20f95718f955a8e2fbac69424d5c736ddc885` (over the file bytes
of `JUNE_M2_INTERSECTION_MANIFEST.json`).
