# Stage-2B F0 + F2 run evidence — FROZEN 2026-07-18

F0 (June market yardstick, EXP context: registration-free yardstick; policy
COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE W=60s L=300s; info-price-v2): one immutable
snapshot per committed decision over the 2,876-market June universe. 2,518 committed
(1,959 strict), refusals typed (332 NO_VALID_COMMIT_WINDOW, 26 NO_TWO_SIDED_BOOK),
2,078 committed markets saw post-commit revisions (held, never re-decided). No winner,
settlement, P&L or CLV read; June outcomes sealed throughout.

F2 (EXP-STAGE2-F2-GLOBAL-ELO-001, Design B, via l4_pricing.crossfit with the additive
warm-up threshold): label-policy-v1 completed-only, td-norm-v1 identities, no odds
columns read. K grid {16,24,32} on OOF only; selected ATP K=24 / WTA K=32.
OOF (2019-01..2025-05): ATP n=15,165 ll=0.62645 Brier=0.21887 slope=0.833;
WTA n=13,938 ll=0.62123 Brier=0.21645 slope=0.853. Prequential validation
(2025-06..2026-05): ATP n=2,521 ll=0.6256; WTA n=2,414 ll=0.6199 (no temporal
degradation). Structural-null reference: ln 2 = 0.69315. Full exclusion funnels,
cold-start bands, per-year K stability and reliability tables in
F2_EVALUATION_REPORT.json. No June row; no market-relative claim (no Betfair
baseline exists pre-June).
