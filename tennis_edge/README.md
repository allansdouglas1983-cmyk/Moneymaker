# `tennis_edge`

Measurement of whether a tennis model can beat the closing price, a model that does, and a
weekly job that keeps extending the measurement without anyone present.

## The short version, as of 2026-07-26

**A model that beats the closing price exists.** It gains **+0.000862 nats** over the
de-vigged close, day-clustered 95% CI [+0.000471, +0.001228], on 63,576 out-of-sample
matches, and a placebo that detaches the features from their matches returns −0.000114 — so
the procedure cannot manufacture the number
(`docs/research/findings/TE-0007-the-model-that-beats-the-price.md`).

Two things got it there, and both are recorded below because the sequence matters more than
the result:

1. **The market's errors do not all point the same way.** Ranking and rating gaps are
   *over*-weighted by the close; the serve model is *under*-weighted. Six earlier
   architectures bundled these into one composite probability, where a fade and a follow of
   similar size cancel — which is a mechanical explanation for the α ≈ 0 below, not a
   metaphor for it.
2. **Ratings that can see below the main tour.** Every earlier rating was fed only the
   priced main-tour corpus, so a qualifier with fifty Challenger matches looked like a
   debutant. The three largest coefficients in the fitted model are pyramid ratings and the
   serve model, and on the 10,209 matches with *no* pyramid record the model adds exactly
   **+0.000000** — the gain lives entirely where the new information exists.

**What it is worth, and where it is not yet known.** Against bookmakers it converts: +0.98%
at Pinnacle and +3.05% at best-of-market, against controls of −2.08% and +0.42% for the
identical rule driven by the market's own probability. At Betfair — the only venue that
cannot limit a winning account — the two available measurements disagree in sign and both
span zero. **The exchange is untested at usable power, not shown to fail.** Settling it
needs roughly 49,000 markets of tick data.

Nothing here authorises a stake. `upcoming.py` pins `recommendation` to `NOT_EVALUATED` and
a test asserts no input can move it.

## What was measured before that, and why it read as nothing

Four architectures, each evaluated walk-forward against the same pinned market benchmark
(log loss **0.57539** on power-de-vigged Pinnacle closing prices, locked as a regression
test in `tests/integration/tennis_edge/test_market_benchmark.py`).

| Architecture | Result against the market |
|---|---|
| Elo, surface Elo, weighted Elo | calibration slope b₁ = **−0.027** |
| Barnett–Clarke point model over shrunk serve statistics | b₁ = **+0.056**, Diebold–Mariano t = 1.89 |
| Cross-book consensus deviation, closing prices | CLV **−1.59 %**, deflated Sharpe 0.048 |
| Residual gradient boosting on a market logit offset | **+0.00018 nats**, DM t = 0.94 |

All four are flat, and two later ones (full-pyramid Elo, MLE market combination) were too.
That was read at the time as "there is no edge in these inputs". The single-feature residual
diagnostic showed it was really "every architecture so far combined these inputs in a way
that cancelled them" — see the short version above and TE-0005.

Every one of those uses **bookmaker closing prices**: 4.4% overround, and a displayed line
rather than a transactable one. **Exchange prices are the one genuinely untested case** —
no overround, commission on the net result only, and a price someone will actually trade at.

That test is now built and waiting on data. `betfair.py`, `exchange.py` and
`exchange_link.py` turn a Betfair Historical BASIC download into the same benchmark the
bookmaker prices were measured against. Betfair returns 403 to this container (US IP,
regional block), so the archives have to be fetched from a UK connection and dropped under
`TENNIS_EDGE_DATA`; nothing else is required.

```
uv run python -m tennis_edge.exchange_link --betfair <path>
```

### How much is the model worth? α ≈ 0, seventeen years running — 2026-07-25

The decisive measurement (`docs/research/findings/TE-0004-what-the-model-is-worth.md`).
Rather than asking "is the model better than the market", fit
`score = α·logit(model) + β·logit(market)` by MLE, refitted each year on strictly earlier
years, scored on **72,669 out-of-sample matches**.

| | value | t |
|---|---:|---:|
| α (model weight) | ≈ 0, often negative | **−0.4 to +0.3, every year** |
| β (market weight) | ≈ 0.95 | **55 to 69** |

The control that settles it — β alone, α forced to zero, identical rows:

| | pooled log loss |
|---|---:|
| market | 0.58234 |
| shrink-only (α = 0) | 0.58219 |
| full combination | 0.58217 |

**Gain from shrinking the market alone +0.00015 nats; gain the model adds on top
+0.00001.** The model contributes 6% of a 0.03% improvement. The one real finding is that
the de-vigged market is very slightly overconfident and shrinking its logit ~5% is a
genuine, overwhelming (t≈60), economically trivial improvement.

