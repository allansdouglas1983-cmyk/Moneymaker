# ADR 0017 — Tennis-first sport-agnostic platform transition (founder program)

**Status:** ACCEPTED as a program, 2026-07-16 (founder directive, verbatim scope
below). Supersedes the SCOPE of ADR 0016's minimal-change proposal — the founder has
authorised a deeper transformation: the platform becomes the **Betfair Exchange
Research Platform with Sport Modules**; horse racing is preserved as one sport
adapter; pre-match tennis becomes the first new empirical implementation *later*,
after data. ADR 0016's analysis (what is sport-agnostic vs sport-specific) remains
valid input; its "avoid renames" posture is replaced by this directive's Phase 11
("rename what unnecessarily embeds horse racing; preserve git history; avoid churn").

## The program (founder's 12 phases, condensed)

1. **Adversarial architecture audit** — find every horse-racing assumption. Report
   first, change nothing.
2. **Generalise** — Core Platform → Sport Adapter → Feature Provider → Probability
   Model → Market Combination → Execution → Settlement → Evidence → Analytics.
   Nothing in core knows the sport.
3. **Tennis domain model** — immutable, versioned CONTRACTS only (Match, Player,
   Tournament, Surface, Round, BestOf, retirement/walkover/qualification statuses,
   market/prediction snapshots, settlement/execution outcomes). No algorithms.
4. **Probability interfaces** — contracts only, no implementations.
5. **Model interfaces** — contracts for future Surface Elo / Weighted Elo /
   Bradley-Terry / regularised LR / Bayesian / GBM / ensembles. No model exists yet.
6. **Feature registry** — versioned registry design (name, description,
   knowledge-time, licensing status, source, missing-data behaviour, deterministic
   definition, version, evidence status). No features implemented.
7. **Evidence registry** — future experiments (market-only, Surface Elo, Weighted
   Elo, Bradley-Terry, combined) plugging into the EXISTING gate framework.
8. **Tennis settlement contracts** — completed / walkover / retirement before and
   after set one / disqualification / cancelled / postponed / surface change.
   Final empirical policy deferred pending data (modelled as explicit refusal
   states + `planned` enforcement, never a TODO literal — the escape-hatch ban in
   money/evidence modules stands).
9. **Market abstractions** — Match Odds now; Set Winner / Correct Score / Game
   markets as future variants. Only Match Odds will be enabled.
10. **Benchmark interfaces** — final midpoint / windowed midpoint / WAP /
    microprice as future implementations. NO benchmark chosen; selection stays
    evidence-driven after pilot data (DR-TENNIS-BENCHMARK-001 is unresolved).
11. **Repository cleanup** — rename what unnecessarily embeds racing; preserve git
    history; no aesthetic churn.
12. **Documentation** — ADR, repo map, architecture diagram, migration rationale,
    open/blocked decisions, data-dependent work, risk register, licensing questions.

## Hard boundaries (founder's never-list, additive to CLAUDE.md's)

No tennis model implementations; no invented datasets or fabricated schemas; no
probability estimates; no simulated fake markets; no fabricated ATP data; no
scraping; no weakening of the deterministic architecture; no removal of horse
racing; no customer features/dashboards; no betting implementation. Everything
requiring purchased data, provider licences, empirical validation, benchmark
selection, or gate evaluation REMAINS BLOCKED (ADR 0015 and the research ledger
govern those).

## Standing-rule interactions (recorded so no rule silently bends)

- The three rules bind every phase. Adversarial-review findings may be implemented
  "where appropriate" per the directive — but a change to any committed test still
  ships as its own governed slice with the SPEC-ID cited.
- **Test-correction 0002 remains UNAPPROVED** and is NOT implicitly approved by this
  directive. Repo-wide `make verify` is red on that property until the founder
  rules; the refactor needs a green baseline (see the Phase-1 report's blocker
  section).
- SPEC texts are edited only where the requirement itself unnecessarily embeds
  racing; money/evidence requirement SEMANTICS are never diluted. Manifest changes
  remain enforcement-increasing or founder-directed.
- Phase 3A (offline broker) continues in parallel — it is already sport-agnostic.
