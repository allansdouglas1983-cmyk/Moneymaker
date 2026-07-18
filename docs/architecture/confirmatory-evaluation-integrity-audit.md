# Confirmatory-evaluation integrity audit (Stage 2B §1 — before any F3 scoring)

**Status:** FROZEN 2026-07-18. Outcome-blind (match counts only; NO F3-vs-F2 score
computed). Founder directive: before relying on the 34,046 count, audit the design.

## The contamination the audit confronts

F2's single K (ATP 24 / WTA 32) was selected on **OOF-window performance**
(2019-01..2025-05). Therefore those OOF observations are **not automatically untouched
confirmatory evidence**: a comparison that reused the reported single-K F2 predictions
would let F2's own tuning data score the confirmatory trial. Two honest designs remove
this, per the founder's options.

## Honest confirmatory counts (eligible = completed, both-identity-resolved, deduped)

Per-year eligible matches, 2019-01..2026-05 (the post-warm-up span):

| Year | ATP | WTA | Total |
|---|--:|--:|--:|
| 2019 | 2,512 | 2,343 | 4,855 |
| 2020 | 1,236 | 1,032 | 2,268 |
| 2021 | 2,408 | 2,338 | 4,746 |
| 2022 | 2,546 | 2,252 | 4,798 |
| 2023 | 2,616 | 2,400 | 5,016 |
| 2024 | 2,634 | 2,418 | 5,052 |
| 2025 | 2,490 | 2,376 | 4,866 |
| 2026 (Jan–May) | 1,244 | 1,193 | 2,437 |
| **Total** | **17,686** | **16,352** | **34,038** |

Required N at δ=0.0007, σ_d=0.04075 (planning), power 0.80, α=0.025 (two-sided): **32,212**.

## The three candidate designs and their honest power

| Design | Confirmatory-eligible | ATP / WTA | ≥ 32,212? | Verdict |
|---|--:|--:|:--:|---|
| **A. Nested (full)** — warm-up ≤2018 selects K/params for the 2019 outer block; each later outer block re-selects on its own past | **34,038** | 17,686 / 16,352 | **YES** (+1,826) | powered at planning σ_d |
| A′. Nested (drop 2019) — 2019 as pure initial-selection block | 29,183 | 15,174 / 14,009 | NO (−3,029) | underpowered |
| B. Validation-only untouched holdout (2025-06..2026-05) | 4,935 | 2,521 / 2,414 | NO | grossly underpowered |

## Registered design: **A (full nested chronological cross-fitting)**

Chosen because it is the founder's preferred option AND the only one that reaches power.
It is legitimate because the reported single-K is **never used**: each outer block's
confirmatory prediction (for both F2 and F3) uses hyperparameters selected **only on that
block's past**, so no outer-evaluation outcome selects its own model.

Protocol (frozen; executed only after all Stage-2B reviews land):

- **Outer folds** = calendar years 2019, 2020, …, 2026(Jan–May). Warm-up ≤2018 feeds
  ratings and the FIRST outer block's inner selection.
- For each outer block Y: F2's K and F3's (K_global, K_surface) are chosen by inner
  minimisation of mean log loss on data strictly **before** Y (warm-up + years < Y);
  ratings are built from all data before Y; both families emit exactly **one** prediction
  per eligible match in Y.
- Every prediction carries outer-block + inner-selection provenance (which years chose
  its K, the selected values, the training-through date).
- Endpoint: paired per-match log-score difference `d_m = −ln p_F2(winner) + ln p_F3(winner)`,
  aggregated by **UTC-day block bootstrap** (SPEC-090) for the 97.5% CI.

## Exact separation of observation roles

- **Development / tuning (already spent):** the OOF window 2019-01..2025-05 under the
  single-global-K analysis — this is the M1 *adequacy* evidence for F2, NOT confirmatory.
- **Confirmatory (this trial):** all 34,038 matches 2019-01..2026-05, each predicted under
  the nested protocol whose selection never saw that match's outcome. No development OOF
  rows are combined with a holdout to reach N — the entire set is regenerated under the
  leakage-safe nested protocol (the founder's explicit prohibition is respected).
- **Sealed:** June 2026 (M2, separate trial) — untouched here.

## Power statement (honest)

At the **frozen planning** σ_d = 0.04075, design A (34,038) is adequately powered
(+1,826 over 32,212). The realised σ_d of the F2-vs-F3 paired difference is unknown and
may differ; two similar Elo models plausibly have a *smaller* paired σ_d (tighter → more
power), but this is not asserted. If the realised anytime-valid Cit is wide, the trial
returns **CONTINUE / INCONCLUSIVE** — δ is never weakened and no data is bought to reach N.
