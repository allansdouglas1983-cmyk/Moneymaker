# Stage 2E — frozen June M1 prediction bundle (OUTCOME-BLIND)

The frozen, outcome-blind inputs the Stage-A burn will score. **No June outcome is in this
bundle.** One row per market for the 1,213 governed calibrated-F2-valid June singles.

- `JUNE_M1_PREDICTION_BUNDLE.jsonl` — per market: `market_id, tour, cohort, prior_band,
  cluster_day, competitor_designated, competitor_other, selection_id_designated,
  selection_id_other, p_raw_designated, p_cal_designated`. **No winner/status/settled/result
  field of any kind.** Sorted by `market_id`.
- Digest (file bytes): `sha256:37e43f64a65fd89ac3ba03263f224f2c23acb9ee5a93f995367a951bc2906347`.

## How it was built (outcome-blind)

- **F2:** per-tour global Elo over ALL Tennis-Data pre-June completed matches (Date <
  2026-06-01), same-day batch update at the frozen 2026-fold `k_global` (ATP 24, WTA 24),
  cold-start 1500.0. `p_raw_designated = elo_win_probability(rating_designated, rating_other)`.
- **Calibration:** frozen affine (calibration-policy-v2) per tour — ATP intercept 0.025399 /
  temperature 1.218638; WTA intercept 0.029204 / temperature 1.150681.
- **Identity:** the governed `td-norm-v1` bridge with the same universe-filtered inputs as the
  eligibility build, so tour tags reproduce the frozen M1 manifest (`manifest_tour_match: true`).
  Designated = the lower governed CompetitorId string.
- **Selection ids:** read only from each June market's FIRST pre-off `status=="OPEN"`
  marketDefinition (`id` + `name`). CLOSED definitions, runner WINNER/LOSER status, and
  `settledTime` were never read.

## Verification (independently re-checked, not trusted from the builder)

- **Outcome-blind:** the bundle bytes contain no `winner/loser/status/settled/result/score/pnl`
  token; the field set is exactly the 11 above.
- **Counts:** 1,213 rows; ATP 592, WTA 621 — matches the M1 transfer manifest exactly; 0
  missing streams, 0 missing selection joins, 0 exclusions.
- **Structure:** every `p_raw`/`p_cal` ∈ (0,1); the two selection ids and the two competitor ids
  differ; designated < other for all rows; every row is an `ELIGIBLE_F2` manifest market.
- **The 5 mixed-tour homonym markets stay refused** (absent from the bundle) — not repaired or
  remapped.
- **Scoring-ready & deterministic:** the real bundle flows through the governed join +
  `m1_scorecard` under synthetic winners, both tours supported (≥500), byte-identical across
  reshuffles (`tests/unit/l8/test_june_stage_a_driver.py`).

The bundle is the frozen input to `l8_evidence.june_stage_a_driver` / the atomic burn; scoring
runs from the immutable outcome artifact, never by reopening the raw lockbox.
