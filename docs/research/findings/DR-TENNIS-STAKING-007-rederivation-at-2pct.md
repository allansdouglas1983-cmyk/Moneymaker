# DR-TENNIS-STAKING-007 — the 003/004/005 chain re-derived at the corrected 2% commission

**Status:** ASSESSED. **Date:** 2026-07-30. **Type:** internal re-derivation of the deep-research
corpus's arithmetic at a corrected premise — the move DR-005 itself models. Founder-directed
("Accept proposals build it properly no shortcuts", 2026-07-30, accepting the 2-then-3 sequence).
**Reproducible:** `tennis-edge/tools/rederive_staking_at_2pct.py` — the script must reproduce
DR-005's published @5% table exactly before it emits the @2% column, and does.

## Why this document exists

DR-003 (the completed 105-agent run) recommended adopting **no** edge-consuming staking rule,
explicitly conditionally: *"while the edge interval spans zero."* DR-004 concluded *"the bank,
not the algorithm, is the binding constraint."* Both computed every number at **5% commission**
— the TE-0042 error the founder attested was wrong on the day it was written (TE-0044
Correction). This document re-runs their own chain (KL → δ → commission → EV/b, DR-004's,
unchanged) at the real 2% rate and re-checks DR-003's condition against the measured
day-clustered intervals in TE-0043's raw sweep. Nothing else is altered; no new premise is
introduced.

## Result 1 — the expressibility conclusion of DR-004/005 reverses at 2%

Same chain, validated against DR-005's table first (5 of 5 rows exact):

| odds | ROI @2% | full Kelly | full expressible from | half from | quarter from |
|---|---|---|---|---|---|
| 1.30 | +1.95% | 6.64% | £15.05 | £30.11 | £60.22 |
| 1.50 | +2.46% | 5.02% | £19.94 | £39.88 | £79.76 |
| 2.00 | +3.43% | 3.50% | £28.60 | £57.20 | £114.40 |
| 3.00 | +4.94% | 2.52% | £39.69 | £79.37 | £158.75 |
| 5.00 | +7.30% | 1.86% | £53.72 | £107.43 | £214.87 |

At 5%, DR-005's uncomfortable position was that the only expressible variant on £100 was the
one the evidence most condemns (full Kelly), with the supported shrunk forms needing
£102–£511. At 2% that inverts: **conservatively shrunk allocations are expressible on a
£100–£200 bank across the whole traded price range.** DR-004's "below roughly £400 no
allocation rule can express itself" was an artefact of the wrong commission rate.

## Result 2 — DR-003's condition is discharged on the supported reading

DR-003's recommendation was conditional on the edge interval spanning zero. The measured
day-clustered CI95s (TE-0043 raw sweep, model source, supported fills, 2%):

| min_edge | ROI | CI95 | bets |
|---|---|---|---|
| 0.00 | +2.32% | [+0.62%, +4.06%] | 25,174 |
| 0.01 | +3.22% | [+1.31%, +5.20%] | 16,563 |
| **0.02** | **+3.86%** | **[+1.37%, +6.29%]** | **9,793** |
| 0.03 | +4.10% | [+0.89%, +7.38%] | 5,474 |
| 0.04 | +5.03% | [+0.72%, +9.44%] | 2,862 |

The lower bound is positive at every threshold from 0.00 to 0.04. **The condition "while the
edge interval spans zero" no longer holds on the supported-fills reading at the attested
rate.** The market control is simultaneously significantly negative (−1.59% [−2.73, −0.37]),
so the interval that cleared belongs to the forecast, not to a venue-disagreement artefact.

## What is NOT discharged, stated as prominently as what is

- **Realised fills.** SUPPORTED means the market later traded at that price or better —
  no fill is proven (TE-0043's own caveat). The after-real-execution edge is what the
  ADR 0020 manual trial measures; no historical reading can.
- **SPEC-081.** The 2% rate is founder-attested account state, still `ASSUMPTION` until read
  off a settled market's statement (task #89).
- **Design-level selection.** The walk-forward is honest but the feature set saw the corpus
  (TE-0043 "what this does NOT establish"). The untouched May–Jul 2026 window is
  directionally consistent and underpowered.

## What follows — the corpus's own next step, not a new invention

With the condition discharged on the supported reading, the matrix's own gate ("Group D
enters… gated on the edge test resolving") opens for exactly one honestly-conservative form
it names: **D7 K-LCB — "Kelly at pre-declared conservative quantile of p… the honest 'not
yet' rule"** — which consumes the *lower bound* of the measured interval, refuses by
construction the moment that bound touches zero, and therefore carries DR-003's warning
("no shrinkage factor is protective" against a mis-signed edge) inside itself: if the sign
reverts to undecided, D7 stakes nothing. At the operative threshold the conservative
displacement is **Δe = 3.86% − 1.37% = 2.49pp = 0.0249 per unit stake** (provenance:
TE-0043 raw sweep, line "min_edge 0.02 … CI95 [+1.37%, +6.29%]").

Registration of the D7 arm — exact formula, same-day joint treatment per matrix §4,
drawdown bound, and its harness run — is a separate pre-registered document
(TE-0047), frozen before any replay output, per STK-HARNESS-V1 discipline.

## Ledger

No SPEC-ID changes. No gate evaluated. No stake authorised by this document. DR-003's
recommendation stands wherever its condition holds; this document records that its condition
no longer holds on the supported reading at the attested commission, and hands the next step
to the pre-registered TE-0047.
