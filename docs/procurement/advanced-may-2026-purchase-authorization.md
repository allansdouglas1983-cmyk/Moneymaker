# May 2026 ADVANCED market-development purchase — AUTHORISATION + handoff (Stage 2D §4)

> **WITHDRAWN 2026-07-18 (Stage 2E).** The May 2026 ADVANCED purchase authorisation is
> REVOKED — no historical-data purchase is authorised. Superseded by
> specs/programme/june-evidence-plan-amendment-v1.yaml (use the existing June corpus first).
> Retained only as an audit record.


**Founder authorisation, 2026-07-18.** One targeted historical-market development month is
authorised for fitting the frozen SPEC-032 combination (development data only — not a new
model-family search, not confirmatory evidence).

## Authorised order (exact)

| Field | Value |
|---|---|
| Provider | Betfair Historical Data |
| Sport | Tennis |
| Tier | **ADVANCED** |
| Period | **1–31 May 2026** |
| Market programme | MATCH_ODDS, singles |
| Quantity | **one calendar month only** — no bulk package |
| **Maximum authorised displayed price** | **£49** |

## Who executes the purchase — NOT the agent

Per **ADR 0015** (point 2: "the agent performs none of these at any time"; the CLAUDE.md hard
prohibition on all Betfair account activity) and the environment prohibition on any Betfair
account/credential/secret access: **the agent does not and cannot make this purchase.** The
**founder personally** completes it through the Betfair Historical Data portal under their own
restored account (ADR 0015 addendum point 4 — the ADVANCED purchase may proceed once lawful
account access is confirmed, which this directive constitutes). The agent's role is limited to
**preparing the pre-purchase checklist** and **ingesting the local files** the founder provides.

## Pre-purchase checklist (founder confirms at the portal, before paying)

1. The displayed price is **£49 or less**. **If it exceeds £49 — stop and report. Do not purchase.**
2. It is **one month only** (May 2026) — no additional month and no package selected.
3. Tier = ADVANCED; Sport = Tennis; market type = MATCH_ODDS; singles.

## Month selection is outcome-blind

May 2026 is chosen solely because it is the **immediately preceding complete calendar month**
before the sealed June lockbox. No outcome, return, ROI, CLV, or model-performance signal was
used. **Do not substitute April** unless May is technically unavailable or materially defective
for a **metadata-only** reason — and that reason must be returned before any substitution.

## Handoff to ingestion (Stage 2D §5–§7, blocked until files arrive)

Once the founder has purchased May and placed the download in the session (e.g. under the
scratchpad or a named path, with the original preserved byte-for-byte outside the repo), the
agent will execute, in order:

- **§5 acquisition + ingestion:** preserve original bytes; sorted SHA-256 file manifest + manifest
  hash; record portal order details + retrieval timestamp; combined-vs-per-market packaging audit;
  canonical replay dedup (as June); derive May MATCH_ODDS singles universe by frozen rules
  (marketTime, not folder path); preserve every exclusion; deterministic replay ×2 byte-identical.
- **§6 market-development block:** frozen F0 `COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE` (W=60s, L=300s,
  info-price-v2); strictly prequential raw global-Elo F2 (only pre-match TD data; same-day batch;
  calibration from prior lawful data only); governed td-norm-v1 identity join (no guessed
  corrections); governed F0-valid ∩ F2-valid ∩ calibrated ∩ outcome-eligible intersection; every
  exclusion retained; Tennis-Data odds columns never read.
- **§7 SPEC-032 fit:** deterministic MLE of one pooled α and one pooled β on the May development
  intersection only (no per-tour/surface/interaction coefficients, no method contest, no June, no
  odds); frozen init/constraints/optimizer/convergence/seed; report α, β, uncertainty,
  convergence; freeze α, β into an immutable combination-model version; no refit after June opens.

**No purchase has occurred. No May data is in the repository. §5–§7 cannot run until the founder
provides the purchased files.** May sporting outcomes may be used **only** for the registered
development fitting (May is outside the June lockbox — lawful pre-June development data); no ROI,
P&L, CLV, EV, or selection analysis, ever.
