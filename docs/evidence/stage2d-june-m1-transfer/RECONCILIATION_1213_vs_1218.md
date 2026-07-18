# Reconciliation — 1,213 (M1-valid) vs 1,218 (F2-eligible), OUTCOME-BLIND

**No June outcome was read to produce this. No market was manually removed.**

The frozen F2/F3 eligibility manifest (`docs/evidence/tennis-data-2026-07-18/`, digest
`96bd1f12…`) reports **1,218** both-player-mapped / F2-eligible June singles. The Stage-2D
prospective June M1 transfer manifest reports **1,213** calibrated-F2-valid markets. The
difference is **exactly 5 markets**, all typed `REFUSED_TOUR_PROVENANCE:MIXED_TOUR`.

## Root cause: cross-tour homonym mis-resolution (governed identity discipline working)

The eligibility manifest's test is *both players mapped to some governed identity*. The M1
manifest adds the stricter requirement the **per-tour affine calibration** needs: both players
must resolve to the **same tour namespace** (so a single ATP-or-WTA calibration and trustworthy
F2 ratings apply). The 5 markets fail that stricter test because one player's `surname+initial`
key (td-norm-v1) collides with an opposite-tour player of the same key — a homonym:

| market_id | cohort | player → resolved namespace |
|---|---|---|
| 1.258954329 | STRICT | "Brooke Anna Black" → **td-atp** (`Black B.`) · "Tereza Martincova" → td-wta |
| 1.258960086 | STRICT | "Viktorija Golubic" → td-wta · "Daniella Britton" → **td-atp** (`Britton D.`) |
| 1.259313230 | STRICT | "Oleksandra Oliynykova" → td-wta · "Sofia Johnson" → **td-atp** (`Johnson S.`) |
| 1.259341082 | STRICT | "Sofia Johnson" → **td-atp** (`Johnson S.`) · "Emiliana Arango" → td-wta |
| 1.259381241 | STRICT | "Julia Riera" → td-wta · "Daniella Britton" → **td-atp** (`Britton D.`) |

Each is a women's-singles market where one player (a female name) mis-matched a **male ATP**
player of the same surname+initial (`Black B.`, `Britton D.`, `Johnson S.`). Assigning such a
market a tour, an F2 rating, or a per-tour calibration would import a wrong identity. Refusing
them — and keeping them **visible** in the funnel as typed refusals (SPEC-038) — is the governed
identity discipline working, not a defect.

## Answers to the reconciliation checklist

- **Cause:** calibration availability — the per-tour affine calibration requires an unambiguous
  tour, which a cross-tour homonym cannot provide. **Not** market status, manifest version, or a
  manual edit.
- **No outcome used:** the resolution is purely name-based (td-norm-v1 over pre-June names +
  June runner names). No winner/settlement field was read.
- **No manual removal:** the 5 fall out mechanically from the tour-consistency rule in
  `scripts/june_m1_manifest.py`.
- **Defect?** No. It is a *stricter, more correct* rule than the eligibility manifest's
  both-mapped count. The frozen eligibility manifest is not edited (separate artefact, own
  digest, own purpose); these 5 are documented here as a newly-characterised cross-tour-homonym
  refusal class. (Note for Stage B: the same 5 should be excluded from the SPEC-032 development
  intersection derived from the M1 universe — carried forward as a typed exclusion, not a drop.)

## Final frozen prospective M1 counts

- **M1-valid total: 1,213** — ATP **592**, WTA **621**; strict **1,150**, primary-only **63**.
- Mixed/unknown-tour refusals: **5** (the table above).
- UTC calendar-day clusters: **30** (overall min 5 / median 36 / max 125; ATP 30 days, WTA 29).
- Prior-history cohorts (ATP/WTA): 1-4 223/197, 5-9 74/64, 10-19 59/74, 20+ 236/286.
- Manifest digest:
  `sha256:d192b4e3a3980fd3e2108a3efd68feb03d15e041a436569353178395f8b17b23`.
