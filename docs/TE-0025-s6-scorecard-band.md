# TE-0025 — S6 closed: the site grades itself, and every edge wears its cost band

Both halves of the registered slice shipped and are live.

## The band (P2's table reaches the user)

Every displayed edge is now a range: ``[edge − band, edge]``, where the band is the rise
in commission-aware break-even at half the frozen Roll spread for the prediction's
liquidity stratum. The frozen table (provenance 2026-07-28, measured over 46,169 markets
with a Roll estimate, 5.0% refusals excluded rather than imputed):

| stratum (S5 staleness band) | relative spread (p75) |
|---|---|
| <60s | 4.25% |
| 60–600s | 4.79% |
| >600s | 5.48% |
| **unknown stratum (pooled p90)** | **7.79%** |

A manually entered price carries no age, so it always takes the pooled conservative
fallback — the table is constructed so unknown costs more than every knowable stratum,
and the display can never reward not looking. The conversion is deterministic and
golden-vectored across every stratum in both languages, including the cap the vector
generator itself uncovered: at short odds the cost can swallow the whole price, and the
band honestly becomes everything above break-even rather than an error.

**The DR-mandated TE-0014 restatement:** TE-0020's banded standing statement (+2.63%
uncosted / +1.25% central / −0.09% pessimistic, supported-only) is the operative
restatement of every prior money table, TE-0014's included; the frozen display table now
serves the same standard on every live prediction. The pending item is closed.

## The scorecard (the serving path finally graded)

The predictions table was write-only; now the loop closes without a credential anywhere:

1. The weekly Action exports recent corpus results (120-day window; 1,774 rows first run)
   with grade keys precomputed by `tennis_edge/scorecard.py` — plus an **alias table** of
   every name form reducing to a window key, so the database grades by exact string
   lookup and **no name logic exists in SQL**. Ambiguous aliases are neutralised, never
   guessed. The one reducer lives in Python; there is no port to drift.
2. pg_cron pulls the file Mondays 07:30 and runs `tennis.grade_ledger()`: the **declared
   vintage policy** (last prediction created on or before the match date; post-match rows
   never grade) joins through the aliases and **appends** settled rows — predictions are
   never mutated, and `on conflict do nothing` makes replay idempotent.
3. `/scorecard` + the page's Ledger tab show the denominator whole: matches predicted,
   graded, awaiting results, **unmatched names as a visible typed count** (the
   double-surname tail lands there, never silently absent), post-match rows excluded.
   Paired day-clustered model-vs-market log loss with a deterministic seeded bootstrap
   interval — and **no interval at all below five match days**, rather than a misleading
   one.

**Non-gating by construction, and it says so on the page:** the scorecard feeds nothing
served — not MIN_EDGE, not the staleness thresholds, not the model — a single user's
volume can gate nothing, and its number is never comparable to the 63,676-match research
intervals. Any future formal halt rule must meet the SPEC-096 anytime-valid standard.

**Replay proof, on the record:** a labelled synthetic pre-match prediction on a real
completed match graded exactly (winner through the alias join; log losses equal to
−ln 0.60 and −ln 0.53 to the digit; the prediction row untouched); the labelled rows were
then removed and a second `grade_ledger()` appended nothing. Reference logic pinned by 14
unit tests (744 total green).

## Standing state

Function version 6 live; page deployed with the band display and scorecard section; cron:
state pull Mondays 07:00, results pull + grading 07:30. The scorecard fills as
predictions are entered and matches complete. Remaining in the frozen TE-0017 order:
S2 (delay-cost curve), S7 (edge-floor diagnostic), S8 (cadence), S9 (anchor temperature),
then P4 (coherence probe) last.
