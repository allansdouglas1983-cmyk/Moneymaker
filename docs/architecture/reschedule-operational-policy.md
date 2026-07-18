# Reschedule operational policy (Stage-2A Task 5) — RECOMMENDATION

**Status:** RECOMMENDED 2026-07-18, pending founder ratification into a baseline-v2
`markettime_protocol` update (baseline-v1 left this item explicitly UNFROZEN). Chosen using
**only** Stage-1 evidence and **only** the four permitted criteria — operational
consistency, live replicability, deterministic replay, governance. Profitability, betting
outcomes, CLV and hindsight were not used and must never be used to choose it.

## The problem, from Stage-1 evidence

The governed marketTime state machine mints an immutable horizon instance on every crossing
and re-arms on schedule revision. Stage 1 measured (primary singles): median **6** non-monotone
marketTime revisions per market; the *first* T-60s crossing sits a median **25 min** before
the real off; **1,306 / 2,876** markets produce multiple T-60s instances; the off is a median
**+5.7 min** late even vs the *final* published schedule. So a market typically presents its
"N minutes to off" horizon **several times**, and the first presentation is usually **not**
close to the true off. A live system must decide *which* crossing it acts on — deterministically,
knowing only the past.

## Candidates and assessment (four criteria only)

| Candidate | Operational consistency | Live-replicable | Deterministic replay | Governance |
|---|---|---|---|---|
| **First crossing** | one decision, but systematically mistimed (median 25 min early at T-60s) | yes | yes | simple, but acts on a schedule the market revises ≥6× more |
| **Latest crossing** | one, well-timed | **NO — requires knowing which crossing is last, i.e. the future** | yes (offline only) | **disqualified: lookahead** |
| **Refresh after every revision** | many decisions/market (1,306 at T-60s); repeated order/marketVersion events | yes | yes | churn; heavier reconciliation surface; no consistency gain |
| **Stability window (recommended)** | one well-timed decision, or an explicit abstention | yes | yes | governable: dwell is a pre-registered constant; abstains rather than guesses |

## Recommended policy — **stability-window**

Act on the **first horizon-instance crossing that is followed by a governed dwell period `W`
with no further marketTime revision** (the schedule is treated as "settled"). If no crossing
achieves the dwell before the off, **ABSTAIN** — record no pre-match decision for that
market at that horizon, with an explicit reason. All first-crossing and per-revision
instances remain in the immutable lineage as descriptive record; the stability-selected
instance is derived, never a mutation.

Why it wins on the four criteria:

- **Operational consistency:** exactly one decision per (market, horizon), taken once the
  schedule stops moving — directly addressing the measured churn (median 6 revisions) and
  the 25-min first-crossing mistiming, without inventing a "final" instance.
- **Live replicability:** `W` uses only elapsed wall-clock since the last observed revision —
  knowable live; no future information.
- **Deterministic replay:** a pure function of the stream and `W`; the selected instance and
  any abstention reproduce byte-for-byte (SPEC-010/011).
- **Governance:** `W` is a **pre-registered constant** (⟨PENDING FOUNDER⟩), never tuned on
  outcomes; abstention is a first-class, recorded result (no forced decision — consistent
  with SPEC-047 abstention discipline); the lineage is append-only.

`W` (the dwell length) and the maximum lead before the off beyond which a settled crossing
is still acceptable are pre-registered numbers, set by the founder on operational grounds
only — not derived from any result.

## Rejected

- **Latest crossing** — disqualified outright: not live-knowable (you cannot know a crossing
  is the last until the off occurs). It is a lookahead and violates the whole premise.
- **First crossing** — retained only as a descriptive **floor / sensitivity**, not the
  primary policy: it is live and deterministic but acts, in the median case, ~25 min before
  an off the schedule will still revise several times; using it as the operating decision
  would bake the measured mistiming into every downstream study.
- **Refresh after every revision** — retained in the lineage (its instances are exactly the
  state machine's), but rejected as the operating policy: it multiplies decisions and
  order/marketVersion events with no consistency benefit, enlarging the reconciliation and
  transaction-rate surface (SPEC-073) for nothing measurable pre-outcome.

## Scope

This chooses only *which pre-off instance a live system would act on*. It selects no stake,
no order, no benchmark, and nothing in-play (pre-off only). It is an operational-consistency
decision, frozen before Stage-2 consumers depend on it, and revisited only by a governed
baseline-v2 — never because a later result would prefer a different timing.
