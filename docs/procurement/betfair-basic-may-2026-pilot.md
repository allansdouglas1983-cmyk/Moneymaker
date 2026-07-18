# Betfair Historical BASIC — May 2026 zero-cost sufficiency pilot (Candidate 1)

**Status:** PREPARED 2026-07-18 (founder direction: prioritise a zero-cost
longitudinal-results route). **Not yet executed** — execution begins only after the
founder confirms the portal price is £0. If the displayed price is NOT £0: **STOP and
report; do not check out.** All portal interaction is performed by the founder alone
(ADR 0015 — the agent never touches a Betfair account or portal).

**Question this pilot answers:** can Betfair Historical BASIC lawfully and technically
serve as the F2 global-Elo OUTCOME source (winners/losers + timing only)? It is a data
sufficiency pilot — **no model is trained, no model performance inspected, and no June
outcome is read.**

## 1. Exact portal selections (return/confirm BEFORE purchase)

At `historicdata.betfair.com` (same account/flow as the June ADVANCED purchase):

| Portal field | Selection |
|---|---|
| Sport | **Tennis** |
| Plan | **Basic** |
| Time period | **01 May 2026 – 31 May 2026** (single month) |
| Market type filter | **MATCH_ODDS** only (deselect all others if the filter exists on Basic) |
| File type | **M only** (market files; exclude E/event files — June showed E files are byte-duplicate packaging, and M-only prevents Market/Event duplicate ingestion at source) |
| Expected price | **£0.00** |

**Founder pre-purchase confirmation to send back (the price-confirmation request):**
1. the displayed **price** for exactly these selections (must be £0.00 — otherwise STOP);
2. the displayed **file count** and **total size**;
3. whether the MATCH_ODDS / file-type filters were available on the Basic tier as shown
   (if a filter is missing, report what WAS available and stop before checkout).

## 2. Download → private storage → workspace (the amended June flow)

Identical to the June ADVANCED flow that worked (storage amendment in
`tennis-pilot-purchase.md`): founder downloads the archive → uploads to the founder's
PRIVATE Drive → shares to the workspace for the session → agent pulls, computes
`sha256` of the archive and of every extracted file, pins the manifest in-repo
(`docs/evidence/…/corpus-file-sha256sums` pattern), cross-checks file count against the
portal's displayed count. Raw data never enters the repo; portal re-download is the
source of record.

## 3. Sufficiency verification protocol (the founder's eight checks)

All checks run under the existing guards: metadata passes use the pre-lockbox
field-access recorder; outcome reads go ONLY through the governed extractor
(`l8_evidence.tennis_outcomes`) with a pilot `OutcomeAccessAuthorisation`
(`experiment_id = EXP-BASIC-SUFFICIENCY-001`, data manifest = the May corpus manifest;
May is entirely inside the authorised PRE_JUNE_DEVELOPMENT scope). The June lockbox
stays sealed throughout; June is touched only for **metadata** (names/ids — SAFE
fields) in check 3.

1. **Terminal WINNER/LOSER availability** — % of May MATCH_ODDS markets whose stream
   carries a CLOSED marketDefinition with exactly one WINNER (the extractor's
   unambiguous pattern). Report the full pattern distribution (one-winner / no-CLOSED /
   anomalous), never guessing the anomalous ones.
2. **Void/unresolved handling** — enumerate every non-one-winner pattern (all-LOSER,
   REMOVED-present, no-CLOSED, settledTime-absent) with counts; confirm the extractor
   REFUSES each (typed error), and record them as explicit exclusions.
3. **Selection-id stability May↔June** — for players appearing in both months (matched
   by runner name), is the Betfair selection id stable? Report match rate, collision
   cases (same name, different ids; same id, different names). Metadata only.
4. **Singles classification** — apply the frozen two-axis classifier (classify_v2
   rules) to May; report MatchFormat/evidence counts and confirm zero UNCLASSIFIABLE /
   CONFLICT anomalies (or enumerate them).
5. **Chronological completeness** — May calendar coverage: markets per UTC day,
   gaps, marketTime span vs the delivery window, out-of-window spillover (the June
   delivery contained May/July spillover — measure the mirror).
6. **Outcome-extractor compatibility** — the governed extractor runs unmodified over
   BASIC M files: report parse errors, field absences vs the ADVANCED-derived
   field-classification spec (any NEW field → UNKNOWN → flagged for a
   classification-v2, fail-closed).
7. **No Market/Event duplicate ingestion** — verify no E-file/duplicate packaging is
   present (M-only filter held); every market id unique in the delivery; if E files
   appear anyway, run the June dedup-audit pattern (fail hard on conflicts).
8. **Exclusion retention** — every excluded market (out-of-window, doubles,
   unresolved-outcome, unclassifiable) lands in a May universe/exclusion ledger with a
   reason — nothing disappears (SPEC-091 Exclusion discipline).

**Pass definition (pre-stated):** checks 1–2 show terminal outcomes for a high,
enumerated fraction with all residue explicitly excluded; 3 shows a workable stable-id
or name-join rate with collisions enumerated; 4–8 show no structural blocker. The pilot
returns measured numbers; the founder judges sufficiency. FAIL on any structural
surprise (e.g. BASIC lacks CLOSED runner statuses) — reported, not patched.

## 4. What BASIC may support if the pilot passes (founder-scoped, binding)

ONLY: **global Elo (F2); outcome-only Bradley–Terry (F4, outcome-only variant);
recency/workload counts.** BASIC is NOT claimed to support surface, tournament-tier,
ranking or serve/return features — F3/F5/F6 remain blocked on an enrichment source
(Tennis-Data or paid fallback) with its own rights approval.

## 5. Proposed historical range if the pilot passes

**2021-01 through 2026-05** (five years + five months), purchased as BASIC backfill,
subject to the same £0-or-stop rule per month batch. Extending EARLIER than 2021-01
requires an **outcome-blind player-history/warm-up audit** first: measure, on
2021–2026 metadata only, what fraction of primary-universe players would enter
evaluation months with fewer than a declared minimum of prior observed matches
(rating cold-start coverage). Only a demonstrated cold-start gap justifies reaching
further back — never "more data on principle."

## 6. Rights note (Gate −1 input, not a conclusion)

DR-0001 assessed the Betfair Historical licence for internal research/model training;
its unresolved items (cloud/CI processing wording, personal automated betting under
personal-use terms, retention) carry over to BASIC unchanged and stay on the written-
clarification list. £0 price does not change the licence analysis. Gate −1 for the F2
outcome source consumes this plus the pilot result (decision tree:
`docs/procurement/results-data-gate-minus1-decision-tree.md`).
