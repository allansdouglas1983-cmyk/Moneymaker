# TE-0023 — S4: the coverage gate measured; every declared prediction held

The frozen predicate (both players carry a pyramid record — concretely, the builder
emitted the pyramid block) split the v3-priced out-of-sample rows 38,584 covered / 6,402
uncovered. Harness `tennis_edge/experiments/s4_coverage_gate.py`, committed with every
reading declared before the run.

## The binding denominator

**13.8% of fired bets** (5,304 of 38,314) land on uncovered rows — reported over fired
bets as the amendment requires, and materially close to the row share here (14.2%).

## The readings

| cohort | reading | bets | ROI | 95% CI |
|---|---|---|---|---|
| ungated | supported only | 25,250 | +2.57% | [+0.91%, +4.33%] |
| **gated (predicate true)** | supported only | 21,996 | **+3.37%** | [+1.52%, +5.21%] |
| uncovered | supported only | 3,254 | −2.83% | [−7.48%, +1.95%] |
| uncovered | all fills | 5,304 | −0.68% | [−4.66%, +2.85%] |
| uncovered control | all fills | 5,024 | −1.49% | [−4.05%, +1.19%] |

The gated reading is a **policy refinement of seen data, labelled as such** — excising a
negative-expectation cohort predictably pushes the same sample up (+2.57% → +3.37%
supported-only) and is not new evidence. TE-0020's execution-cost band applies to every
row here; no gated number is quotable without it.

## The declared predictions, checked

- **The uncovered cohort does not earn.** Model −2.83%/−0.68%, spanning zero — the
  suspected-bug trigger (money edge living where the forecast edge is not) did not fire.
- **Consistency (a) holds:** uncovered model ≈ uncovered control (−0.68% vs −1.49%) —
  both are estimation noise around the market minus commission, as the structural
  identity says they must be.
- **Consistency (b) holds on the 22-feature model:** forecast gain over the market is
  +0.001131 nats [+0.000553, +0.001708] on covered rows and **−0.000142
  [−0.001219, +0.001006] on uncovered rows** — the model still has no measurable forecast
  edge where the predicate says it knows nothing. The published +0.000000 was the
  10-feature fit; the 22-feature result is reported either way, as required, and it says
  the same thing.

## Standing policy

The gate is frozen exactly as registered: refuse the fired bet when either player lacks a
pyramid record. Its justification is the structural zero-information identity, not the
money split above. It stands as a **declared secondary policy for future prospective
data**; adoption on any live path additionally requires founder approval (TE-0017 §2.12).
Removing a zero-information cohort also mechanically lowers the n\* the money question
needs — fewer noise bets diluting the same signal.
