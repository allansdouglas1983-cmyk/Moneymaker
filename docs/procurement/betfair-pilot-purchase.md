# Betfair ADVANCED pilot purchase — specification and rationale

**Authorised:** 2026-07-16 by the founder — £69, separately authorised research
expenditure (SPEC-103: distinct from the £499 Live App Key reserve, which remains a
later conditional purchase requiring fresh approval after Gates 1–2).

## Selected pilot month: January 2026

Selection criteria (founder decision 2): most recent complete, representative,
high-volume WINTER calendar month under the frozen cohort (GB all-weather WIN).
Rationale, documented BEFORE purchase, with **no model performance inspected** (none
exists — no model has ever seen market data):

- January is deep winter: the GB racing calendar is at its most all-weather-dominated,
  so the month maximises in-cohort races per pound.
- The official BHA 2026 Fixture List shows fixtures across all six AW tracks
  (Lingfield, Kempton, Wolverhampton, Southwell, Newcastle, Chelmsford) through
  January 2026 — no evidence of anomalous cancellation clusters; AW is the
  weather-resilient code, so winter disruption risk mostly affects turf.
- January 2026 is a complete 31-day month, fully outside any future experiment
  window decision (the pilot cohort is pre-registered as PILOT and excluded from the
  EXP-0001 corpus by construction).
- More recent complete months (Feb–Jun 2026) were considered: Feb is winter but
  shorter (28 days); Mar–Jun trend into turf season, diluting the AW cohort. The
  founder's January default stands; no anomaly found requiring an alternative.

**Authoritative pre-purchase coverage check (operative step, on the portal):** before
paying, use the Historical Data portal / `GetCollectionOptions`-`GetDataSize` flow to
confirm the January 2026 Horse Racing ADVANCED selection filtered to
country=GB, marketType=WIN returns a plausible file/market count (rough expectation:
~180–280 GB AW WIN races in a January; a count far outside that range = stop and
report before purchase). This check uses metadata counts only — no market data, no
prices, no outcomes are inspected.

## Exact purchase specification

| Field | Value |
|---|---|
| Account | Founder's Betfair.com account (service is customers-only; billed to account statement) |
| Plan | **ADVANCED** |
| Sport | **Horse Racing** (packages are per-sport; subsets are not separately priced) |
| Data month | **January 2026** (single month) |
| Price | **£69.00** (statement line: `ADVANCED Horse Racing Jan 2026`) |
| Download filter (post-purchase) | `countriesCollection: ["GB"]`, `marketTypesCollection: ["WIN"]`, `fileTypeCollection: ["M"]` |
| Purpose | Pilot: pipeline validation (l0→l3→snapshots→replay on real mcm files), p_market_info infrastructure, ADVANCED schema verification (1s cadence, best-3 levels, trd/tv behaviour), and the pre-registered σ_d pilot once form data exists |

## Handling constraints (founder decision 3 — binding until Betfair answers in writing)

- **Local-only processing.** Purchased raw files are stored and processed on local
  infrastructure only. They MUST NOT be uploaded to third-party CI, cloud storage, or
  any hosted service. No raw-data-derived fixture may enter this repository or its
  CI while the cloud/CI rights question is open.
- The SPEC-044 registry entry for this source (when created, after
  test-correction-0001 is decided) marks `cloud_processing` and
  `third_party_ci_processing` as NOT granted.
- The two written questions to Betfair developer support remain outstanding:
  (1) is private cloud/third-party-CI processing of purchased files permitted for a
  personal-use buyer; (2) is private automated betting using models trained on the
  data within personal use.

## What this purchase does NOT authorise

No further months, no PRO tier, no Live App Key, no live credential, no order of any
kind, no EXP-0001 registration (blocked on form data), no lockbox definition.
