# TE-0016 — The literature screening round: one death, one survivor with nowhere to go

Two feature families from DR-TENNIS-FORECAST-LIT-001 were screened under one pre-registered
rule: paired walk-forward on identical rows, day-clustered bootstrap, and — because two
families were tested from the same research round — verdicts at the Bonferroni-adjusted
97.5% bar, not the bare 95%. Both runs: 63,676 out-of-sample matches, 2,000 draws.

| family | gain (nats) | 95% CI | verdict |
|---|---|---|---|
| cross-book dispersion (`ln(max/avg)` gap) | +0.000082 | [+0.000025, +0.000139] | survives the adjusted bar — and goes nowhere (below) |
| network (common opponents + intransitivity) | **−0.000043** | [−0.000077, −0.000007] | **dead — significantly negative** |

## The network layer is not merely useless here; it is harmful

The one family the literature genuinely backed — cyclic matchup structure a scalar rating
cannot hold — *subtracts* forecast value once the market anchor and 22 features are present:
the interval is entirely below zero. This is consistent with the source itself read
carefully: Clegg and Cartlidge's positive result was **subset-only profitability** while
their model lost to the market overall on the full sample. As a broad residual on an
anchored model, the information is evidently already in the price, and the estimated
coefficients only add noise. The layer is not wired into the feature builder; the module and
its 13 tests remain solely so this measurement stays reproducible. Recorded as the negative
result it is.

## Dispersion survives the letter of the rule and is still not deployed

At the adjusted bar the dispersion interval stays above zero (normal-approximation lower
bound ≈ +0.000017). Three reasons it is nonetheless **measurement-only, not admitted to the
feature registry**:

1. **It has no live path.** The feature is the spread between the panel's best and average
   quote at the close; the site's live input is a single Betfair price. Serving coefficients
   fitted *with* a feature to predictions that cannot have it produces neither model.
2. **The gain is a tenth of the durability layer's**, itself the smallest kept layer.
3. The odds-in-features ban would need a governed exception, and spending governance on a
   +0.00008 nats measurement-only feature is spending it wrong.

It is recorded as a true, small, currently-unusable fact about the market's shape.

## What the round actually established

Nothing from the published post-2018 literature enters the deployed model. That is not a
failure of the round — it is the round doing its job cheaply: two families measured to a
verdict in a day, one killed before it could quietly damage the model, and the review's own
headline confirmed in our data — once a sharp market anchor and a well-specified residual
are in place, the remaining broad headroom is vanishingly small.

The durable next gains remain what the data said before the literature did: the exchange
re-anchor (+0.000773 nats, deployment gated on the archive's missing 2022–2026 tail) and
more exchange history. Data beats features from here.
