# F2/F3 chronological design — candidates, selection, power accounting (2026-07-18)

Outcome-blind (metadata + identity coverage only; label-policy-v1 completed-only rows).
Full numbers: `docs/evidence/tennis-data-2026-07-18/CANDIDATE_DESIGNS.json`.

| | Design A | Design B (SELECTED) |
|---|---|---|
| Warm-up (ratings only, unscored) | ≤2020-12-31 (86,032 matches) | ≤2018-12-31 (78,904) |
| Development / chronological OOF | 2021-01→2025-08 (23,572) | 2019-01→2025-05 (29,111) |
| Final pre-June validation | 2025-09→2026-05 (3,346) | 2025-06→2026-05 (4,935; full season cycle, all surfaces) |
| Evaluation total (OOF+validation) | 26,918 | **34,046** |
| Power vs declared (δ=0.0007, σ_d=0.04075, 0.80) | adequate @ α=0.05 single (26,600); NOT @ 0.05/6 (41,039) | adequate @ α=0.05 single; NOT @ 0.05/6 |

**Selection: Design B**, because (a) 7,100 more evaluation observations against a
declared requirement neither design fully meets at the 6-comparison allocation — power
is the scarce resource; (b) its validation block is a full June→May season cycle (every
surface represented; A's Sep→May block has no grass); (c) warm-up remains deep (79k
matches). **Recorded trade-off:** B's development window contains the 2020 COVID
disruption (regime anomaly inside OOF — reported by period cohort, never silently
smoothed); A avoided it at the cost of power and seasonal balance.

**Honest power statement:** both designs support single-comparison evaluation at the
declared constants; NEITHER reaches the 41,039 required under the full 6-family α
allocation. Consequence (pre-stated, not negotiable later): the programme spends its
family-wise budget on FEW comparisons — F2-vs-null and combined-vs-market first — or
accepts CONTINUE/INCONCLUSIVE at the declared δ for later families. No data is bought
for volume; June remains an external replication/veto block, never asserted as
independently powered (its F2-eligible count is 1,218).

June F3 emission is blocked separately: `JUNE_SURFACE_SOURCE_MISSING` — F3 develops and
validates pre-June on Tennis-Data's own surface field, but emitting for June markets
requires a governed June-tournament-surface source (a future, founder-approved
addition; never inferred silently from event names).

This design binds at the F2 trial registration; changing it afterwards is a new
registration with multiplicity consequences.
