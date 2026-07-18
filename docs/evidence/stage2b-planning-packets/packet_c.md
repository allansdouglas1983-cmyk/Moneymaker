# Packet C — Reschedule dwell W × max-lead L evaluation (outcome-blind)

Policy semantics and constraints: see scripts/packet_c.py header. first-inPlay is a
POST-HOC diagnostic only. All rows deterministic replays of Stage-1 metadata.

## Cohort: primary

| W | L | avail % | abstain % | later-revision % (of decided) | re-arms (mean) | post-hoc lead min p10/med/p90 |
|--:|--:|--:|--:|--:|--:|--:|
| 15s | 5m | 89.1 | 10.9 | 82.4 | 4.85 | 9.59/26.59/142.77 |
| 15s | 10m | 92.8 | 7.2 | 87.0 | 3.64 | 16.38/51.98/151.59 |
| 15s | 15m | 94.7 | 5.3 | 87.3 | 3.43 | 21.58/56.55/158.14 |
| 30s | 5m | 89.0 | 11.0 | 82.4 | 4.86 | 9.56/26.62/141.08 |
| 30s | 10m | 92.8 | 7.2 | 87.0 | 3.64 | 16.25/51.96/151.5 |
| 30s | 15m | 94.7 | 5.3 | 87.3 | 3.43 | 21.58/56.44/157.13 |
| 60s | 5m | 88.6 | 11.4 | 82.4 | 4.86 | 9.5/26.72/143.06 |
| 60s | 10m | 92.7 | 7.3 | 87.0 | 3.64 | 16.22/51.92/151.5 |
| 60s | 15m | 94.6 | 5.4 | 87.2 | 3.43 | 21.61/56.44/157.13 |
| 120s | 5m | 87.9 | 12.1 | 82.3 | 4.88 | 9.24/26.72/143.55 |
| 120s | 10m | 92.4 | 7.6 | 87.0 | 3.65 | 16.03/51.98/151.59 |
| 120s | 15m | 94.4 | 5.6 | 87.3 | 3.43 | 21.58/56.57/158.14 |
| 300s | 5m | 81.8 | 18.2 | 83.3 | 5.01 | 9.37/31.2/148.67 |
| 300s | 10m | 90.2 | 9.8 | 87.2 | 3.68 | 16.44/53.89/154.03 |
| 300s | 15m | 92.5 | 7.5 | 87.5 | 3.46 | 22.22/58.37/159.38 |

## Cohort: strict

| W | L | avail % | abstain % | later-revision % (of decided) | re-arms (mean) | post-hoc lead min p10/med/p90 |
|--:|--:|--:|--:|--:|--:|--:|
| 15s | 5m | 86.8 | 13.2 | 77.3 | 5.28 | 9.09/21.69/148.14 |
| 15s | 10m | 91.3 | 8.7 | 83.4 | 3.85 | 17.61/54.73/159.55 |
| 15s | 15m | 93.7 | 6.3 | 83.8 | 3.77 | 22.24/58.9/165.06 |
| 30s | 5m | 86.7 | 13.3 | 77.3 | 5.28 | 9.09/21.69/147.13 |
| 30s | 10m | 91.3 | 8.7 | 83.4 | 3.85 | 17.61/54.73/159.45 |
| 30s | 15m | 93.7 | 6.3 | 83.8 | 3.78 | 22.24/58.89/164.88 |
| 60s | 5m | 86.5 | 13.5 | 77.4 | 5.28 | 9.03/21.72/147.13 |
| 60s | 10m | 91.3 | 8.7 | 83.4 | 3.85 | 17.62/54.93/159.45 |
| 60s | 15m | 93.6 | 6.4 | 83.8 | 3.78 | 22.22/58.88/164.88 |
| 120s | 5m | 86.2 | 13.8 | 77.4 | 5.29 | 8.96/21.69/148.14 |
| 120s | 10m | 90.9 | 9.1 | 83.5 | 3.86 | 17.61/55.54/159.55 |
| 120s | 15m | 93.3 | 6.7 | 83.9 | 3.78 | 22.24/59.08/164.88 |
| 300s | 5m | 81.3 | 18.7 | 78.9 | 5.32 | 9.25/26.89/154.88 |
| 300s | 10m | 88.4 | 11.6 | 83.7 | 3.9 | 18.19/57.73/160.75 |
| 300s | 15m | 91.0 | 9.0 | 84.1 | 3.81 | 22.83/60.89/166.58 |

## Findings (no W frozen here — founder declares)

1. **Dwell W is nearly irrelevant in 15–120 s** — availability, later-revision rate,
   re-arms and leads are indistinguishable across W∈{15,30,60,120}s; W=300 s only
   costs availability (−1–7 pts) for no reduction in later revisions. The revision
   process has no quiet threshold in this range to exploit.
2. **L dominates availability**: L=5m → ~89% / L=15m → ~95% (primary).
3. **Post-decision revisions are STRUCTURAL: ~82–88% of committed decisions see a
   later marketTime revision at every (W,L)** — schedule movement continues into the
   final nominal minutes, so no dwell prevents it. The real post-hoc lead to the off
   is a median ~27–57 min (p90 ~2.5 h) even when the nominal lead was ≤L.
4. Cohort differences (primary vs strict) are small; strict is not operationally
   easier.
5. **Live replicability / determinism**: every candidate uses only past observations
   and replays deterministically; all are governance-equal. The genuine open choice
   is therefore not W (any of 15–120 s is equivalent on this evidence) but the
   GOVERNED RESPONSE TO POST-DECISION REVISIONS — re-decide vs hold — which is an
   operational-policy question for the founder, to be decided outcome-blind.

Candidate policies returned: (W=60 s, L=10 m) and (W=60 s, L=15 m) as representative
mid-grid candidates; (W=15 s, L=5 m) as the minimal-lead variant. Not frozen.
