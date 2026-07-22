# DR-TENNIS-XMARKET-SETTLEMENT-001 — findings (accepted as evidence input)

**Status:** ACCEPTED WITH LIMITATIONS (founder directive STAGE3-0004 §1).
**Intake record:** `docs/research/requests/DR-TENNIS-XMARKET-SETTLEMENT-001.md`.
**Blocker resolved:** `EXT-XMARKET-001` → `RESOLVED_WITH_EXCLUSIONS`
(`specs/programme/xmarket-blockers.yaml`).
Findings inform decisions; they never prove a gate (Amendment A §4).

## Source hierarchy / research date

External founder-run Deep Research. Report accepted 2026-07-21. Official Betfair Exchange
tennis rule text is the primary source; June-2026 rule-text byte identity is **not yet
verified**, but the research found **no semantic change** relevant to the June corpus.

## Accepted findings — market classification (normally completed matches)

- **MATCH_ODDS** — verified **primary** match-winner market.
- Usable **only as auxiliary structural markets, only under explicit match-level
  exclusions**: `SET_WINNER`, `SET_BETTING`, `NUMBER_OF_SETS`, `COMBINED_TOTAL`,
  `HANDICAP`, `PLAYER_A_WIN_A_SET`, `PLAYER_B_WIN_A_SET`.
- **Excluded**: `SET_CORRECT_SCORE` (exact contract unresolved); `TOURNAMENT_WINNER`
  (wrong event granularity for a single-match model).

## Accepted findings — global evaluation exclusion policy

**EXCLUDE:** walkover; withdrawal / did-not-start; retirement at any stage; disqualification;
abandonment; incomplete match; post-load scoring-format change; cancelled-and-relisted
market instance; ambiguous result; conflicting outcome source.
**INCLUDE:** normally completed matches; venue or surface changes where the match otherwise
completes normally.

Exclusion MUST be keyed on **match-completion status**, not merely whether an individual
derivative market received a settlement.

## Unresolved facts

- Exact `SET_CORRECT_SCORE` contract.
- June-2026 official rule-text byte identity (no semantic change found, but not byte-verified).
- Asian half/whole-line win/half-win/push micro-semantics are recorded at the classification
  level (VERIFIED_CONTRACTUALLY_DIFFERENT_BUT_USABLE_WITH_EXCLUSIONS) and remain part of the
  math/format spec (`EXT-XMARKET-003`).

## Project interpretation

The settlement blocker is resolved **with exclusions** for the V1 supported set (MATCH_ODDS,
COMBINED_TOTAL, HANDICAP). These are compatible with completed-match evaluation under the
exclusion policy above. The settlement matrix is versioned in
`specs/evidence/tennis-derivative-settlement-semantics-v2.yaml`, preserving every unresolved
item explicitly.

## What the report does NOT prove

- It does not prove `SET_CORRECT_SCORE` semantics (prohibited from V1).
- It does not make `TOURNAMENT_WINNER` suitable for a single-match layer (prohibited).
- It does not authorise reading any June outcome; completion status must be established
  through the governed outcome path, not inferred from a derivative settlement.
- It does not authorise the numerical model (that is `EXT-XMARKET-003`).

## Implementation consequences

- Settlement registry v2 created; blocker `EXT-XMARKET-001` → `RESOLVED_WITH_EXCLUSIONS`.
- Outcome evaluation (future) uses the label-safe subset (§6): normally completed only.
- Raw `marketType`, observed selection structure, semantic confidence, and official-name
  verification status are kept as **separate** fields — inferred display names are never
  silently promoted to verified official names.
