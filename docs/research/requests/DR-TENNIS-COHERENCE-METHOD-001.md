# DR-TENNIS-COHERENCE-METHOD-001 — Inverting the derivative complex to price Match Odds (ADVISORY)

**Status:** REQUESTED / AWAITING FOUNDER EXTERNAL RESEARCH. Contains **no conclusions**.
Findings inform decisions and never prove a gate (Amendment A §4).

**Classification:** ADVISORY. Implementation proceeds in parallel; this exists to tell us
early if the approach is known to fail, and to import failure modes rather than rediscover
them.

**Requested:** 2026-07-27.
**Related:** SPEC-030, SPEC-034; `sport_tennis/coherence/` (solver, pmf, match);
`tennis_edge/xmarket.py`.
**Companion, do not duplicate:** `DR-TENNIS-XMARKET-INDEPENDENCE-001` already asks whether
derivative prices carry information independent of Match Odds, and holds blocker
`EXT-XMARKET-002`. **This request assumes that question is unanswered and asks a different
one: whether the inversion *method* is known, and what is known about how it fails.** If the
independence question resolves negative, this method is worthless and that is the cheapest
possible outcome to learn.

## What we now hold

The Betfair BASIC archive (2015-07 to 2022-03, truncated at 94%) contains the full derivative
complex at scale, extracted and counted:

| market type | markets |
|---|---|
| SET_WINNER | 300,113 |
| SET_BETTING | 146,112 |
| SET_CORRECT_SCORE | 33,221 |
| NUMBER_OF_SETS | 33,209 |
| PLAYER_A_WIN_A_SET | 33,197 |
| PLAYER_B_WIN_A_SET | 33,209 |
| HANDICAP | 32,859 |
| COMBINED_TOTAL | 20,865 |
| MATCH_ODDS | 478,323 |

A solver exists (`sport_tennis/coherence/`) that identifies per-point serve probabilities
`(p_a, p_b)` from a set of derivative prices and pushes them forward through the
Barnett–Clarke game/tiebreak/set/match recursion to a match probability. It is built, tested
and has never priced anything, because until now there was no corpus to run it on.

**The intended use is deliberately narrow.** The inversion excludes Match Odds from its
inputs. The resulting match probability is then compared to the Match Odds price, and the
difference — `logit(p_coherence) − logit(p_market)` — enters as a feature. Excluding Match
Odds is the entire point: it makes the estimate structurally independent of the price it is
correcting, rather than an echo of it.

## Questions (answers with sources and publication dates)

1. **Is this a known method?** Has anyone published on recovering latent per-point
   probabilities from a set of tennis derivative prices and using the implied primary price
   as a signal? Under what name — implied-state estimation, cross-market arbitrage-free
   fitting, structural inversion, something else. Any sport, not only tennis.
2. **Known failure modes.** Where does such an inversion break? Candidates we expect and
   want confirmed or corrected: non-identifiability (several `(p_a, p_b)` pairs fitting the
   same observed prices), sensitivity to which markets are included, degeneracy at extreme
   prices, the effect of stale quotes on thin derivatives, and the assumption that points
   are i.i.d. within a match — which is known to be false and whose consequences we would
   rather have quantified than assumed.
3. **The i.i.d. point assumption.** Barnett–Clarke assumes independent points with constant
   serve probabilities. What does the literature say about the size of the error this
   introduces at the *match* level, and are there established corrections that stay
   tractable?
4. **Does the derivative complex actually contain extra information?** Related to but
   distinct from DR-TENNIS-XMARKET-INDEPENDENCE-001: even if derivative prices are quoted
   independently, is there evidence that a match probability implied by them differs
   *usefully* from the Match Odds price — as opposed to differing only by noise and staleness?
   Any published measurement of that difference's predictive value would be decisive.
5. **Liquidity as a confound.** Derivative markets are thinner. Is the implied price from a
   thin market systematically biased, and does the literature offer a weighting or a
   liquidity threshold that is not simply fitted after the fact?
6. **What would falsify it cheaply.** The single most informative diagnostic to run first,
   so we spend a day rather than a fortnight learning the answer. We would rather be told
   "test X, and if it comes back flat, stop" than be handed a research programme.

## Constraints on the answer

- **Current as of 2026-07**, sources dated.
- **BASIC only.** No ladder, no traded volume: last-traded prices at roughly one-minute
  intervals. Methods requiring order-book depth are out of scope by founder decision and
  should be identified as such rather than recommended.
- Peer-reviewed and preprint work first; practitioner work with disclosed methodology
  second; tipster and marketing claims excluded.
- **No betting advice, no staking systems.**

## Deliverables

1. Whether the method is known, and under what name, with references.
2. A ranked list of its documented failure modes.
3. A statement on the i.i.d.-points error at match level, quantified if the literature
   quantifies it.
4. The single cheapest falsifying diagnostic.

## Acceptance criteria

Sourced and dated. "Not established in the literature" is an acceptable and useful answer.
If the method is known to fail, say so plainly and early — that outcome saves the most time
and is the most valuable result this request can return.

## If unresolved

Implementation proceeds under our own falsification discipline: the layer must beat the
frozen benchmark on a paired, day-clustered, out-of-sample comparison with a
feature-permutation placebo, exactly as every other layer has had to, and is deleted if it
does not.
