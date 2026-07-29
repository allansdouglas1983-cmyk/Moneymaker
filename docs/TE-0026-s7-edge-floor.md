# TE-0026 — S7: the edge floor holds up, and the edge is worth its face value

Harness `tennis_edge/experiments/s7_edge_floor.py`, pins frozen and committed before the
run. The gate compares each fired bet's point edge against the market's own Roll-implied
half-spread through the S6 frozen conversion — the threshold is the market's measured
cost, never a fitted constant.

## The gated reading (EXPLORATORY, as pre-registered — the label binds regardless)

| cohort | bets | ROI | 95% CI |
|---|---|---|---|
| ungated (standing policy) | 38,314 | +2.37% | [+0.94%, +3.70%] |
| edge above the market's own floor | 25,999 | +3.33% | [+1.47%, +5.32%] |
| edge below the floor (excised) | 10,470 | +0.55% | [−1.58%, +2.52%] |
| Roll-refused markets (typed exclusion) | 1,845 | −0.81% | [−6.53%, +5.06%] |

The registration expected the gated reading to span zero; it cleared. **The exploratory
label binds anyway** — this archive motivated the hypothesis, so the reading cannot
graduate itself; the confirmatory test is future data under this frozen spec, and any
live minimum-edge buffer remains a founder decision (§2.12). The excised cohort earning
roughly nothing is the structurally expected picture: bets thinner than the price's own
noise are noise. The refused cohort (positive autocovariance — trending markets, where
the gate is structurally blind) is disclosed at 1,845 bets, wide and unresolved; the
cross-tab shows refusals concentrate in SILENT markets (820 of 5,253) exactly as the
blindness warning predicted.

## The monotonicity diagnostic — the surprise worth having

Deciled by predicted edge, returns rise nearly monotonically from the bottom decile to
the top (+2.4%, −2.2%, +1.6%, +1.2%, +1.2%, +3.4%, +2.3%, +4.4%, +4.7%, +4.9%). The
per-bet slope of net return on predicted edge is **+1.168 [+0.419, +1.873]**,
day-clustered.

- The pre-declared equivalence claim ("edge magnitude carries no selection value") is
  **not licensed** — the interval excludes nothing below 0.5 from above; it excludes
  ZERO from below.
- Read plainly: a calibrated edge has slope 1, and 1 sits comfortably inside the
  interval. The model's claimed edges are being paid at roughly face value on this
  archive — the strongest calibration-in-money evidence in the record, and precisely the
  property a future minimum-edge policy would need. It is archive evidence, subject to
  the same hypothetical-fill and cost-band caveats as every money number (TE-0020
  applies to every row).

## Standing

The gate spec is frozen as evidence for a future founder decision. Nothing changes on
the live path; the site's MIN_EDGE display thresholds are untouched.
