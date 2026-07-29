# TE-0033 — composition vs sharpening: neither clears, and the model's own edge held

Harness `tennis_edge/experiments/regime_decomposition.py`, declarations committed before
the run. 44,986 joined rows, eras 2016–2023 vs 2024–2026, eight declared strata, exact
Oaxaca identity, day-clustered 95% CIs.

## Q1 — the model's gain over the exchange baseline (the edge that matters)

| component | estimate | CI 95% |
|---|---|---|
| Δ (POST − PRE) | **+0.000336** | [−0.000851, +0.001501] spans zero |
| composition | −0.000040 | [−0.000150, +0.000056] spans zero |
| within (sharpening) | +0.000375 | [−0.000817, +0.001552] spans zero |

**The model's residual edge did not decline after 2023.** The point estimate is mildly
positive, and the composition channel is a precisely-measured nothing (its CI is ±0.0001).
Whatever changed at 2023/24, it was not the mix of matches, and it did not eat the model's
gain over the exchange price.

## Q2 — the exchange's informativeness over Bet365 (the anchor comparison)

Δ −0.000619 [−0.001662, +0.000352]; composition +0.000013 (nil); within −0.000632
[−0.001662, +0.000344]. All span zero. Directionally this is TE-0019's "anchor advantage
halved" seen again — the exchange price's lead over Bet365 shrank within strata — but at
95% it does not clear, so it stays a direction, not a finding.

## Reading, per the declared rule

Both questions: **MIXED / UNRESOLVED** — no component clears. The useful knowledge is
still substantial:

1. **Composition is exonerated with precision.** Both composition CIs are an order of
   magnitude tighter than the within CIs and centred on zero. The post-2023 diagnostics
   were never about the archive's mix changing.
2. **The three earlier diagnostics concerned the anchor, not the model.** The model's own
   out-of-fold gain (Q1) is stable across the break — consistent with TE-0032's untouched
   window showing a historical-sized gain. The thing that weakened is the exchange price's
   *relative* lead over the bookmaker (Q2, directionally), which is about the anchor
   choice, not the edge.
3. **No stratum stronghold exists.** The per-stratum persistence map shows no cell whose
   post-2024 gain is reliably above the pool (the largest, WTA slam underdog-priced,
   sits on n=349). Nothing here motivates a stratum-restricted serving registration.

Diagnostic only, one run, recorded as declared. No serving rule changes.
