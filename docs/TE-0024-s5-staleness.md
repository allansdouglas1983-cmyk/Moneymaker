# TE-0024 — S5 closed: the staleness rule frozen from forecast quality; the money agreed from the other side

The full S5 sequence ran in its registered order, each step committed before the next was
allowed to look: the `ltp_age_at` primitive (tests red → green), the v2 price-table kind
carrying per-side ages (v4 table, 48,596 rows, guard passed — v3 byte-identical
underneath), reading (1) in log-loss, the freeze, then reading (2) in money.

## What the ages themselves say

At T-600s the "current" exchange price is typically an old opinion: the older side's last
print is a median 327 seconds stale, and 32% of rows (15,685) have a leg more than ten
minutes old. Band composition: <60s 5,301 / 60–600s 27,610 / >600s 15,685.

## Reading (1) — forecast quality by band (the only confirmatory look)

| band | n | gain, exchange+features over bare exchange | 95% CI |
|---|---|---|---|
| <60s | 4,388 | +0.002139 | [+0.000392, +0.003842] |
| 60–600s | 22,491 | +0.000998 | [+0.000242, +0.001777] |
| >600s | 11,714 | +0.000349 | [−0.000729, +0.001317] |

**Primary endpoint (pre-registered): T = gain(>600s) − gain(<60s) = −0.001790
[−0.004431, +0.000950] at the four-family 98.75% bar — NULL.** The point direction is the
opposite of the phantom-edge hypothesis: descriptively, the model's gain over the anchor
*shrinks* with staleness rather than growing. The declared consequence of a null applies:
the threshold below is **an assumption, not a measurement** — a null of this width does
not locate a boundary.

The binding amendments held: the age × post-horizon-prints cross-tab confirms staleness
and thinness are one variable seen from two sides (>600s rows are 35% SILENT markets vs
8% in <60s — never cited as independent evidence), and band composition shows no
odds-band or tour confounder (all bands span both tours, all years, similar odds mix).

## The freeze (step 2, before any money)

Commit 9ef3544, from the log-loss strata only: **refuse the >600s band** — the one whose
model-over-anchor gain fails to clear zero even descriptively. Labelled an assumption in
the code itself; live scope is the delayed-key observation path and timestamped manual
entries (the Betfair UI shows a price, not its age); an unknown band is out of scope,
never silently admitted.

## Reading (2) — money by band, under the already-frozen gate

| reading | bets | ROI | 95% CI |
|---|---|---|---|
| ungated (= TE-0022, consistency ✓) | 38,314 | +2.37% | [+0.94%, +3.70%] |
| **gated by the frozen rule** | 26,532 | **+3.49%** | [+1.78%, +5.28%] |
| gated, supported only | 18,903 | +3.36% | [+1.41%, +5.45%] |
| band <60s | 4,355 | +5.26% | [+1.30%, +9.37%] |
| band 60–600s | 22,177 | +3.14% | [+1.20%, +5.14%] |
| band >600s | 11,782 | −0.16% | [−2.60%, +2.30%] |

Money is monotone in freshness, agreeing with the forecast strata from the other side,
and the stale band is dead money — it is also where fill evidence collapses (NO_EVIDENCE
26.0% vs 4.6% in the fresh band; supported share 53.9% vs 73.9%). All rows hypothetical
trade-through returns; TE-0020's execution-cost band applies to every one; the gated
number is a policy refinement of seen data and **cannot promote the assumption label**.

## Standing state

`STALENESS_REFUSAL_BANDS = (">600s",)` is the staleness-refusal candidate carried into
prospective capture, alongside S4's coverage gate — both frozen, both labelled, both
awaiting confirmation on data that did not exist when they were written. The v4 table
(kind v2, ages) is the standing price table. Next in the frozen order: S6, the site
grading its own served predictions with the cost band displayed.
