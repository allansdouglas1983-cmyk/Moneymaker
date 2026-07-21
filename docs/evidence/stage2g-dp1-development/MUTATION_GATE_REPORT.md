# Stage 2G DP1 mutation gate report (SPEC-105/106/107) — FINAL

Modules: `sport_tennis/glicko2_family.py`, `sport_tennis/dp1_distribution.py`,
`sport_tennis/dp1_calibration.py`. cosmic-ray 8.4.6, targeted suite
`tests/{unit,properties}/sport_tennis`, 60s timeout.

## Final gate (after 6 kill rounds; one container restart survived, no data trusted across it)

| module | mutants | killed | survived | kill-rate |
|---|---|---|---|---|
| glicko2_family | 1234 | 1170 | 64 | 94.8% |
| dp1_distribution | 1068 | 948 | 120* | 88.8% |
| dp1_calibration | 573 | 542 | 31 | 94.4% |

*dp1_distribution survivors were classified in MUTATION_SURVIVOR_PACKET_V1.json
(round 3); its module is unchanged since. The glicko2_family and dp1_calibration
final survivors are in MUTATION_SURVIVOR_PACKET_FINAL_V2.json.

## Kill progression
- Round 1: golden quadrature reference, exact prediction reconstruction, volatility
  root-condition, boundary guards.
- Round 2: independent rate_player witness, exact pair reconstruction, bit-exact
  sigmoid-branch pins.
- Round 3: (dp1_distribution frozen here) documented equivalence classes.
- Round 4: initial_bracket pure seam (bit-identical, golden-grid-proven); first
  gate on dp1_calibration (86.0%).
- Round 5: calibration golden exact-fit pins (3 corpora) + MLE gradient-zero
  contract killed every Newton-step-internal mutant (80 -> 47).
- Round 6: calibration predicate-seam exact boundaries, n_rows=0, tour whitespace,
  keyword-only signature, horizon-both-sides (47 -> 31).

## Survivors: 95 (64 glicko2 + 31 calibration), 0 unexplained behavioural

Every survivor is classified into a mechanically-proven equivalence class with the
founder §3 field set (public-domain reachability, pure-seam behaviour, exact
volatility/fit output comparison, downstream rating/RD/probability/uncertainty
comparison, state/replay digest comparison, associated tests, proof digest,
`approved_by: null`). See MUTATION_SURVIVOR_PACKET_FINAL_V2.json.

NO survivor is approved. Per-ID founder adjudication is required before any entry
reaches `specs/mutation-survivors.yaml`.
