# TE-0006 findings — the lower-tier exchange, and whether the price sharpens

**Measured:** 2026-07-26, in-workspace against the June 2026 Betfair ADVANCED corpus.
Reproducible from the named scripts; nothing here is a source claim.

Two questions, both of which had been recorded as blocked and both of which turn out to be
answerable with data that was already on the machine.

---

## Part 1 — the Challenger/ITF thesis, at prices you can actually transact at

**TE-0001 closed task #72 as untestable on free data.** Published operator figures put the
achievable yield at roughly 9% in Challenger/ITF against 2.4% on the main tour, and the one
corpus carrying those tiers priced them 94–100% off an OddsPortal aggregate — an average
across books and across time that nobody quotes and nobody can bet into. The verdict was
that testing it needed exchange historical data, which was unreachable.

**The data was already here, and had been misread.** The June ADVANCED corpus is not a
main-tour sample with gaps: it is *mostly lower-tier tennis*. Its event names are ITF and
Challenger players — Roca Batalla, Jorda Sanchis, Ma van der Merwe. The only link built for
it joined into the main-tour Tennis-Data corpus, so the lower-tier majority was correctly
reported as having no corpus match and then quietly forgotten. Linking on pyramid identities
instead takes the yield from **425 markets to 2,227**, out of 3,521 read.

Outcomes come from Betfair's own settlement, which matters more than it sounds: Sackmann's
archive ends May 2026 for ATP and 2024 for WTA, so there is no other source of June 2026 ITF
results in reach. It also makes the no-lookahead argument structural rather than careful —
the rating state is built from an archive that *stops before the scored window begins*, and
the run asserts it: `rating state frozen at 2026-05-24; 0 archive matches arrive between
2026-06-01 and 2026-07-02`.

Excluded and counted, never absorbed: 627 unresolved names, 377 markets whose tour could not
be resolved uniquely, 190 with too thin a rating history, 100 with no unique settled winner.

### Finding 1 — the lower-tier exchange is expensive, not cheap

This is the number TE-0001 wanted and could not get. Overround is both best-back prices,
so it is the round-trip cost of crossing.

| horizon | ATP overround | WTA overround |
|---|---:|---:|
| T−6h | **14.16%** | **23.05%** |
| T−1h | 5.17% | 5.81% |
| T−10m | **3.67%** | **4.66%** |

For comparison: TE-0003 measured **1.12%** on the main-tour exchange, and TE-0001 measured
4.4% at main-tour bookmakers.

So the lower-tier exchange at the off costs **three to four times** what the main-tour
exchange costs, and about the same as a main-tour bookmaker. Six hours out it is
catastrophic. TE-0001's conclusion that the tier is expensive rather than cheap was right,
and it survives moving from bookmakers to the exchange. A 9% claimed yield does not survive
a 4% round trip plus 2% commission on winnings.

### Finding 2 — pyramid ratings do not beat the lower-tier price either

Elo trained on the whole professional pyramid, which is the only rating in this programme
that knows a player's Challenger and Futures record, scored against the exchange midpoint at
the same horizon:

| | ATP exchange | ATP model | WTA exchange | WTA model |
|---|---:|---:|---:|---:|
| T−1h log loss | **0.60490** | 0.64362 | **0.61106** | 0.67163 |
| T−10m log loss | **0.60312** | 0.64688 | **0.60898** | 0.67071 |

The model is worse at every horizon and on both tours. Blending 10% of it into the price
adds nothing measurable in five of six cells.

The sixth — WTA at T−6h, +0.0048 nats [+0.0021, +0.0071] — is **not** treated as a finding.
It appears only at the horizon where the overround is 23%, which is exactly where the
midpoint is least reliable, and it vanishes by T−1h. That is the signature of an imprecise
price being improved by any independent estimate, the same mechanical effect the
microstructure battery found in spread width. With six cells, 0.3 would clear by chance.

### Finding 3 — and it does not pay

Flat stakes at the actual best-back price with commission on net winnings:

| | T−6h | T−1h | T−10m |
|---|---|---|---|
| ATP | −8.29% (t −2.15) | −8.17% (t −2.27) | −6.45% (t −1.81) |
| WTA | −3.61% (t −0.73) | −2.05% (t −0.44) | −1.81% (t −0.39) |

Every cell negative; the ATP losses are significant.

### Verdict on task #72

**Closed. Tested at transactable prices and refuted.** The thesis was that the lower tiers
are where the edge is because the market has least to price from. The market there is indeed
worse — but the cost of transacting is worse by more, and the one rating that knows those
tiers does not beat it anyway.

This is a stronger closure than TE-0001's. That one said "cannot be tested"; this one says
"tested, and no".

---

## Part 2 — the exchange price does not sharpen

Run over the main-tour-linked snapshot cache (425 markets, eight horizons from T−24h).

| horizon | log loss | Brier | mean spread (ticks) |
|---|---:|---:|---:|
| T−24h | 0.59372 | 0.20639 | 44.89 |
| T−6h | 0.59118 | 0.20465 | 6.54 |
| T−1h | 0.59247 | 0.20524 | 3.59 |
| T−10m | 0.59345 | 0.20561 | 3.48 |
| T−2m | 0.59337 | 0.20556 | 3.85 |

**The spread collapses by a factor of thirteen and the forecast does not improve at all.**
All the sharpening is liquidity; none of it is information.

That closes the "be early" thesis directly. The reason to prefer an early price would be
that the late price contains information the early one lacks, so that being early means
transacting before that information arrives. There is no such information here — which also
means there is nothing for a model to anticipate.

Everything downstream reads the same way:

- **Drift** is within noise in every price band (|t| < 0.7) and for the always-back-A
  control (−0.0028, t = −0.49).
- **The favourite–longshot bias** points the right way — backing longshots at the early
  price returns −42.4% — but on 62 bets it is an observation of the bias, not a strategy.
  Backing favourites returns −4.91%.
- **Trading the drift** out-of-sample is a coin flip: 52.9% sign agreement in training,
  −1.67% ROI on 187 test bets.

One correlation clears easily: early spread width against subsequent drift, r = 0.249,
t = 5.18. **It is mechanical, not informative.** A wide spread means an imprecise midpoint,
and an imprecise midpoint mean-reverts toward the eventual price by construction. It is
measurement noise in the early estimate rather than a signal about where the market is
going, and it is recorded here so that nobody later reads it as one — the same caution the
WTA T−6h cell in Part 1 needs, for the same reason.

## Reproduction

- `tennis_edge/experiments/lower_tier_exchange.py` — Part 1.
- `tennis_edge/experiments/microstructure.py` — Part 2, off the snapshot cache.
- `tennis_edge/pyramid_link.py` — the identity path that unlocked the lower-tier sample.

Data: Betfair Historical ADVANCED, June 2026 (outside the repository); Jeff Sackmann's
archive (CC BY-NC-SA 4.0, non-commercial) for the ratings.
