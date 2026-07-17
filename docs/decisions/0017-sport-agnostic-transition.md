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

---

## Addendum (2026-07-17): founder approval as governing plan; implementation order; F-13 ruling

ADR 0017 is **approved as the governing architecture-hardening plan** (founder,
2026-07-17). S0–S9 are landed; the conceptual-coupling audit and phase report are the
program's closing evidence (`docs/architecture/conceptual-coupling-audit.md`,
`adr-0017-phase1-report.md`); machine-readable finding ownership lives in
`docs/architecture/adr-0017-findings.yaml`.

**Implementation order (founder-fixed):** A2 (ClosePrice) → A3 (backfilled-corpus
replay) → A1 (true-start knowability) → A6 (generic outcome vocabulary) → A4
(adapter-owned cluster key) → A5 (provider/model seam; opaque string competitor
identity; **model-independent OOF orchestration** — fold assignment and OOF production
owned by a crossfit orchestrator, conditional logit never the only leakage-safe
family).

**Hard gates:** A2 and A3 land before any historical-data purchase. A1 lands before
any tennis feature construction or activation.

**F-13 ruling (founder):** a confirmed terminal zero-fill FOK miss does not reserve
the market until settlement — release the reservation when there is no exposure and no
order-state ambiguity, with a governed cooldown/attempt budget if needed. The
settlement-horizon reservation is retained for fills, partial fills, unknown states,
acknowledgement gaps, cancel/replace ambiguity, and reconciliation uncertainty.
Repeated firing from an identical decision snapshot is prevented; retries require a
materially changed market state or an explicitly governed retry condition. Implemented
in its own Phase-3A broker slice, red tests first.

**Standing never-list (reaffirmed):** no tennis model activation, no tennis benchmark
selection, no provider-specific production ingestion, SPEC-084 stays refused, no live
orders.