That is what `predictor.py` implements: **the price, recalibrated**, with the model view
reported as a labelled diagnostic and `model_weight` on every prediction.

**Superseded as the best available model, and worth keeping for why.** The α ≈ 0 result is
correct about the thing it measured — a *single composite* model probability weighed against
the market. TE-0005 and TE-0007 show that constraint was the problem: unbundled into
separate corrections with free signs, the same class of information gains 3.5× the best
single feature. `residual_model.py` is the model that does; `predictor.py` remains the
honest answer to the narrower question it was built for.

### Exchange vs bookmaker prices — tested 2026-07-25

Every measurement above uses **bookmaker closing prices**. The one venue that matters for
actually betting is the exchange, and the June 2026 Betfair ADVANCED corpus answers it
(`docs/research/findings/TE-0003-exchange-vs-bookmaker-june-2026.md`, 416 linked markets).

| | exchange | bookmaker (b365) |
|---|---:|---:|
| log loss (midpoint) | 0.59316 | 0.59454 |
| round-trip margin | **1.12%** | **4.4%** |

**As a forecast they are indistinguishable** — paired advantage +0.00138 nats, t = +0.70
over 416 matches on 30 days. **As a venue the exchange is ~1.6 points cheaper per bet**,
which is the whole of its advantage. Median size at best back £250 on the linkable
(main-tour, liquid) subset.

So the exchange should be the assumed venue for any future economic test, but no model that
fails against bookmaker closing prices becomes viable just by moving there.

### The Challenger/ITF tier thesis — tested 2026-07-25, closed 2026-07-26

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

**Closed by measurement the next day, not left as "untestable".** The June ADVANCED corpus
turned out to be *mostly lower-tier tennis* — the existing link joined it against a
main-tour corpus and discarded 70% as unmatched. Linking on pyramid identities and grading
from Betfair's own settlement gives 2,227 scored markets, and the answer holds at real
transactable prices (TE-0006): the tier costs **3.67% (ATP) / 4.66% (WTA)** round-trip at
the off against 1.12% on the main-tour exchange, pyramid Elo is worse than the price at
every horizon on both tours, and flat staking loses 1.8–8.3%.

### The price does not sharpen — tested 2026-07-26

Across eight horizons on the June tick corpus the spread collapses from **44.9 ticks to
3.5** between T−24h and the off, and the log loss does not move (0.59372 → 0.59337). All the
sharpening is liquidity; none is information. That closes the "bet early" thesis directly —
there is nothing arriving to anticipate — and with it signed drift, drift-trading and the
favourite–longshot bias, all of which came back within noise.

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
| `betfair.py` | Betfair Historical BASIC reader. Pre-off only; BSP quarantined behind `grading_view()`. |
| `exchange.py` | Exchange probability and EV — no overround, commission on the net result. |
| `exchange_link.py` | Joins Betfair markets to corpus matches with typed exclusions, and benchmarks exchange against bookmaker on the same matches. |
| `pyramid.py` | Elo over the whole professional circuit — Grand Slam to Futures — keyed to priced-corpus names. The only rating here that knows a player's Challenger record. |
| `pyramid_link.py` | Links exchange markets to pyramid identities and grades them from **Betfair's own settlement**, which is what made the lower tiers testable at all. |
| `snapshots.py` | Per-horizon market states cached out of the tick corpus, so a price experiment loads in a second instead of replaying 45 hours per market. |
| `feature_cache.py` | The feature matrix keyed to the inputs that produced it. A mismatch is a miss; a truncated file raises. |
| `residual_features.py` | The one residual feature builder, shared by every experiment and by the predictor. Ten minutes cold, two seconds warm. |
| `residual_model.py` | The fitted model as a deployable artefact: coefficients, training window, digest. Full Newton with a line search — the diagonal version diverged. |
| `upcoming.py` | Prices fixtures that have not been played. Commission-aware break-even; `recommendation` pinned to `NOT_EVALUATED`. |
| `cli.py` | `fit` / `show` / `price`. |

Odds columns are usable for evaluation and execution but remain **banned as model
features** — `features.py::assert_no_price_features` enforces that.

## Running it

```
python -m tennis_edge.cli fit              # build features (cached), fit, freeze to artifacts/
python -m tennis_edge.cli show             # print the frozen model and its digest
python -m tennis_edge.cli price fixtures.json     # price upcoming matches
```

Freezing is the point of `fit`. A prediction recorded today is only evidence if the
coefficients that produced it can be named months later, and a model refitted on every run
cannot be held to anything it said. Re-fitting produces a *new* digest rather than editing
the old artefact, so predictions already recorded still name the model that made them.

`price` never prints a recommendation. The model's exchange performance is undecided at the
power available, and turning an undecided statistical result into a financial instruction is
the specific failure this programme exists to avoid.

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
