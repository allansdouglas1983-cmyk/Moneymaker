# TE-0019 — The eleven-year verdicts: money clears the strict bar; the re-anchor does not deploy

The merged archive (2015-05-01 → 2026-05-12, 354,487 singles markets after market-id dedup,
47,818 corpus matches priced at T-600s with fill evidence attached) closed the coverage gap
that has qualified every prior conclusion. Both frozen harnesses were re-run unchanged —
only the price-table path moved to `exchange_prices_600s_v2.jsonl`. All numbers are
hypothetical returns under the trade-through execution rule (DR-TENNIS-MICROSTRUCTURE-001
standard); nothing here is a realised return.

## Verdict 1 — the strict money reading clears zero for the first time

44,291 of 63,676 out-of-sample matches carried an exchange price. Flat 1 unit at the
commission-aware break-even, day-clustered bootstrap, 2,000 draws:

| reading | bets | ROI | 95% CI | verdict |
|---|---|---|---|---|
| **supported fills only** | **24,886** | **+2.63%** | **[+0.94%, +4.29%]** | **clears zero** |
| all fills credited | 37,738 | +2.38% | [+0.97%, +3.82%] | clears zero |
| control, all fills | 34,922 | −1.33% | [−2.49%, −0.12%] | below zero |
| control, supported only | 23,654 | −1.45% | [−2.85%, +0.07%] | spans zero |

At 13,526 bets this reading missed clearing by 0.11%; at 24,886 the lower bound is +0.94%.
The control losing at the same prices attributes the edge to the forecast, not to price
selection.

The falsification machinery paid for itself in the decomposition: **unsupported** fills —
the ones a conventional backtest silently invents — show +4.56% [+1.49%, +7.49%], the
best-looking cell on the page and precisely the least real one (a price that runs away
unmatched was always the best "value"). **No-evidence** (silent markets): −2.02%, flat.
Strata: thin +2.77%, moderate +4.00%; evidence split over fired bets 65.9% / 20.4% / 13.7%.

Still owed on this result before it is quoted anywhere customer-shaped: the Roll-family
execution-cost band (tooling built, application pending) and the AU-events commission
caveat, both per the microstructure standard. *(Settled: the band is TE-0020, and the
supported-only reading does not clear zero at the central cost assumption. TE-0020's
standing money statement supersedes this section's headline whenever the two are read
together.)*

## Verdict 2 — the deployment gate FAILS; the site keeps the b365-anchored model

| comparison | gain (nats) | 95% CI | verdict |
|---|---|---|---|
| bare exchange T-600s over bare b365 close | +0.000430 | [−0.000021, +0.000864] | spans zero |
| features over bare b365 | +0.000959 | [+0.000353, +0.001584] | clears zero |
| features over bare exchange | +0.000972 | [+0.000406, +0.001529] | clears zero |
| decision row (like-for-like anchors) | +0.000443 | [+0.000041, +0.000832] | clears zero |
| **deployment row (re-anchored 24k-train vs deployed 90k-train)** | **+0.000326** | **[−0.000165, +0.000826]** | **spans zero — NO DEPLOY** |

This is exactly what the verification existed to test, and the pre-registered rule gives
the answer without negotiation. On 2015–2022 alone the deployment row cleared
(+0.000812 [+0.000042, +0.001570]); with 2023–2026 included the advantage roughly halves
and the interval spans zero. The "assumed stable to 2026" caveat recorded in TE-0015 was
tested and **did not hold at the bar**. Like-for-like, the exchange anchor remains better
(decision row clears) — but like-for-like is not what deployment is: deployment trades the
sharper anchor against a 3.7× smaller training set, and on recent seasons that trade no
longer wins convincingly.

Consequences, in the frozen order:
1. The site continues to serve the Bet365-anchored 22-feature fit. No model change ships
   from this run.
2. The attenuation itself is informative and goes on the record: the bare-anchor gap also
   shrank (+0.000781 → +0.000430, now spanning zero), i.e. the relative sharpness of the
   T-600s exchange price versus the later b365 close is weaker in 2023–2026 than in
   2015–2022. Composition shift (the tail's tier mix) and genuine market sharpening are
   both candidates; distinguishing them is a diagnostic, not a licence to refit.
3. Re-litigating the gate with a different training scheme (e.g. mixed-offset training) is
   permitted only as its own pre-registered slice. Nothing is tuned against this result.

## What stands after both verdicts

The forecast result is untouched (+0.001058 nats over the close). The money question, at
the strictest reading the data supports, now clears zero on eleven years against a losing
control — hypothetical, banded, and honest. The deployed model stays exactly as measured
and served. The discipline that blocked a flattering deployment is the same one that makes
the money number credible.
