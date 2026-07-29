# TE-0029 — S8: what the weekly snapshot silently costs, and the one free fix it exposed

Harness `tennis_edge/experiments/s8_staleness.py`, committed with the delayed-observation
walk declared before the run: under lag mode the state serving a match uses only results
*observed* strictly before the lagged cutoff (decay still advanced to the true day), the
lag is part of the feature-cache key, and training stays day-fresh so the comparison
isolates the serving schedule, not the model fit. Same corpus (vintage-2026-07-26,
manifest sha256:dfbccd130eb3…), same folds, paired on identical rows.

## The primary (family 3, 98.75%)

| | penalty (nats) | CI | aligned |
|---|---|---|---|
| **Monday-snapshot vs day-fresh** | **+0.000879** | [+0.000510, +0.001227] — **clears** | 63,289 / 63,676 (fresh-only 387, lag-only 0) |

The Monday-schedule penalty is real and it is large in this programme's own currency:
+0.000879 nats is roughly **80% of the model's entire forecast edge over the exchange
anchor**. The site has been paying it every week.

## Dose-response (validity check: penalty must not shrink as lag grows)

| lag | penalty (nats) | CI 95% |
|---|---|---|
| 1 day | +0.000226 | [+0.000063, +0.000391] |
| 3 days | +0.000749 | [+0.000475, +0.001027] |
| 5 days | +0.000933 | [+0.000615, +0.001252] |
| 7 days | +0.001032 | [+0.000674, +0.001388] |

Monotone, every step clearing zero, no stale-beats-fresh anomaly anywhere. The harness is
measuring what it claims to measure.

## The registered switch rule cannot fire

The rule was: if the penalty clears and a faster cadence is available, switch. The
pre-check killed the second clause — **the provider publishes weekly**. There is no daily
feed to switch to at BASIC (and no paid feed will be bought). The penalty is therefore
recorded as what `state_stale_days` silently costs, on the record instead of invisible.

## The operational fix the provenance stamps license (not the switch rule)

The pre-check's `Last-Modified` stamps showed the season files land **Sunday ~20:37 UTC
(ATP) and Monday ~20:00 UTC (WTA)** — both *evenings*. The refresh ran **Monday 06:00
UTC**: it caught ATP's Sunday drop but missed WTA's Monday-evening drop by ~14 hours,
serving WTA a week stale — precisely the penalty measured above, self-inflicted for one
tour.

Fix applied: the Action moves to **Tuesday 06:00 UTC** and the two pg_cron pulls
(`tennis-pull-state`, `tennis-pull-results`) to **Tuesday 07:00/07:30 UTC**. Cadence
stays weekly, exactly as the provider's is; nothing is fetched more often, nothing new is
bought. This is scheduling alignment justified by measured publication times — it is not
the registered switch rule firing, and it changes no model, threshold or feature.

## Programme state

S8 closes the S-slices. TE-0017's remaining item is P4 (derivative-market precondition
check, computing).
