# TE-0040 — the configuration the site actually serves, scored for the first time

The residual model's coefficients were fitted with the **Bet365** power-de-vigged price as
the unpenalised offset (`residual_features.py`: `PRICING_BOOK = "b365"`, `DEVIG = POWER`).
Two of its 22 features — `elo_residual` and `point_model_residual` — are defined as
`logit(estimate) − market_logit`, so they carry that same anchor *inside* them.

The site serves neither. `scoring.ts::priceFixture` anchors to the **Betfair back/back
pair**, and `liveFeatures` computes the two residual features against that anchor.

**That configuration had never been scored.** The exchange-anchor harness swaps the offset
but not the features, and stops one step short of the served combination. This closes it.

## The input gap is the size of the model's entire output

| quantity | median | p75 | p90 | p99 |
|---|---|---|---|---|
| \|b365 anchor − exchange anchor\| | **0.0672** | 0.1178 | 0.1758 | 0.4211 |
| model's own \|correction\| (60,000 cached rows) | **0.0689** | 0.1218 | 0.1815 | 0.3142 |

Read those two rows together. **The difference between the market probability the model was
fitted against and the one the site serves against is the same size as the entire
correction the 22-feature model applies.** Not a rounding term — the whole model, twice over
at the tail.

A related check, worth recording because it corrects an assumption: swapping the *method*
on the same exchange book (power versus proportional) moves the anchor by a median of only
**0.0032** logits. **The venue dominates the method by roughly twenty to one.** The
interesting question was never power-vs-proportional; it was Bet365-vs-Betfair.

## What that gap does to the output: much less than you would fear

`tools/served_anchor_check.py`, 25,268 rows joined to exchange prices across 1,880 days.
Both configurations scored against the **same** exchange baseline, so the comparison isolates
the anchor.

```
log-score gain over the exchange baseline
  as MEASURED  (b365 offset, b365-anchored features)      +0.000469 nats
  as SERVED    (exchange offset, re-anchored features)    +0.001008 nats

  SERVED minus MEASURED, day-clustered:  +0.000539 nats  CI95 [-0.000055, +0.001121]
                                                          SPANS ZERO
  |p_measured - p_served|:  median 0.0128   p90 0.0315   p99 0.0517
```

Re-anchoring needs no feature rebuild. Both anchored features have the form
`logit(estimate) − market_logit`, so replacing the anchor is exact addition:
`feature_exchange = feature_b365 + (anchor_b365 − anchor_exchange)`.

## Verdict: no harm found, favourable direction, nothing established

**The served configuration is not degraded.** Its point estimate is *better* than the
as-measured configuration, which is the direction you would expect — anchoring to the venue
you actually bet at should beat anchoring to a bookmaker you cannot use. The served figure
of +0.001008 nats also sits close to the project's standing +0.001064, which is a
consistency check that passes.

**But the difference spans zero, so the improvement is not established**, and two
limitations must travel with these numbers:

1. **Neither level is out-of-fold.** The v3 coefficients were fitted on these rows
   (`trained_rows: 96,052`, `trained_through: 2026-07-19`). Both configurations carry that
   contamination equally, which is why the *difference* is the reportable quantity and the
   levels are context only. A level from this table must never be quoted as an edge.
2. **This is a restatement of one frozen model under two anchors**, not a new fit. It says
   what the existing coefficients do when the anchor moves. It does not say what
   coefficients fitted against the exchange anchor from the start would do.

## The part that does matter operationally

`|p_measured − p_served|` has a median of **0.0128** — 1.3 probability points, with a p90 of
3.2. `MIN_EDGE` is 0.02. So while the aggregate score barely moves, **individual bets flip**:
a marginal fixture near the firing threshold can land on either side of it depending on
which anchor is used. The aggregate being safe does not make the per-bet selection stable.

## What this does NOT license

No rule change, no refit, no threshold change, no claim of improvement. The served
configuration is now *scored* rather than *unscored*, which was the whole point. If the
exchange anchor is ever to be adopted as the fitting anchor rather than merely the serving
one, that is a new model version with its own out-of-fold walk-forward and its own gate
evaluation — not a consequence of this table.

## Provenance

`tools/served_anchor_check.py`, seed 20260730, 2,000 day-clustered draws, corpus
vintage-2026-07-26, model `sha256:458574037e863122…`. Deterministic and re-runnable.

Originated from the profit audit's items 14 and 15, which identified the gap qualitatively;
this measures it. The audit's emphasis on de-vig *method* turned out to be the smaller half
of the story, which is recorded above rather than quietly dropped.
