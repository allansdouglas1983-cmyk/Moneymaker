# Operating Tennis Edge — the honest manual

What this is: a private research predictor for ATP/WTA match odds, with every number it
shows traceable to a measured, committed, digest-named model. What it is not: a tipping
service, a betting bot, or anything that has passed a deployment gate. `BET_CANDIDATE` is
structurally unreachable and `recommendation` is pinned `NOT_EVALUATED` — by construction,
not by promise.

## The five-minute weekly routine

Nothing below is required for the system to keep its record — the automatic scorecard
accumulates on its own every Tuesday. The manual routine adds the *decision-time* evidence
layer the automatic one cannot capture.

1. Open the site, log in (password auth, owner-only).
2. When you're looking at a live Betfair Match Odds market you care about, enter the two
   players, the two displayed back prices, and the date — *at the moment you read them*.
   S2 measured that hesitation costs ~0.2% ROI: the price you see now is measurably better
   than the price minutes later, so enter it now or not at all.
3. Read the row it returns:
   - **Edge (after cost)** is a RANGE, not a number. The lower end applies the frozen Roll
     execution-cost band at its conservative pooled width (manual entries can't prove
     their price's freshness, so they get the widest band — that's deliberate).
   - **Status** is the governed vocabulary. `BET_CANDIDATE_DISABLED` means "this is the
     shape of a candidate, and the gate that could ever enable it has not passed."
   - **Reasons** are deterministic sign/threshold codes from the numeric core. They never
     explain *why* a player is better; they say which input moved the price.
4. That's it. The prediction is minted append-only; results join after the weekly pull;
   the scorecard grades itself. Never edit, never re-enter to get a better view — a later
   view of the same match is a *new* row and the record shows both.

## What the numbers rest on (one paragraph each)

- **The model**: a ridge logistic residual on top of the de-vigged market price — 22
  features (ratings, serve decomposition, workload, head-to-head, rank), trained
  walk-forward on ~96,000 matches, frozen as `residual-model-v3.json`. The site's
  `/health` reports its digest; the weekly Action fails if the served digest ever drifts
  from the committed artifact.
- **The measured edge**: ~+0.0011 nats of log-score over the exchange price on 63,676
  matches — real, small, calibrated (slope ≈ 1 on data it never saw, TE-0032), and stable
  across the 2023/24 market shift (TE-0033). The hypothetical money reading (+2.63% ROI
  on supported fills) sits inside a cost band that spans zero (TE-0020) and has passed no
  deployment gate. That is why nothing here recommends a bet.
- **The state**: rebuilt every Tuesday 06:00 UTC (the provider publishes Sunday/Monday
  evening; the old Monday schedule silently cost ~80% of the forecast edge in staleness —
  TE-0029). The database pulls it credential-free at 07:00; results 07:30; forecasts 07:45.
- **The automatic scorecard**: every week, the *previous* week's committed state is graded
  against the Bet365 book on every completed tour match. The state file's pre-match
  existence is enforced by git history, so this record cannot cheat even in principle.
  Bet365 baseline — never comparable to the manual ledger's exchange prices.

## What would change the "no betting" answer

Only a pre-registered deployment gate passing on prospective evidence — which needs the
scorecard record this system is now accumulating. Nothing in this repo may lower that bar:
budgets, stakes and execution live behind gates that are human-controlled specification
changes. Until then the site is an instrument, and its value is that its record is honest.

## Reading the two things that actually matter

**Price age (on every board row).** How old the quote is. Amber past two hours. TE-0027
measured that acting on a stale price costs ~0.2% ROI — a meaningful slice of a ~2% edge —
so an old price is worth re-checking on screen before acting on it, not just trusting.

**Closing line value (Ledger tab).** The share of picks the market moved *toward* after we
made them, and by how much in probability points. This is the earliest honest signal that
a live edge exists, and it is the number to watch — not P&L.

Why not P&L? TE-0036 measured it: at a 50-unit budget, ruin is 29% if the edge is real and
76% if it is not. Both happen often under both hypotheses, so settled profit and loss
cannot distinguish them on any timescale a single person will live through. CLV can,
because it measures every bet continuously instead of waiting for outcomes.

Two honest caveats. The board refreshes three times a day, so the "closing" quote may be
several hours before the off and the number understates the true signal — read it as
multi-hour drift. And CLV is evidence about *edge*, never about *profit*; it is not a
target to optimise and it gates nothing.

**What patience looks like.** Seventeen consecutive losing bets is normal for this rule
(TE-0036). Any reaction to a shorter run is a reaction to noise.

## When a match shows no model opinion

The board can only price a player the rating state knows. When a feed name doesn't
resolve, the fixture still appears with the real exchange price but reads
INSUFFICIENT_DATA, and the name is logged to `tennis.unmapped_names` with a count. Two
different causes, two different answers:

- **A genuinely unknown player** — a debutant, a wildcard, a junior. Nothing to fix; the
  refusal is correct. (First real example: Cruz Hewitt, 2026-07-30. Note the danger the
  matcher avoided — a surname-only match would have priced him with *Lleyton* Hewitt's
  ratings.)
- **A spelling mismatch** — the feed writes a name the corpus spells differently. Fix it
  once and permanently by adding a row to `tennis.player_aliases`:
  `feed_name` (lower-case, accents stripped, punctuation as spaces), `tour`, `player`
  (the exact corpus spelling, e.g. `Zverev A.`), optional `note`. Aliases are consulted
  *before* the spelling heuristic, so a correction is never re-guessed.

Check the queue with: `select * from tennis.unmapped_names order by seen_count desc;`
The counts sort the costly gaps to the top — each one is a match the board showed with no
opinion, which is evidence the ledger never collected.

## When something looks broken

- `/health` answers with `ok:true`, the model digest, and `state_stale_days`. Stale > 8
  days means the Tuesday refresh failed — check the Actions tab; a push whose commit
  message contains `[refresh]` re-runs the full pipeline manually.
- The scorecard shows its own denominators (pending, unmatched, excluded) precisely so a
  quiet failure is visible as a growing "pending" count rather than a flattering silence.
