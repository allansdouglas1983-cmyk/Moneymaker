# ADR 0018 — June Tennis Market Feasibility Review (Stage 1 closure)

**Status:** ACCEPTED — founder closure directive 2026-07-18. Closes the
market-feasibility phase opened by ADR 0016/0017 under the ADR 0015 pilot carve-out.
**Evidence:** `docs/evidence/pilot-2026-06-tennis/` (frozen, digest-pinned).
**Gate:** `specs/gates/market-m0.yaml` — Gate M0 outcome **PASS** (scope-bounded).
**Frozen decisions:** `specs/programme/baseline-v1.yaml`.
**Next phase definition:** `docs/architecture/stage2-probability-programme.md`.

This document is a programme review, not a build record. It changes no code, re-runs no
analysis, and re-opens no accepted architecture or governance.

---

## 1. Objectives

The pilot existed to answer one programme question at minimum cost, before any
modelling spend: *is Betfair Tennis Match Odds a market in which an evidence-led
probability project is technically possible?* Sub-objectives: prove the purchased
historical data is reproducible evidence (not just data); freeze an analytical universe
before outcomes were knowable; measure market structure (completeness, spreads, depth,
volumes) at pre-registered decision horizons; measure schedule behaviour against the
F-01 hypothesis; establish which closing-benchmark candidates the data can honestly
support; and surface every limitation that later phases must carry.

## 2. Questions the pilot attempted to answer

1. Can the ADVANCED historical files be replayed deterministically, byte-exactly?
2. Is the delivered corpus internally consistent (packaging, duplication, dating)?
3. Can a defensible universe be frozen by rules, blind to outcomes?
4. Do valid pre-match decision states exist, and at which horizons?
5. What do spreads, depth and matched volume look like where decisions would be taken?
6. Can a fixed-minimum-stake policy (SPEC-060) execute against displayed depth?
7. How do tennis starts actually behave vs the schedule (F-01)?
8. Which closing-benchmark candidates are constructible, at what availability?
9. Is one month of data enough, and if not, for exactly which question?

## 3. Questions now answered

- **(1) Yes.** Two independent full reconstructions byte-identical
  (`3c1b64ab…`); zero parse errors; zero off-ladder prices. Replay correctness is no
  longer a risk, it is a property.
- **(2) Yes, after work.** The corpus double-packages markets (16,955 standalone +
  3,527 combined event files, 16,909 verified byte-identical overlaps, 26
  combined-only markets, zero conflicts). Folder dates are unreliable in both
  directions. Both facts are now neutralised by the canonical replay manifest
  (16,981 unique markets, one canonical source each).
- **(3) Yes.** 3,521 MATCH_ODDS markets classified with zero unknowns and zero
  conflicts; universe frozen and hashed (`ce9a147e…`) before any price was read.
- **(4) Yes, via protocol.** Naïve fixed anchors fail (the pre-registered
  `earliest marketTime` anchor is a placeholder for 89% of markets); the governed
  as-of-published-marketTime state machine yields instances for ~92% of primary
  singles at T-30m and ~82% at T-5m, with typed reasons for every miss.
- **(5) Measured.** Median 3-tick (~135 bp) spreads, horizon-invariant T-30m→T-60s;
  median best-back ~£57–70; median matched ~£502/selection (primary) vs ~£840
  (strict tier).
- **(6) Yes.** £2 ≈ exchange-minimum stakes: 96% executable at best price, ~100%
  within the three delivered levels. Capacity degrades smoothly and measurably above
  that (£100: 35% at best, 25% unfillable in displayed depth).
- **(7) Answered decisively.** Tennis starts are late-dominant but not
  late-guaranteed (125/2,876 early vs final schedule), median 6 non-monotone
  schedule revisions per market, off median +5.7 min after even the final published
  time. F-01's refusal to generalise racing's "only ever delayed" fact is vindicated
  by measurement.
- **(8) Answered.** Midpoint/microprice/last-traded candidates: 96.7–99.5%
  constructible with structural in-play exclusion. Traded-WAP: 40.4% — evidenced out
  as a primary candidate. Selection itself remains open by design.
- **(9) One month suffices for feasibility.** A second month is justified only by
  the cross-regime question (§11), never by sample size alone.

## 4. Questions still unanswered

- Cross-regime stability of every liquidity/schedule magnitude (June = grass
  run-up; hard/clay/slam regimes unmeasured).
- Closing-benchmark **selection** (feasibility ≠ choice; DR-TENNIS-BENCHMARK-001 open).
- Live-stream latency, conflation and realised-fill behaviour vs historical files
  (unknowable offline; queue position latent — SPEC-040).
- The reschedule operational policy (first-crossing vs invalidate-and-refresh vs
  stability window) — deliberately unfrozen, must be decided outcome-blind.
