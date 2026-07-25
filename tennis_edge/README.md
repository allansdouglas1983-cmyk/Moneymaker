# `tennis_edge`

Measurement of whether a tennis model can beat the closing price, and a weekly job that
keeps extending that measurement without anyone present.

## What was measured

Four architectures, each evaluated walk-forward against the same pinned market benchmark
(log loss **0.57539** on power-de-vigged Pinnacle closing prices, locked as a regression
test in `tests/integration/tennis_edge/test_market_benchmark.py`).

| Architecture | Result against the market |
|---|---|
| Elo, surface Elo, weighted Elo | calibration slope b₁ = **−0.027** |
| Barnett–Clarke point model over shrunk serve statistics | b₁ = **+0.056**, Diebold–Mariano t = 1.89 |
| Cross-book consensus deviation, closing prices | CLV **−1.59 %**, deflated Sharpe 0.048 |
| Residual gradient boosting on a market logit offset | **+0.00018 nats**, DM t = 0.94 |

All four are flat. That is the same answer the published literature reports for closing
tennis prices, and it is the honest conclusion from the data reachable here.

Two follow-ups are walled rather than concluded. Betfair returns **403 from every
endpoint** for this container's IP, so historical exchange prices are unreachable; the
cross-book work above therefore rests on bookmaker closing prices, which is a weaker test
than exchange prices would be.

### The Challenger/ITF tier thesis — tested 2026-07-25

Published operator figures put the achievable yield near **9% in Challenger/ITF against
2.4% on main tour**, which would mean we had been measuring the wrong tier all along. That
thesis is now tested and **does not survive contact with the data**
(`docs/research/findings/TE-0001-challenger-itf-tier-efficiency.md`).

| tier | overround | model b₁ | t | bets | ROI at the quoted price |
|---|---:|---:|---:|---:|---:|
| main | 4.4% | 0.160 | 6.69 | 19,221 | **−5.51%** |
| challenger | 7.3% | 0.170 | 5.61 | 13,523 | **−7.44%** |
| itf | 8.0% | 0.528 | 19.09 | 10,471 | +1.24% |

Two things kill it. First, the lower tiers are **twice as expensive to trade** — 7.3–8.0%
overround against 4.4%. Second, and decisively, they have **no real prices**: ITF quotes
are 100% OddsPortal aggregate and Challenger 94.2%, so only 152 Challenger matches and
**zero** ITF matches carry two or more actual books. The ITF +1.24% is measured against an
aggregator average no one quotes, is ~1.3 standard errors from zero, and is gross of
commission. Where real prices exist, the method loses.

## What the weekly job is — and is not

Tennis-Data publishes each week's **results and their closing odds in the same file**. A
prediction derived from that file can never be timestamped before its own outcome was
knowable. So this is **not** a prospective tipping record, it issues no advice, and it must
not be described as one.

It is a **frozen-policy, forward-extending out-of-sample evaluation**. The integrity claim
comes from git, not from trust: `policy.py` and its constants are committed at a hash dated
*before* the matches it is later judged on existed, and every ledger row records that
commit and a digest over every constant alongside the data vintage. Anyone can check the
claim "this rule predates this data" rather than take it on faith. Each week adds matches
the model was never fitted on.

Given four flat architectures, the expected result is a ledger that accumulates evidence of
**no edge**. That is still worth having: it is the thing that would detect an edge if one
ever appeared.

## Modules

| Module | Role |
|---|---|
| `corpus.py` | Typed loader. Re-orients provider rows (stored winner-first) to name-ordered `(player_a, player_b)` with the outcome isolated in `winner_is_a`; measured 0.4998 over 113,547 matches, so no ordering leak. |
| `devig.py` | Margin removal: proportional, multiplicative, power, Shin. Power is the default — it leaves the market at calibration slope 1.011. |
| `metrics.py` | Log loss, Murphy-decomposed Brier, calibration by IRLS, day-clustered bootstrap, Diebold–Mariano, deflated Sharpe. |
| `ratings.py` | Elo / surface Elo / weighted Elo, day-batched. |
| `serve_stats.py`, `point_model.py` | Shrunk serve estimates and the Barnett–Clarke / O'Malley hierarchical match model. |
| `consensus.py` | Cross-book consensus deviation. CLV is measured against a reference **outside** the consensus, or it raises. |
| `backtest.py` | Walk-forward harness, one-tick slippage, trial log. |
| `refresh.py` | Immutable Tennis-Data vintages with per-file SHA-256 provenance and conditional GET. |
| `archive.py` | Restores the Sackmann archive from Software Heritage, pinned to an exact snapshot and verified against a pinned digest. |
| `policy.py` | The frozen decision rule and its digest. |
| `ledger.py` | Append-only JSONL evidence store. |
| `weekly.py` | The unattended job. |

Odds columns are usable for evaluation and execution but remain **banned as model
features** — `features.py::assert_no_price_features` enforces that.

## Running it

```
python -m tennis_edge.weekly --dry-run     # evaluate and report, write nothing
python -m tennis_edge.weekly               # refresh, evaluate, append to the ledger
```

The job is idempotent by construction: matches already in the ledger are skipped, so a run
that dies halfway, or a schedule that fires twice, changes nothing on the second pass.
Ordering is the safety property — state is rebuilt strictly forward and every match is
decided from state that has observed only *earlier* days, which
`test_a_decision_never_sees_a_result_from_its_own_day_or_later` asserts against the state
that actually priced each match.

Raw provider data lives outside the repository (`TENNIS_EDGE_DATA`, default
`~/tennis_edge_data`) so a push never redistributes someone else's corpus.

Both corpora restore themselves. Tennis-Data is fetched by `refresh.py`; the Sackmann
archive by `archive.py`, which matters because **both upstream GitHub repositories are
deleted** and Software Heritage is now the only route to the data:

```
python -m tennis_edge.archive            # restore whatever is missing (~88 MB, ~20s)
python -m tennis_edge.archive --verify   # check the local corpus, fetch nothing
```

It is pinned rather than resolved live — the exact snapshot, revision and directory of the
last successful crawl, plus a digest over the git blob hashes of all 258 consumed match
files. A restore that does not reproduce that digest is refused, and a corpus that already
verifies costs zero requests. Two consequences: the corpus is reproducible, which is what a
frozen policy needs underneath it; and the **coverage asymmetry is permanent** — ATP was
last archived 2026-05-08 and WTA 2025-01-03, so ATP runs to May 2026 and WTA only to the end
of the 2024 season. Any split has to respect that.

The archive is CC BY-NC-SA 4.0 (attribution to Jeff Sackmann / Tennis Abstract,
non-commercial). If it is missing entirely the weekly job **refuses to run** rather than
quietly pricing every row with the rating blend alone under the point-model policy digest.

## Verification

```
uv run pytest tests/unit/tennis_edge tests/integration/tennis_edge
uv run mypy --strict tennis_edge
uv run ruff check tennis_edge tests/unit/tennis_edge
```
