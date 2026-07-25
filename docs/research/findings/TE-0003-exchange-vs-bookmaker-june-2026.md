# TE-0003 — Exchange prices vs bookmaker prices, June 2026

**Measured:** 2026-07-25 on the June 2026 Betfair Tennis **ADVANCED** corpus already held
(1.1 GB, 20,482 markets, 1–30 June + 1–2 July). All 20,482 files re-verified against the
pilot's per-file SHA-256 manifest before use: **zero failures**.

**Status: DIAGNOSTIC.** Consumes no confirmatory alpha, closes no gate, and is not evidence
for or against any registered model. The June lockbox was already spent by the Stage A
Gate‑1 read (`june-evidence-plan-amendment-v1.yaml`), whose continuation rule returned
FAIL_HARM, permanently prohibiting Stage B. Nothing here fits or refits any registered
model; it measures *prices*.

---

## The question

Every measurement in `tennis_edge` had used **bookmaker closing prices** — a displayed line
carrying a 4.4% overround, at books that limit winners. Exchange prices are what the founder
would actually transact at. Are they better, and how much cheaper?

## Result

416 markets linked out of 3,521, scored against Tennis-Data outcomes.

| price source | exchange log loss | b365 log loss | overround (median) |
|---|---:|---:|---:|
| **MIDPOINT** (probability estimator) | **0.59316** | 0.59454 | **0.9998** |
| **BEST_BACK** (transactable price) | 0.59640 | 0.59381 | **1.0112** |

**Finding 1 — as a probability, the exchange and B365 are indistinguishable.**
Paired advantage to the exchange **+0.00138 nats, per-match sd 0.04043, SE 0.00198,
t = +0.70** over 416 matches spanning 30 days. Not significant, and clustering by match day
(30 clusters, the governed unit) would weaken it further. The exchange closing midpoint is
*not* a materially better forecast than a bookmaker's closing line.

**Finding 2 — the exchange is materially cheaper, and that is the whole advantage.**

| venue | round-trip margin | per side |
|---|---:|---:|
| bookmaker (main tour) | 4.4% | 2.2% |
| **exchange (best-back, median)** | **1.12%** | **0.56%** |
| exchange Challenger/ITF (bookmaker, TE-0001) | 7.3–8.0% | 3.7–4.0% |

Roughly **1.6 percentage points cheaper per bet**, before commission. Commission is charged
on net winnings only, adding ~1% of turnover at even money — so the exchange edge on cost is
real but partly given back. It does not by itself rescue the −5.51% ROI measured in TE-0001.

**Finding 3 — capacity on the linkable subset is adequate.** Median size at best back
**£250–253**. Note the selection effect: the only markets linkable to Tennis-Data are main
tour, i.e. the liquid end. The pilot's median across all 2,876 singles was £57. Capacity is
fine for the matches this system would price; it is not fine across tennis generally.

## Why the midpoint, not best-back

Best-back is the *worst* price on each side. Estimating a probability from it distorts the
favourite/longshot balance even after de-vigging — visible above, where BEST_BACK scores
0.59640 against MIDPOINT's 0.59316 on the same markets. The midpoint (normalised mid of best
back and best lay) is the estimator, and is the pilot's own benchmark candidate 1. Best-back
remains the price EV must be computed against. A quote carries both.

The midpoint's median overround of **0.9998** is the sanity check: a midpoint removes the
spread by construction, so it is a probability and not a cost. The two numbers now visibly
do different jobs.

## Three feed bugs real data caught that fixtures did not

Recorded because they are the same class of error and all three were invisible to tests
written from the specification alone.

| symptom | cause |
|---|---|
| entire corpus unreadable | `ltp: 0.0` is ADVANCED's "nothing traded yet" **sentinel**, not a price; the off-ladder guard correctly refused it |
| stale prices after a side emptied | an **empty ladder array** means the side is gone, not that the previous level persists |
| midpoint available for only 15 of 3,521 markets | `batb`/`batl` arrive as **separate deltas**; an absent key means *unchanged*, an empty array means *cleared*. Conflating them wiped half the book on every one-sided update |

The third is the instructive one: it produced a plausible-looking pipeline that silently
discarded 96% of the two-sided books, and only the pilot's independently measured ~99%
two-sided rate revealed that 15 was impossible.

## Limits, stated plainly

- **One month, one regime.** June 2026 is the grass-court run-up to Wimbledon. The pilot
  already flagged cross-regime stability as the single gap a second month would close.
- **n = 416**, 30 clustering days. Small.
- **Main tour only.** 2,257 of 3,521 markets are Challenger, ITF or doubles that Tennis-Data
  does not carry; they are explicit `UNRESOLVED_NAME` exclusions, not silent drops.
- **B365, not Pinnacle.** Tennis-Data carries **no Pinnacle quotes for June 2026** (0 of
  761). The pinned 0.57539 benchmark is a Pinnacle figure and is **not** comparable to the
  0.594 numbers here.

## What this changes

The strategic answer to "are we measuring against the wrong price?" is **partly yes, and it
does not rescue anything**. The exchange is ~1.6 points cheaper per bet, which matters and
should be the venue assumed in any future economic test. But it is not a better forecast, so
no model that fails against bookmaker closing prices becomes viable simply by moving venue.

Reproduce: `uv run python -m tennis_edge.exchange_link --betfair <corpus>`
(`--price BEST_BACK` for the transactable variant).
