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

## When something looks broken

- `/health` answers with `ok:true`, the model digest, and `state_stale_days`. Stale > 8
  days means the Tuesday refresh failed — check the Actions tab; a push whose commit
  message contains `[refresh]` re-runs the full pipeline manually.
- The scorecard shows its own denominators (pending, unmatched, excluded) precisely so a
  quiet failure is visible as a growing "pending" count rather than a flattering silence.
