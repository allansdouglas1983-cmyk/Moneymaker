# STAGE3-0004 — RETURN (cross-market research intake, governance, contracts, plumbing hardening)

Governance + contracts + production-hardening of critical data plumbing only. **No numerical
latent model was implemented** (blocked by `EXT-XMARKET-003`). No outcomes, no tips, no EV/
ROI/P&L/CLV/stakes, no data purchase, no execution. Branch `claude/project-files-followup-dif8al`.

## 1. Research-intake records and digests
- `docs/research/findings/DR-TENNIS-XMARKET-SETTLEMENT-001-findings.md` — sha256 `151956b062968c6d…`
- `docs/research/findings/DR-TENNIS-XMARKET-INDEPENDENCE-001-findings.md` — sha256 `6d94aa2be522d84e…`
  (source hierarchy, research date, accepted findings, unresolved facts, interpretation, what
  the reports do NOT prove, implementation consequences; raw marketType / semantic confidence /
  official-name-verification status kept as separate fields).

## 2. Updated blocker statuses (`specs/programme/xmarket-blockers.yaml`)
- `EXT-XMARKET-001` (settlement semantics) → **RESOLVED_WITH_EXCLUSIONS**.
- `EXT-XMARKET-002` (information origin) → **RESOLVED_AS_UNOBSERVABLE_LIMITATION**.
- `EXT-XMARKET-003` (exact mathematical + format specification) → **OPEN** (new; blocks all
  numerical implementation).

## 3. Settlement-semantics v2 digest
- `specs/evidence/tennis-derivative-settlement-semantics-v2.yaml` — sha256 `196576426a79f9e5…`
  (every unresolved item preserved explicitly; MATCH_ODDS primary; COMBINED_TOTAL/HANDICAP
  usable-with-exclusions; SET_* deferred; SET_CORRECT_SCORE + TOURNAMENT_WINNER prohibited).

## 4. Independent-signal hypothesis closure
- `specs/programme/cross-market-independent-signal-closure-v1.yaml` — sha256 `2ed07b94c411b43a…`
  `CROSS_MARKET_LATENT_INDEPENDENT_SIGNAL_V1` → **NO_GO_UNPROVEN_INFORMATION_ORIGIN**.

## 5. CROSS_MARKET_COHERENCE_V1 registration
- `specs/programme/cross-market-coherence-v1-registration.yaml` — sha256 `913219d612e4ebb1…`
  Coherence diagnostic only (not a predictor/tip/edge/final-probability); permitted output
  statuses listed; no numeric coherence score affects the final V0 probability/tip.

## 6. Exact initial supported market types
MATCH_ODDS, COMBINED_TOTAL, HANDICAP. Deferred: SET_WINNER, SET_BETTING, NUMBER_OF_SETS,
PLAYER_A_WIN_A_SET, PLAYER_B_WIN_A_SET. Excluded: SET_CORRECT_SCORE, TOURNAMENT_WINNER.

## 7. Exact initial supported cohort
June F0-committed singles Match Odds, **STRICT** cohort, correctly linked COMBINED_TOTAL and/or
HANDICAP sibling, available ≤ the exact F0 decision timestamp, OPEN, pre-match, not suspended,
parseable, two-sided, not crossed, valid line, verified semantics, no later prices.
`PRIMARY_ONLY_TIER` **unsupported** (June: 0/559). Quote-age policy unresolved; sensitivities
still reported at 15/30/60/120/300 s.

## 8. Outcome-evaluation exclusion policy
Normally-completed only; excludes walkover / withdrawal-DNS / retirement / disqualification /
abandonment / incomplete / format change / cancelled-relisted / ambiguous / conflicting source.
Keyed on **match-completion status**, not per-derivative settlement. Report separately the
pre-match coherence-constructible count and the outcome-evaluable count.

## 9. Audit-code promotion assessment
`docs/evidence/stage3-cross-market-audit/PROMOTION_ASSESSMENT.md`: components 1–8 (parsers,
linkage, as-of-F0 synchronizer, two-sided validator, quote-age, provenance/observation)
**PROMOTE_AFTER_HARDENING**; book-quality arithmetic + redundancy co-timing
**KEEP_RESEARCH_ONLY**; run_audit driver **DELETE_AFTER_EVIDENCE_FREEZE**; coherence numerical
layer **BLOCKED_BY_MATH_SPEC**.

## 10. Neutral coherence input contracts
`xmarket_contracts/observation.py`: `CrossMarketObservation` + `CrossMarketObservationSet` —
NO latent parameter / p_A / p_B / coherence score / final probability / tip; raw marketType
preserved; optional quality fields default None (no fitted maths); immutable digest +
deterministic serialization.

## 11. Cross-matching evidence policy
`specs/evidence/cross-matching-evidence-policy-v1.yaml` — sha256 `8d083d61d63f9f7a…`. Statuses
OBSERVABLY_NON_REDUNDANT_UPDATES / OBSERVABLY_REDUNDANT_PATH / ORIGIN_UNRESOLVED /
INSUFFICIENT_ACTIVITY. **No `INDEPENDENT` status.** `crossMatching` flag is metadata only.

## 12. V0 integration status
`assistant_v0/html_report.py` gains an optional cross-market research diagnostic under the
banner **"CROSS-MARKET RESEARCH DIAGNOSTIC — NOT USED IN THE FINAL PROBABILITY"** (availability,
quote age, sync status, market-type presence, settlement-semantics status, origin-unresolved
warning, research-only summary). It shows no latent/coherence/tip/probability-adjustment; the
final V0 probability remains **market-only** and is unaffected.

## 13. Tests, mutation and verification results
_(mutation numbers + full make verify filled below.)_

## 14. Remaining EXT-XMARKET-003 questions
Exact point→game→set→match equations; best-of-3; best-of-5; standard tiebreak; final-set
tiebreak; match-tiebreak formats; server-order treatment; exact expected-total-games
distribution; exact game-handicap distribution; deterministic format identification from
pre-match data; objective function; constraints; uncertainty and sensitivity method.

## 15. Confirmation — no latent mathematics implemented
Confirmed: no serve model, no O'Malley/Barnett equations, no line selection, no liquidity
weights, no latent parameters. `xmarket_contracts` is plumbing + neutral contracts only.

## 16. Confirmation — no outcome/profit/tip analysis
Confirmed: no outcomes read; no ROI/P&L/CLV/EV/stake/tip; observation contracts and V0 output
carry no such fields (structural).

## 17. Confirmation — no paid action
Confirmed: £0 spend; no purchase, API call, bet, deposit, account action, or execution.