- Why 4.3% of markets never turn in-play (cause is outcome-adjacent; untouched).
- Everything about probability modelling — deliberately untouched in Stage 1.

## 5. Incorrect assumptions disproved

1. **"`earliest marketTime` can anchor decision horizons."** Pre-registered, and
   wrong: it is a session/order-of-play placeholder for ~89% of markets (off median
   +105 min later). Corrected mid-pilot by governed founder decision to the as-of
   state machine; all three naïve anchors demoted to descriptive sensitivities.
2. **"Folder path dates the market."** 29 May-scheduled markets sit in `Jun/`
   folders and 3 July markets in the June delivery; `marketTime` under the
   date-membership rule is the only defensible authority.
3. **"One file = one market."** The delivery double-packages every event; without
   the packaging audit, naïve ingestion would double-count 16,909 markets or miss 26.
4. **"Sibling corroboration is required to classify format."** The two-signal
   classifier over-excluded 597 structurally resolvable markets; the founder's
   two-axis redesign (MatchFormat × ClassificationEvidence) classified 100% with
   zero conflicts — and the evidence axis then turned out to be a real liquidity
   covariate, not just labelling hygiene.
5. **"Late starts only" as a live knowability floor** — racing's directional fact
   does not transfer: early starts exist (F-01 confirmed empirically, not just
   conceptually).

## 6. Correct assumptions validated

1. **The mutually-exclusive-choice-set abstraction carries tennis unchanged** — every
   instance had exactly two active selections; MATCH_ODDS is cleanly the N=2 case.
2. **The canonical tick ladder is exchange-level truth** — zero off-ladder prices in
   ~4M runner-change events (SPEC-053 held with zero exceptions).
3. **Metadata-only universe freezing is practicable** — the entire universe,
   classifier and packaging policy were frozen and hashed before any price was read.
4. **Determinism disciplines (SPEC-010/011) extend to purchased historical data** —
   proven byte-exact, twice.
5. **The governed-correction protocol works under pressure** — a pre-registered
   parameter (the horizon anchor) was found wrong on evidence, escalated rather than
   silently patched, and replaced by explicit founder decision with the old anchors
   retained as sensitivities. This is the system behaving as designed.

## 7. Risks removed

- Data-quality risk (parse failures, dirty prices, missing books) — eliminated.
- Reconstruction ambiguity (dual packaging, duplicate replay) — eliminated by
  canonical manifest with fail-hard conflict policy (zero conflicts found).
- Universe-integrity risk (post-hoc cherry-picking surface) — eliminated by frozen
  rules-not-counts manifest.
- "No viable decision point" risk — eliminated (T-10m/T-5m instances at high
  coverage with ~99% complete books).
- "No constructible benchmark" risk — eliminated (three candidates ≥96.7%).
- Minimum-stake executability risk — eliminated for the SPEC-060 v1 policy.

## 8. Risks remaining

- **Regime specificity** — all magnitudes are June-grass; the single approved reason
  for a second data month.
- **Capacity ceiling** — the £50/£100 displayed-depth cliffs bound any future
  strategy's scale; edge (if any) and capacity likely anti-correlate across tiers.
- **Schedule churn as operational risk** — 1,100+ markets re-arm short horizons;
  every re-decision is a marketVersion-lapse opportunity (correct behaviour, but it
  taxes throughput).
- **Displayed ≠ executed** — three delivered levels, no queue data; SPEC-040's
  latent-queue discipline stands between these tables and any fill claim.
- **Thin primary-only tier** — 589 singles with systematically worse books; retained
  with tier as covariate, but any result concentrated there is suspect.
- **Data-rights debt** — Betfair rights questions remain open (procurement doc);
  Stage 2's longitudinal training data needs its own licensing before Gate −1
  (SPEC-101) can pass for models.
- **ADR 0015** — the account-exclusion block stands; everything live remains
  prohibited regardless of any gate outcome.

## 9. Explicit programme decisions

Frozen machine-readably in `specs/programme/baseline-v1.yaml`; summary: primary
market = Tennis / Match Odds / **singles**; primary universe = the frozen June-2026
pilot universe (2,876; strict 2,287 as sensitivity tier; doubles descriptive only);
operational horizon target = **T-10m→T-5m** under the governed marketTime
state-machine protocol; benchmark **unselected**; models **not started**; live
activity **prohibited**. These are working defaults until displaced by evidence
through a governed gate — never by convenience.

## 10. Why no profitability conclusions are permitted

Structurally, none are possible from this pilot, and none may be implied:

1. **No outcome was opened.** Winners, settlement and P&L were never read; there is
   nothing to compute a return against, by construction.
2. **Displayed liquidity is not execution.** Queue position is latent
   (SPEC-040); historical displayed prices are not executions (CLAUDE.md structural
   facts). The capacity tables are scenarios, not fills.
