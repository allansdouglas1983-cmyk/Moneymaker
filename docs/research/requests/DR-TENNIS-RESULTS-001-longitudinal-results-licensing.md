# DR-TENNIS-RESULTS-001 — Pre-June-2026 longitudinal tennis results licensing (BLOCKING)

**Status:** REQUESTED (BLOCKING) — authorised by the founder 2026-07-18 (Stage-2A
acceptance, decision 5). No results source may be onboarded, scraped, purchased, or
placed in any model path until this research returns with dated citations AND the founder
approves the rights/budget decision. Research findings inform decisions; they never prove
a gate (Amendment A §4).

**Consumer decisions blocked on this:** fundamental model families F2–F6 (Elo, surface
Elo, Bradley–Terry, feature logistic, serve/return); `docs/licensed-sources.yaml` entry;
Gate −1 (SPEC-101) for model training data; the F2+ trial registrations.

**Hard rules bound to this request (founder, verbatim intent):**
- Provider **silence is never permission** — every needed right must be affirmatively
  evidenced in writing (licence text, contract, or provider correspondence).
- A source licensed **non-commercially only** must NOT enter the deployable model path —
  it may at most inform throwaway internal prototyping explicitly marked as
  non-deployable, and even that requires founder sign-off.

## The question

What is the cheapest LAWFUL source (or minimal combination of sources) of **historical
ATP/WTA singles match results and rankings ending before 2026-06-01**, adequate to train
longitudinal player-strength models for **personal profit-seeking use**, with genuine
knowledge-time support?

## Evidence required per candidate provider (all eleven, affirmatively documented)

1. **Personal profit-seeking model-training rights** — the licence permits an individual
   to train models used for their own for-profit betting. Exact licence clause cited.
2. **ATP/WTA singles historical coverage** — tours/levels covered (ATP/WTA main tour,
   Challenger/125, ITF), years available, singles completeness.
3. **Pre-June-2026 backfill** — the full archive is purchasable/retrievable as a
   backfill ending before 2026-06-01 (our training-data boundary).
4. **Knowledge-time fields** — for each field, can what-was-known-when be established
   (publication timestamps, dated snapshots, weekly ranking effective dates)? SPEC-023:
   backfilled sources must declare true publication time.
5. **Rankings / results / statistics coverage** — match winners, scores,
   retirements/walkovers, official rankings & points, and (if any) serve/return
   statistics; which are included at which tier/price.
6. **Retirement / withdrawal treatment** — how retirements, walkovers and withdrawals
   are recorded and distinguished (SPEC-084-adjacent; a source that conflates them
   corrupts labels).
7. **Raw-data retention** — may we retain the raw data locally after any subscription
   ends?
8. **Derived-model retention** — do models trained on the data survive licence
   termination (SPEC-044 derived-model retention)?
9. **Local / private-cloud processing** — is processing on a private cloud workspace/CI
   permitted (our runtime is a remote workspace)?
10. **Smallest pilot or one-off price** — the minimum purchasable unit (one-off backfill
    price preferred over subscription), currency, and total for the coverage in (2).
11. **Minimum commitment** — shortest term, auto-renewal traps, cancellation.

## Candidate classes to investigate (non-exhaustive; rank by evidence, not brand)

Commercial sports-data vendors (e.g. Sportradar, Stats Perform/Opta, Genius Sports and
smaller tennis-specialist feeds), tennis-specific data shops/APIs, betting-data vendors,
and the governing bodies' own data programmes. For each open/community dataset
encountered (e.g. the well-known public tennis results repositories), record its licence
class explicitly and mark it **non-deployable if non-commercial** — do not silently
promote it.

## Deliverables

A comparison table (provider × the 11 evidence points, with citations and dates); the
best 2–3 candidates with their exact licence texts attached/linked; open questions per
candidate that require direct provider contact; a draft provider-contact email for the
founder to send where written clarification is needed; total-cost estimates for the
minimum adequate purchase.

## Acceptance criteria

Every claimed right cites licence text or written provider correspondence (no
inference from marketing pages); prices are current-as-of dated; non-commercial sources
are explicitly flagged; the SPEC-044 permitted-uses vocabulary is used for the rights
mapping.

## Consequences while unresolved

F2–F6 remain blocked (fundamental modelling cannot start). Work that may continue: F0
market-yardstick and F1 structural-null harness (no outcomes, no external data), Packet
follow-ups, and all Stage-2A governance. Work that must pause: nothing currently active
depends on this.

## Budget note

Any results-data cost is NEW spend requiring explicit founder authorisation (SPEC-103
budget separation). The reserved £499 remains earmarked for the Live App Key and is not
available for data.
