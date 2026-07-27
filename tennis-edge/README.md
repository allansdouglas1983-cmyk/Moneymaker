# Tennis Edge

A market-anchored tennis probability model, and the private website that serves it.

**Page:** https://allansdouglas1983-cmyk.github.io/Moneymaker/ (GitHub Pages, `/docs`)
**API:** https://sujrylzzxcqxxfygptns.supabase.co/functions/v1/tips

Sign in with the owner email; a code is emailed. Nothing else can sign in.

The two are separate on purpose. Supabase's gateway forces `text/plain` and a
`default-src 'none'; sandbox` CSP onto every `/functions/v1/*` response so that nobody can
host web pages on a supabase.co domain — an Edge Function is an API surface, and the view
belongs somewhere that serves HTML.

## What it does

Enter a match and its Betfair back prices. It returns the model's probability for each
player, fair odds, the commission-aware break-even, the edge over that break-even, and
deterministic reason codes saying which inputs moved the price. Every prediction is written
to an append-only table before the match and is never rewritten afterwards.

It never says "bet". `BET_CANDIDATE` has no branch in the scoring code that can produce it,
and `recommendation` is pinned to `NOT_EVALUATED` by a database constraint.

## What the model is

A correction to the market price, not a replacement for it. The de-vigged market logit is an
unpenalised offset; twenty-two features add signed corrections to it. With zero coefficients
it reproduces the market exactly, which is the correct degenerate case — absent evidence, the
price stands.

| layer | features |
|---|---|
| Elo family | `elo_residual`, `surface_elo_gap`, `weighted_elo_gap` |
| Ranking | `rank_gap` |
| Barnett–Clarke point model | `point_model_residual` |
| Pyramid Elo (Grand Slam → Futures) | `pyramid_elo_gap`, `pyramid_surface_gap`, `pyramid_rest_gap`, `pyramid_workload_gap`, `pyramid_tier_gap` |
| Decomposed serve/return | `first_serve_rate_gap`, `first_win_rate_gap`, `second_win_rate_gap`, `ace_rate_gap`, `double_fault_rate_gap`, `break_save_rate_gap`, `return_rate_gap` |
| Durability | `h2h_gap`, `retirement_risk_gap`, `workload_minutes_gap`, `workload_long_gap`, `surface_switch_gap` |

Fitted by full Newton with the complete Hessian and a backtracking line search, ridge
L2 = 25.0 fixed a priori and never tuned. 96,052 matches, 2002-06-10 to 2026-07-19.

## What it is measured at

**+0.001064 nats** over the closing price, 95% CI [+0.000639, +0.001476], 63,676
out-of-sample matches. Placebo (feature permutation) **−0.000172** [−0.000278, −0.000061].

Each layer measured paired — same rows, same walk-forward, one feature set difference:

| feature set | gain over the closing price |
|---|---|
| 10 features | +0.000862 [+0.000471, +0.001228] |
| + serve detail (17) | +0.000914 [+0.000516, +0.001276] |
| + durability (22) | **+0.001064** [+0.000639, +0.001476] |

Money, flat 1 unit at the actual quoted price, no required-edge buffer. The control is the
identical rule driven by the market's own probability, so its return is price selection and
not skill:

| venue | model | control | bets |
|---|---|---|---|
| Pinnacle | +1.48% [+0.23%, +2.69%] | −2.08% | 38,078 |
| Max | +3.41% [+2.40%, +4.43%] | +0.41% | 60,817 |
| **Betfair Exchange** | **+0.48%** [−3.76%, +4.62%] | **+1.80%** | **2,854** |

**Betfair is the only venue that counts**, because it is the one that cannot limit a winning
account, and Pinnacle has not accepted UK customers since 2016. There the model returned
+0.48% against a control of +1.80%, on 2,854 bets, with an interval four points wide either
side of zero. The layers improved the forecast and **did not move that interval off zero**.
On the venue that matters the result is undecided and the point estimate is not
distinguishable from betting the market's own opinion.

Cross-market coherence is **blocked, not flat**: the solver needs the Betfair historical tick
corpus, `historicdata.betfair.com` returns HTTP 403 from a non-UK address, and the local copy
went with the container it lived in. Not measured, not claimed.

Strongest internal evidence the model is doing something real: on 10,209 matches where no
pyramid record exists, it adds exactly +0.000000.

Closed by measurement, so nobody re-opens them: cross-market arbitrage (zero locks in 5,799
exhaustive covers, best −0.31%); exchange prices do not sharpen (spread 44.9 → 3.5 ticks,
log loss unchanged); the Challenger/ITF tier costs 3.67% ATP / 4.66% WTA round-trip against
1.12% on the main-tour exchange.

## How it runs

```
tennis-edge/                     Python: data, ratings, model, measurement harness
  sport_tennis/coherence/        the cross-market solver (built, not yet wired in)
  tools/emit_golden_vectors.py   emits the 500 cases the TypeScript is held to
supabase/functions/tips/         the JSON API (Deno), and the ported scoring maths
docs/index.html                  the page, one self-contained file
.github/workflows/tennis-edge.yml  weekly rebuild + commit, on GitHub's runners
```

The scoring maths exists twice — Python, where it was measured, and TypeScript, where it
serves. A silent divergence would produce numbers no evidence supports, indistinguishable on
screen from numbers plenty of evidence supports. So it is not trusted:
`emit_golden_vectors.py` writes 500 cases from the Python, chosen to hit the branches
(complete feature sets, absent serve coverage, absent pyramid coverage, empty), and a Deno
test replays every one to 1e-12. It runs in CI on every push. Drift turns the build red.

## Verifying

```
python -m pytest tests                     # from tennis-edge/
python -m mypy --strict tennis_edge
deno test --allow-read supabase/functions/tips/      # from the repo root
```

## No secrets to add

There is no Supabase credential anywhere in this system, because none is needed.

The GitHub Action rebuilds the walk-forward state and commits it to this repository using
the token GitHub already gives it. The database then pulls that file itself —
`tennis.pull_state()` on a `pg_cron` schedule, Mondays 07:00 UTC, an hour after the rebuild.
Every run is recorded in `tennis.state_pull_log`, so a failed pull is visible rather than
leaving the site serving last week's ratings as if they were current.

The first design pushed state into Postgres with the service-role key, which made the whole
system wait on one secret reaching one settings page. Inverting it removed the wait and the
key at the same time: there is no credential to leak because there isn't one.

## Where this came from

Forked out of a research platform where 13,909 lines of working code sat under 22,521 lines
of governance machinery, 42,428 lines of tests and 471 documents. Everything that earns its
place came across, including the whole measurement harness — not fooling yourself is the
hard part. The spec manifest, mutation harness, gate evaluators and the command line tool
did not.

## Not in scope

Pre-off only, back only, no in-play, no Kelly, no order placement, no Betfair account
action, no credential entry, no registration, no billing.
