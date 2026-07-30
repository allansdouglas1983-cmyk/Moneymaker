# TE-0035 — where the money actually was: outsiders, not favourites

Harness `tools/favourites_slice.py`. The **exact frozen TE-0019 machinery** re-run and
sliced; nothing refit, no rule changed, no threshold introduced. Walk-forward over 96,052
feature rows (corpus vintage-2026-07-26, 2012–2026), settled against the v4 exchange price
table at T−600, 2% commission, three-way fill falsification. 21,568 bets fired, 13,526
SUPPORTED.

**EXPLORATORY subgroup diagnostic.** Founder question, 2026-07-29: "ones the model thinks
will likely win, but more than the market does." Reported beside the pooled headline,
never in place of it. No cherry-picked subgroup may be labelled overall performance.

## The slices

| slice | bets | days | ROI | CI 95% |
|---|---|---|---|---|
| **ALL supported (the frozen headline)** | 13,526 | 1,823 | **+2.33%** | [−0.11%, +4.83%] |
| model-favourite (model's side p > 0.5) | 7,615 | 1,706 | +0.83% | [−0.87%, +2.45%] |
| market-favourite (odds ≤ 2.0) | 7,194 | 1,687 | +0.63% | [−1.04%, +2.28%] |
| **outsiders (odds > 2.0)** | 6,332 | 1,590 | **+4.26%** | [−0.60%, +9.14%] |

Every slice spans zero at 95% — splitting the sample costs precision, exactly as the
power arithmetic predicts. The *point estimates* are nonetheless ordered and the ordering
is large: the outsider half carries roughly five times the favourite half's return.

## Reading

**The founder's requested lens is the weaker half of the edge.** Both definitions of
"favourite" — the model's own (p > 0.5) and the market's (odds ≤ 2.0) — land near +0.7%,
while the outsider complement lands at +4.26%. The pooled +2.33% is a blend of the two,
not a uniform property of every bet the rule fires.

This is what market efficiency predicts. The front-runner is where the money and the
attention concentrate, so the price is sharpest there; mispricing survives longer on the
side nobody is defending. It is also consistent with TE-0001's Challenger/ITF tier
finding and with the pyramid features being the model's largest contributors: the
information the market underweights is information about the *less-watched* competitor.

**What this does NOT license.** The outsider slice was not selected in advance, its CI
spans zero, and its width (±4.9pp) is nearly the whole point estimate. It is a direction
to respect, not a strategy to adopt. Restricting the served rule to outsiders on the
strength of this table would be precisely the after-the-fact threshold-fitting the frozen
policy exists to prevent (`exchange_settlement.settle`: "a threshold is the classic place
to launder an overfit"). **MIN_EDGE stays where it is; the bet rule is unchanged.**

## What was done with it

Display only. The site gained a board filter — "Likely winners the market underrates"
(model's side p > 0.5 AND positive edge) — because the founder asked to see that class.
It re-sorts already-scored rows and re-prices nothing. This finding is what lets that tab
be labelled honestly rather than implied to be the strongest one: the picks it shows win
more often and historically earned less.

## Status

EXPLORATORY, non-gating, recorded for the trial ledger as a founder-requested subgroup
read. The pooled supported number remains the only headline, and it remains undecided
after execution costs (TE-0020).
