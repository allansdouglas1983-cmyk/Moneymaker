# STAGE3-0005 — Founder Return (synthetic coherence engine + mutation hardening)

Authority: founder directive STAGE3-0005. Branch: `claude/project-files-followup-dif8al`.
Standing constraints observed: £0 new spend; no purchase/API/bet/execution/deposit/account
action; no outcomes/winners/settlement/ROI/P&L/CLV/EV/tips read or computed; June is
development data forever; `p_market_info` authoritative — **no coherence output changes it**;
promoted `xmarket_contracts` plumbing remains STAGED (import-quarantined from execution AND
pricing/tipping); the synthetic math engine is quarantined from real ingestion and V0; **NO real
June coherence run performed**; **NO numerical latent implementation beyond the synthetic engine**.

---

## A. Governance (committed)

1. **STAGE3-0004 closed** — `specs/programme/stage3-0004-closure-record-v1.yaml`.
2. **EXT-XMARKET-003 → SPECIFICATION_ACCEPTED_IMPLEMENTATION_VALIDATION** with five
   `not_fully_resolved_until` conditions — `specs/programme/xmarket-blockers.yaml`.
3. **DR-TENNIS-XMARKET-MATH-001 findings accepted** with the five binding §2 corrections —
   `docs/research/findings/DR-TENNIS-XMARKET-MATH-001-findings.md`.
4. **CROSS_MARKET_COHERENCE_V1 registered** (implementation registration) —
   `specs/programme/cross-market-coherence-v1.yaml`: format vocabulary, format-evidence policy,
   identification inputs, holdout reservation, first-server nuisance treatment, structural
   refusals, synthetic-only quarantine.

## B. Synthetic math + identification engine (committed, `sport_tennis/coherence/`)

All modules are SYNTHETIC-ONLY, deterministic, read no prices and no outcomes, and are
import-quarantined (make-verify lines) from `l5_decision/l5b_risk/l6_broker/l7_settle/
assistant_v0/research.xmarket`, and are imported by neither `assistant_v0` nor `l4_pricing`.

5. **`formats.py`** — immutable `MatchFormat` vocabulary (§10); `FORMAT_UNRESOLVED`/
   `UNSUPPORTED_FORMAT`; never defaults to best-of-three. Match-tiebreak decider credits a
   verified synthetic game count (NOT a Betfair settlement claim — that is EXT-XMARKET-003).
6. **`scoring.py`** — production game / tiebreak / set generators by dynamic programming with
   exact closed-form win-by-two tails; normalized PMFs; refuses non-`(0,1)` inputs.
7. **`match.py`** — production full-match forward DP (serve carry, match-TB decider); match-win
   probability + total-games PMF + game-margin PMF for fixed players A and B.
8. **`pmf.py`** — Over/Under (§9) and Asian game-handicap cover with **explicit integer-line
   PUSH mass** and half-line handling; lines are exact `Decimal` multiples of 0.5 (no float
   line arithmetic); expected total and expected margin.
9. **`solver.py`** — the ONE fitting definition (§2.3): a **deterministic bounded 2-D root
   solve** — fixed coarse residual scan → clustered seeds → nested-grid pre-polish → damped
   Newton polish with the numeric identification Jacobian. First server is a **nuisance
   parameter** (§2.4): dual-evaluate A-first / B-first, **no 50/50 prior**, union of solutions.
   Emits ONLY the permitted §15 structural statuses.
10. **`holdout.py`** — projects an identified origin onto the reserved holdout lines (§2.2 / §15)
    and reports **raw metrics only** (model-implied range, observed interval / midpoint, signed
    interval violation, canonical-ladder tick-distance, first-server range, line, market type).
    No categorical coherence verdict; statuses `HOLDOUT_SURFACE_AVAILABLE` /
    `HOLDOUT_SURFACE_UNAVAILABLE` / `ORIGIN_UNRESOLVED`.
11. **`format_evidence.py`** — tiered format-evidence policy (§11): tier A/B may establish the
    full format; tier C may establish **match length only**; price/outcome sources are refused;
    never defaults to best-of-three.

## C. Independent mathematical verification (§2.5) — mandatory, met

12. **`reference.py`** (test-only) — an independently-structured re-derivation of every
    production quantity: closed-form game polynomial (vs production DP), truncated tiebreak
    recursion (vs closed-form tail), backward set recursion AND top-down set distribution (vs
    forward DP), depth-first match recursion (vs forward DP).
13. **Production == reference to 1e-9** across game / tiebreak / set / match-win / total-games
    PMF / game-margin PMF / Over-Under / handicap-cover over a governed input grid. A
    discrepancy is `STOP_MATH_INTEGRITY`; none occurred. Test suites: `test_scoring_core.py`
    (19), `test_match_and_pmf.py` (24), `test_pmf_direct.py` (8), `test_solver.py` (11),
    `test_holdout.py` (12), `test_format_evidence.py` (13) — all pass.

