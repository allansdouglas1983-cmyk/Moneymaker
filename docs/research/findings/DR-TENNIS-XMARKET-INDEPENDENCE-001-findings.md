# DR-TENNIS-XMARKET-INDEPENDENCE-001 — findings (accepted as evidence input)

**Status:** ACCEPTED WITH LIMITATIONS (founder directive STAGE3-0004 §1).
**Intake record:** `docs/research/requests/DR-TENNIS-XMARKET-INDEPENDENCE-001.md`.
**Blocker resolved:** `EXT-XMARKET-002` → `RESOLVED_AS_UNOBSERVABLE_LIMITATION`
(`specs/programme/xmarket-blockers.yaml`).
Findings inform decisions; they never prove a gate (Amendment A §4).

## Source hierarchy / research date

External founder-run Deep Research. Report accepted 2026-07-21. Official Betfair
documentation is the primary source; the historical-feed limitation is a data-availability
fact.

## Accepted findings (official evidence)

- Betfair supports **within-market cross-selection matching**.
- Betfair's engine is **capable** of cross-market matching.
- Official cross-market matching examples are **football-specific**.
- **No official source** establishes tennis Match Odds ↔ Total Games / Handicap / Set-market
  cross-market matching.
- **ADVANCED Historical Data does not expose** order owner, order origin, synthetic status,
  or internal matching decisions.
- Observed non-redundant movement **does not prove** independent customer order flow.

## Project interpretation (binding)

Derivative prices may **NOT** be represented as: proven independent information; proven
deterministic transformations of Match Odds; or a separate confirmed predictive signal.

Derivative prices **MAY** be used for: market-surface coherence; uncertainty; stale-market
detection; data-quality refusal; abstention diagnostics; down-weighted structural
observations whose origin remains **unresolved**.

## Unresolved facts

- The internal origin of tennis derivative-market orders is **unresolved** and, from the
  historical feed, **unobservable**.
- The `crossMatching` flag is **metadata only** — `true` does not establish cross-market
  matching; `false` does not prove independent customer flow. It cannot establish mechanism.

## What the report does NOT prove

- It does not establish tennis cross-market matching (only football examples exist).
- It does not make derivative movement an independent predictor.
- It does not permit any price to receive increased predictive authority via an independence
  claim.

## Implementation consequences

- The independent-signal hypothesis is **closed**:
  `CROSS_MARKET_LATENT_INDEPENDENT_SIGNAL_V1` → `NO_GO_UNPROVEN_INFORMATION_ORIGIN`
  (`specs/programme/cross-market-independent-signal-closure-v1.yaml`).
- The replacement hypothesis `CROSS_MARKET_COHERENCE_V1` uses coherence as a **market-quality
  / uncertainty / abstention diagnostic only** — never a predictor, tip, edge or final
  probability.
- A governed cross-matching **evidence policy** replaces any independence claim with the
  four statuses `OBSERVABLY_NON_REDUNDANT_UPDATES / OBSERVABLY_REDUNDANT_PATH /
  ORIGIN_UNRESOLVED / INSUFFICIENT_ACTIVITY`; there is **no `INDEPENDENT` status**
  (`specs/evidence/cross-matching-evidence-policy-v1.yaml`).
