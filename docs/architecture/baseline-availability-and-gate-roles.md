# Baseline availability and gate roles (governed clarification, 2026-07-18)

**Founder directive, Stage 2B §1.** Outcome-blind wording clarification; nothing here
weakens or redefines `p_market_info`, and no gate is silently altered (the paired
pre-registration amendment is Amendment 3 in `docs/experiments/
STAGE2-tennis-preregistration.md`).

## Which comparator genuinely exists, per evaluation period

| Period | Betfair `p_market_info` (governed) | Model-vs-model comparators | Tennis-Data bookmaker odds |
|---|---|---|---|
| Pre-June (warm-up / OOF 2019-01→2025-05 / validation 2025-06→2026-05) | **DOES NOT EXIST** — no Betfair prices were purchased for this period | EXIST: F2-vs-structural-null; later F3-vs-F2 | present in files, **QUARANTINED — never a proxy for the Betfair baseline** |
| June 2026 (sealed lockbox; F2-eligible 1,218) | EXISTS — F0 produces it from the frozen June corpus under the frozen decision policy | EXIST | irrelevant and quarantined |

## Binding consequences (frozen)

1. The 34,046 pre-June evaluation observations are **never** described as powered
   evidence of improvement over Betfair: no Betfair baseline exists for those matches
   and horizons.
2. The declared δ = 0.0007 nats is **not** used to claim a pre-June market-relative
   pass. Pre-June, δ and the 26,600 / 41,039 planning table apply only to comparators
   that genuinely exist there — **challenger-vs-baseline-model comparisons**
   (F3-vs-F2 confirmatory, and any registered model-vs-model endpoint). The table is
   hereby labelled: *"N required for a model-vs-model paired comparison at δ, σ_d;
   pre-June periods support model-vs-model only; market-relative comparisons exist
   only where F0 exists (June)."*
3. `p_market_info` keeps its frozen governed definition (specs/prices info-price
   family); Tennis-Data odds fields remain quarantined and are never substituted,
   scaled, or blended into it.

## Frozen evidence roles

**M1 — Probability adequacy** (pre-June OOF + chronological validation): model
coherence; proper-score quality (log loss, Brier); calibration (in-the-large, slope,
reliability bands); temporal stability; coverage and exclusions; challenger-vs-baseline
**model** comparisons where the comparator genuinely exists. **No claim of superiority
to Betfair is possible at M1 — there are no Betfair prices pre-June.**

**M2 — Market comparison** (model probability vs governed Betfair `p_market_info`):
June 2026 is the first available market-comparison block; its F2-eligible count is
1,218, so an underpowered June result **remains CONTINUE / INCONCLUSIVE** — never
represented as independently powered; Tennis-Data bookmaker odds are never a proxy.

These roles bind every report, ledger entry and gate evaluation from this point on.