3. **No pre-registration exists.** SPEC-094 requires endpoints, power and stopping
   rules declared before observation; any "profitability signal" extracted now would
   be an unregistered, multiplicity-unaccounted trial (SPEC-091 violation).
4. **The lockbox does not exist yet for tennis.** Until SPEC-092 holdout discipline
   is instantiated, any evaluation would burn evidence we cannot replace.
5. **Commission, latency and fill realism are unmeasured** — the three quantities
   that most reliably delete small edges are exactly the unmeasured ones.
Any statement of the form "this looks profitable" sourced from Stage-1 artefacts is
therefore invalid by construction and must be treated as a defect report.

## 11. Recommendation for the next phase

Proceed to **Stage 2 — the probability engine** (defined in
`docs/architecture/stage2-probability-programme.md`), whose terminal deliverable is
calibrated, out-of-fold, choice-set-level **P(model)** for the frozen universe at
governed horizons — explicitly **not betting**. Its first slices are evidentiary
plumbing, in order: outcome-opening protocol + tennis lockbox freeze +
pre-registration (before any result is read); longitudinal results licensing
(Gate −1 for model data); competitor-identity resolution. Defer the second data
month until the cross-regime question is decision-relevant (at M1/M2 evaluation, a
single-regime result cannot generalise; that is when the purchase closes a named
evidence gap, per the pilot report §15). Freeze the reschedule operational policy
from the pilot's revision-behaviour evidence, outcome-blind, before any Stage-2
horizon consumer depends on it.

---

## 12. Critical review — where does this project most likely die? (founder Task 7)

Answered without softening, ranked by probability, causes separated.

**1. Market efficiency (most likely).** Betfair tennis Match Odds pre-off is a
mature, professionally traded market. The tier where execution is comfortable (strict,
sibling-corroborated, £840 median matched) is precisely the tier where prices will be
sharpest; the tier where inefficiency is plausible (primary-only, junior/low-tier) is
precisely where depth (median best-back ~£14–57) cannot carry stakes. **Edge and
capacity anti-correlate by construction of who trades where.** The single most
probable programme outcome is: models calibrate well, and SPEC-090 paired inference
shows p_fundamental adds ~nothing beyond p_market_info — a clean M2
FAIL_FUTILITY. That is not a failure of the platform; it is the platform's stated
expected outcome ("most likely there is no exploitable edge") reached honestly.

**2. Data limitations.** One regime-month cannot train player-strength models:
~2.9k singles matches with mostly unique pairings is far too thin for Elo-family
longitudinal signal, so Stage 2 lives or dies on licensing an external multi-year
results corpus under knowledge-time discipline (SPEC-023 backfill provenance). The
informational frontier of this market (injury/withdrawal news, order flow) is in
NO dataset we can buy. Three delivered ladder levels truncate capacity modelling.
If Stage 2 stalls, the proximate cause is most likely **training-data licensing**,
not mathematics.

**3. Execution limitations.** taker-v1 pays the spread by construction: median
~135 bp crossing cost plus commission on net winnings sets the hurdle any edge must
clear before it exists economically. FOK-full-stake at £50+ already fails on
*displayed* depth 14% of the time; live it fails more (latency, queue). Schedule
churn adds re-decision overhead where every marketVersion increment correctly lapses
an order. These are all measurable at M3 — but they bound M4 tightly.

**4. Model limitations.** Public-information features (rankings, surface records,
form) are the features most certainly already priced in; models built from them
converge to the market, not past it. Structural serve/return models need point-level
data with its own licensing risk, and tennis's best-of-sets structure makes match
probability sensitive to within-match dynamics no pre-match model sees.

**5. Project design (an honest cost, accepted deliberately).** The safety
architecture — conservative lower bounds, fixed minimum stakes, absolute loss budget,
one selection per market — buys integrity at the price of statistical power. A true
small edge could be real and *undetectable within the affordable sample*: SPEC-094's
own power arithmetic may show required N beyond the loss budget's reach, and the
gates would then correctly return CONTINUE until futility. If that happens the
programme ends not because the edge was absent but because proving it was
unaffordable — an acceptable, pre-chosen outcome, recorded here so nobody later
mistakes it for bad luck.

**6. Variance (least likely as a cause; most dangerous as an excuse).** The
anytime-valid monitoring and pre-registration machinery exists precisely so variance
cannot masquerade as edge or as explanation. If "variance" is ever the stated reason
for failure, the actual reason was a power analysis nobody ran — which is a design
failure (item 5), and should be recorded as such.

**Synthesis:** the most probable terminal state is a clean, well-evidenced
**FAIL_FUTILITY at M2** (no information beyond the market), with second place a
**data-licensing stall in Stage 2**, and third an **M4 death by
spread-plus-commission** on a real but tiny M2 signal. The programme's value in all
three cases is the same: it will know *why*, with evidence, at minimum spend.