## D. Structural mathematical findings (honest, synthetic)

14. **Mirror identification degeneracy.** From Match-Odds + ONE Total-Games line, `(p_a,p_b)`
    and its mirror `(1−p_a,1−p_b)` produce an IDENTICAL total-games distribution and a
    COMPLEMENTARY match-win probability. A match is point-identified only when its mirror pair
    lies OUTSIDE the parameter domain; **symmetric / near-symmetric matches are NOT
    point-identified** (`MULTIPLE_ROOTS`). The parameter-domain lower bound therefore does real
    identification work — directly relevant to the founder-pending domain choice
    (`[0.30,0.90]` vs `[0.35,0.90]` vs `[0.40,0.90]`).
15. **Saturation non-identifiability.** A near-certain match (match-win → 1) saturates match-win;
    the identification Jacobian is singular and the solver honestly returns `NON_IDENTIFIABLE`
    rather than over-claiming a precise `(p_a,p_b)`.

## E. Discipline artefacts

16. **PEP-563 annotation architecture proof** (§7) — `test_annotation_architecture.py` statically
    proves every `xmarket_contracts` and `sport_tennis/coherence` production module activates
    postponed annotations and consumes no annotations at runtime (no `get_type_hints` /
    `__annotations__` / pydantic), making the `PEP563_TYPE_ANNOTATION_OPERATORS` mutation class
    genuinely equivalent.
17. **Synthetic mutation bar** (§16) — core module `sport_tennis/coherence/scoring.py`:
    **1041 mutants, 905 killed / 136 survived (86.9%)** against the fast test subset. Three
    honest hardening rounds (85.0 → 85.8 → 86.9%) killed every behavioural serve-order and
    games-distribution mutant found: (a) made the reference serve order INDEPENDENT of
    production (it had shared `tiebreak_server_is_first`), (b) added a full set-distribution
    cell-by-cell agreement test. Residual 136 survivors classified in
    `specs/mutation-survivors-coherence-v1.yaml` (55 lead-proposed EQUIVALENT with reachability
    proofs; **80 DP_ARITH_OR_LOGIC_UNPROVEN — NOT claimed equivalent**, incl. one `AddNot`
    serve-flip requiring a symmetry proof or killing test), all `approved_by: null`. The
    advice-critical bar is **NOT YET MET and recorded honestly**; it need not be met here (the
    engine is synthetic-only, quarantined, no real run). Full per-survivor evidence in
    `docs/evidence/.../COHERENCE_SCORING_MUTATION_SURVIVORS.json`. Kill rate is a LOWER BOUND —
    the full suite's match/PMF full-PMF agreement (excluded per-mutant for runtime) kills more.
18. **Survivor extractor tooling** — `tools/extract_mutation_survivors.py` (read-only) generates
    the per-survivor packet from a cosmic-ray session for founder adjudication.

## F. Guardrails held / NOT done (by design)

19. No real-data coherence run; no outcomes; the numerical latent layer stays blocked by
    EXT-XMARKET-003 until it fully resolves and the founder separately authorises.
20. `p_market_info` remains authoritative; no coherence output feeds pricing, tipping, V0 or
    execution — proven by the import quarantine in `make verify`.
21. No LLM created, altered, smoothed or priced any probability; all numbers come from
    deterministic tested code; the reference generator is the independent check, not an LLM.

## G. Remaining founder-adjudication deliverable (§5/§6/§8) — status

22. The **final `xmarket_contracts` mutation survivor packet** (18-field per-survivor JSON +
    class index + one-to-one reconciliation) and the bounded hardening (killing every
    observable-changing survivor among the 120 non-annotation survivors) build on the
    STAGE3-0004 record (`specs/mutation-survivors-xmarket-contracts.yaml`: 588 mutants, 66
    PEP-563-equivalent, 120 pending). The extractor tooling (item 18) is now in place to
    generate it. **The advice-critical 100%-killed-or-approved bar remains NOT YET MET** — the
    packet is the next step and is offered for founder adjudication as prepared.

## H. Verification

23. `make verify` — **GREEN**: 664 tests pass; ruff ARG clean; pylint W0613 10/10; escape-hatch
    greps clean; all import quarantines OK (incl. the 7 new `sport_tennis.coherence` lines);
    `mypy --strict .` success across 175 source files.
24. Import quarantines for `sport_tennis.coherence` — all pass (7 lines added to the Makefile).
25. Nothing exposed: staged plumbing unexposed; no June diagnostic run; awaiting founder
    mutation adjudication per the directive's closing instruction.
