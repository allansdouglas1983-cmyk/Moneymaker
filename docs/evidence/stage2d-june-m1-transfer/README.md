# Stage 2D — prospective June M1 transfer manifest (OUTCOME-BLIND)

**June remains SEALED (SPEC-092).** Prospective planning metadata from SAFE_BEFORE_LOCKBOX
fields only (schedule, Betfair runner names, pre-June Tennis-Data history). **No outcome
read.** Distinct from the M2 intersection because **M1 does not require an F0 market
snapshot** — only a calibrated-F2-valid prediction. `scripts/june_m1_manifest.py` reuses the
governed `td-norm-v1` bridge resolution of `eligibility_and_designs.py`.

## Tour derivation — from governed identity provenance, never inferred

Each June singles market's two runner names are resolved through the bridge; the **tour is
the identity namespace** each player resolves into (`m.source.tour` → `td-atp` / `td-wta`).
Both `td-atp` → **ATP**; both `td-wta` → **WTA**; **contradictory** namespaces → typed
`REFUSED_TOUR_PROVENANCE:MIXED_TOUR`; unmapped → identity exclusion. Tour is **never**
inferred from name strings, tournaments, prices, or outcomes.

## Counts

| Quantity | Count |
|---|---|
| Total June primary singles | 2,876 |
| **Calibrated-F2-valid (single-tour)** | **1,213** |
| — ATP | 592 |
| — WTA | 621 |
| — strict cohort | 1,150 |
| — primary-only tier | 63 |
| Mixed/unknown-tour refusals | 5 |
| Identity-excluded | 1,658 |

**Reconciliation:** the 1,218 both-mapped markets = **1,213 single-tour + 5 MIXED_TOUR**
typed refusals. The 5 mixed-tour markets are F2-emittable but cannot be assigned a governed
tour, so they are refused from the tour-tagged M1 population (SPEC-038 — visible, not dropped).

Prior-history cohorts (ATP / WTA): `1-4` 223/197, `5-9` 74/64, `10-19` 59/74, `20+` 236/286.

Calendar-day clusters: overall **30 days** (min 5 / median 36 / max 125); ATP 30 days, WTA 29
days.

## Support verdict (threshold fixed before counts, per the approved amendment)

`minimum_supported_predictions = 500`. **ATP 592 ≥ 500 ✓, WTA 621 ≥ 500 ✓, overall 1,213 ≥
500 ✓** — both tours are **supported**, so the tour-specific M1 calibration requirements can
be evaluated on June (support-wise). Any subgroup (reliability band, prior-history cohort)
below 500 remains diagnostic/CONTINUE, never fabricated. The threshold is not to be altered
now that counts are known.

## Provenance

Each record carries: `f2_can_emit`, `calibrated_f2_valid`, `tour`, cohort, prior-history
band, `outcome_eligibility_policy` (label-policy-v1-completed-only), exact exclusion reason,
`calendar_day_cluster`, selected model (`EXP-STAGE2-F2-GLOBAL-ELO-001`) and calibration
provenance (calibration-policy-v2; final ATP/WTA params; scorecard digest `6001657753…`).

Manifest digest:
`sha256:d192b4e3a3980fd3e2108a3efd68feb03d15e041a436569353178395f8b17b23` (over the JSONL
bytes). Summary: `JUNE_M1_TRANSFER_SUMMARY.json`.
