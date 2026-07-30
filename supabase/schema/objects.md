# What each database object is for

Column lists live in `tables.sql`. This file records *why* each object exists, because
that is the part a schema dump loses and the part a future rebuild actually needs.

## The served model and its inputs

| object | purpose |
|---|---|
| `model` | The frozen residual model: coefficients, feature names, training window, digest. `is_current` selects the served one. The weekly job writes a new row; old rows stay so any past prediction can name the model that made it. |
| `player_state` | The walk-forward rating state as of a date — Elo, surface Elo, pyramid ratings, serve detail, workload, latest-known rank. Rebuilt weekly; `as_of` is the knowledge-time boundary the site enforces. |
| `head_to_head` | Pairwise meeting counts, stored once under the sorted pair. |

## The live board

| object | purpose |
|---|---|
| `fixtures` | Upcoming matches with the price the board is pricing from. `source` is a closed vocabulary (`MANUAL_BETFAIR_UI`, `ODDS_API_*`) so an unknown provenance is refused. `updated_at` is the price's age — TE-0027 measured that acting on stale prices costs ~0.2% ROI. |
| `config` | Service-role-only key/value: API keys, Betfair credentials, refresh throttle stamps, the real-money loss budget. RLS enabled with **no policies**, so the anon key cannot read it. |
| `player_aliases` | Durable feed-name → corpus-name corrections. Consulted *before* the spelling heuristic so a human fix is never re-guessed. |
| `unmapped_names` | Names the matcher could not resolve, with counts. Each is a match shown with no model opinion — evidence not collected. The review queue for closing coverage gaps. |

## The evidence record

| object | purpose |
|---|---|
| `predictions` | Append-only. What was believed, when, at what price, from which model digest and state vintage. `recommendation` is pinned `NOT_EVALUATED` by check constraint. Never updated — a later view is a new row. |
| `ledger` | Predictions joined to outcomes after settlement, with model and market log-loss. Written by `grade_ledger()`. |
| `forecasts` | The automatic scorecard: the previous week's committed state graded against Bet365 on every completed corpus match. Knowledge-time enforced by git history. |
| `results` / `result_aliases` | The rolling results window pulled from the committed artifact, and the name→key aliases that join it. Replaced whole on each pull; the ledger is the durable record. |
| `price_observations` | Every venue's quote at every refresh (~20–35 per match). Feeds line-shopping and closing-line-value analysis. Capture only: encodes no commission assumption and no venue preference. |
| `book_snapshots` | Betfair order-book depth via the delayed key. Dormant until a client certificate is registered. |
| `market_complex` | Cross-market solver output. Research diagnostic; the coherence layer it served was killed by TE-0030 and nothing served reads it. |

## Real money

| object | purpose |
|---|---|
| `placed_bets` | Bets the founder placed **by hand**, recorded with the actual matched price (ADR 0020). Nothing in this system places an order. `status` covers `CHECK_STATEMENT` for retirements/walkovers, because for real money the account statement is truth and the local grade is a hypothesis. |

## Views

| object | purpose |
|---|---|
| `venue_dispersion` | Best exchange quote vs Betfair per match per capture. Exchanges only — bookmakers restrict consistent winners, so their prices are not durably takeable (see `tennis_edge/venues.py`). Gross of commission by design. |

## Functions

| object | purpose |
|---|---|
| `pull_state()` | Fetches the committed walk-forward state artifact and replaces `player_state` / `head_to_head` / `model`. Credential-free: reads a public raw.githubusercontent URL. |
| `pull_results()` | Same for the results window, then calls `grade_ledger()` and `grade_placed_bets()`. |
| `pull_forecasts()` | Same for the automatic forecast ledger. |
| `grade_ledger()` | Joins the last pre-match prediction per match to results and writes log-losses. Declared vintage policy: post-match rows never grade. |
| `grade_placed_bets()` | Settles real bets. COMPLETED only; anything else becomes `CHECK_STATEMENT`. |
| `note_unmapped()` | Upsert-with-increment for the unmapped-name queue (PostgREST cannot express the increment). |

## Scheduled jobs (pg_cron)

| schedule (UTC) | job |
|---|---|
| `0 6 * * 2` | `pull_state` — Tuesday, after the weekly rebuild commits |
| `30 7 * * 2` | `pull_results` — grades both ledgers |
| `45 7 * * 2` | `pull_forecasts` |
| `15 6,12,18 * * *` | `board-refresh` — odds feed; the endpoint's own 6-hour throttle is the real guard |
| *(unscheduled)* | `book-capture` — order-book depth, pinned to `eu-west-2` because Betfair refuses US-soil logins. Off until a certificate is registered. |

## Invariants worth not breaking

- `config` has RLS on and **no policies**. Never add one.
- `predictions.recommendation` is check-constrained to `NOT_EVALUATED`. That constraint is
  the last line of defence behind the structurally-unreachable `BET_CANDIDATE`.
- `fixtures.source` is a closed vocabulary. Adding a venue means extending it deliberately.
- Nothing in this database, and nothing that reads it, places, cancels or amends a bet.
