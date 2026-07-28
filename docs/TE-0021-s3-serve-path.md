# TE-0021 — S3 measured: the serve-path defect was costing a third of the model's edge

TE-0017 S3 registered the fix and the three measurement arms before any number existed;
the fix deployed on its own justification (it restores the model that was actually
measured) and none of these arms gated it. Identical rows (63,676 out-of-sample matches),
day-clustered bootstrap; arms (a) and (a′) share a Bonferroni family and read at 97.5%.

| arm | estimand | gain (nats) | CI 97.5% | verdict |
|---|---|---|---|---|
| (a′) | **fixed deployed artifact, rank_gap present vs withheld — the exact serve-path term** | **+0.000365** | **[+0.000089, +0.000653]** | **clears zero** |
| (a) | paired walk-forward refit, 22 vs 21 features | +0.000106 | [−0.000097, +0.000304] | spans zero |

**Arm (a′) is the number the site was paying.** Every served prediction scored the
22-coefficient model with `rank_gap` absent — 63,673 of 63,676 rows (100.0%) differ
between the two paths — and the forecast cost of that, at fixed coefficients, is
+0.000365 nats: roughly a third of the model's whole measured edge over the closing
price (+0.001064). The fix (live since the version-4 function deploy, ranked state
pulled) recovers it.

**Arm (a) is why the damage hid.** Refit without the feature, correlated features absorb
most of its work — the marginal refit value is small and unresolved. The forfeiture lived
in the *coefficient mismatch*, not in the feature's unique information: coefficients
fitted jointly with a feature, served without it, are miscalibrated everywhere, which is
exactly the train/serve mismatch class TE-0011 refused to deploy over. Per the
registration, the ~0 refit reading is recorded and `rank_gap`'s retention is re-measured
at the next refit — not dropped now, and nothing tuned against this run.

**Arm (b) validates the served fallback.** The snapshot serves each player's
latest-prior-match rank; against the fixture-time corpus rank over 212,608 comparisons:

| rank staleness | share | \|log1p error\| median | p90 |
|---|---|---|---|
| ≤ 7 days | 64.5% | 0.0000 | 0.0488 |
| ≤ 28 days | 23.6% | 0.0488 | 0.2066 |
| ≤ 90 days | 7.5% | 0.0870 | 0.3102 |
| > 90 days | 4.5% | 0.2084 | 0.7943 |

Fresh ranks — the overwhelming mass — are essentially exact. The stale tail (>90d) is
where protected-ranking and injury-return cases live; `rank_date` travels with the state
precisely so that staleness is visible at serve time rather than silent. No
stale-beats-fresh anomaly appeared; the error is monotone in staleness, as it must be.

**Deployment state.** Python `live_state` + TypeScript `scoring.ts` serve `rank_gap` on
every prediction with the training-time `or 500` imputation reproduced exactly; 500 golden
vectors agree to 1e-12 across every rank source (caller, snapshot, half-imputed, both
imputed); `tennis.player_state` carries rank + rank_date for 2,893 of 2,954 players; the
ledger and site now score the same nominal model identically. Harness:
`tennis_edge/experiments/s3_rank_gap.py`.
