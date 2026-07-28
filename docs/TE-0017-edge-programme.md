# TE-0017 — The edge programme: the core spine, nine vetted additions, and what stays dead

**Date:** 2026-07-28 (final synthesis; same-day supersession of the first draft, in place,
while the deciding data is still unopened). **Inputs:** TE-0011 through TE-0016;
DR-TENNIS-FORECAST-LIT-001, DR-TENNIS-MICROSTRUCTURE-001, DR-TENNIS-COHERENCE-METHOD-001,
DR-TENNIS-XMARKET-{SETTLEMENT, INDEPENDENCE, MATH}-001; `tennis-edge/README.md`; and one
adversarial vetting round: **15 proposals across five lenses (timing, selectivity,
estimation, data, product), each attacked by two independent reviews with code-level
verification. A proposal survived only if neither review returned fatal. Nine survived;
six died.** The attacks' binding amendments are folded into every surviving plan below —
they are conditions of execution, not suggestions.

Every acceptance rule below is **pre-registered here, before the deciding data is scored**.
The 2022–2026 archive tail (`data2.tar` / `match_odds2.jsonl`) landed on disk 2026-07-28
and **has not been opened by any pricing, join, or settlement run**. Every freeze in this
document precedes that join, and nothing in this document may be revised after the tail is
opened. Research informed these decisions; it proves no gate. No number below is a realised
return and none ever will be from this data.

---

## 1. What is established

| fact | value | source |
|---|---|---|
| Forecast edge over the closing price (22 features, market-anchored linear residual) | **+0.001064 nats** [+0.000639, +0.001476], 63,676 OOS matches¹ | TE-0011 |
| Placebo (features detached from matches) | −0.000172 [−0.000278, −0.000061] | TE-0011 |
| Exchange re-anchor, paired, anchor isolated | **+0.000773 nats** [+0.000184, +0.001350] | TE-0015 |
| Exchange re-anchor, deployment row (24k vs 90k train) | +0.000812 [+0.000042, +0.001570] | TE-0015 |
| Exchange settlement, all fills credited, **hypothetical** | +1.87% [+0.05%, +3.80%], 21,568 bets | TE-0014 |
| Exchange settlement, supported fills only, **hypothetical** | +2.33% [−0.11%, +4.83%], 13,526 bets | TE-0014 |
| Control (market's own probability) on the same sample | −1.64% [−3.20%, +0.02%] | TE-0014 |
| Network layer (common opponents + intransitivity) | **−0.000043** [−0.000077, −0.000007] — harmful | TE-0016 |
| Cross-book dispersion | +0.000082 [+0.000025, +0.000139] — true, no live path | TE-0016 |
| Model gain on the 10,209 no-pyramid-record OOS matches | **+0.000000** [−0.000835, +0.000841] | TE-0007/README |
| Sample required to resolve a 2% return (5%/80%) | n\* ≈ 31,000 exchange bets | TE-0012 |
| Exchange data held | BASIC last-trade traces only; 27,209 matches priced at T-600s, 2015-07-01 → 2022-03-14, 1,880 days; tail on disk, unopened | TE-0014 |
| Literature calibration of our forecast edge | plausible and small; at the high end of credible broad headroom; not suspiciously large | DR-FORECAST-LIT |

¹ The DR-TENNIS-FORECAST-LIT-001 request quoted +0.001058 nats from an earlier corpus
vintage of the same fit; the repository record is +0.001064. Same measurement, immaterial
difference, both stated so neither number is ever "corrected" silently later.

The control result is the structural fact that changed the programme: on 21,568 bets the
market's own de-vigged opinion **loses** at the exchange (−1.64%) while the model reads
+1.87%. Whatever the model's hypothetical edge is, it is not price shopping. The earlier
small-sample reversal (TE-0011/TE-0013, control above model) was noise, exactly as TE-0012
said eleven-month samples produce.

---

## 2. Constraints, unsoftened

None of these is negotiable, none has an exception path, and no item below may be written
so as to require one.

1. **Pre-off only. Back only. No lay, no hedging, no green-up, no in-play.**
2. **No Kelly.** Flat 1 unit is the only staking rule any measurement uses.
3. **No paid data, ever.** The free Betfair Historical BASIC product is the exchange
   dataset. There is no other. The lost ADVANCED corpus creates no entitlement to replace
   it. No provider feed (TDI, Stats Perform, Sportradar, API-Tennis, Goalserve) is bought.
4. **No Betfair account activity of any kind — ADR 0015 is a permanent hard gate.** Data
   purchase included. No account creation, recovery, credential use, or workaround, ever.
5. **BASIC is a last-trade trace.** No ladder, no volume, no depth. Every money figure is
   **hypothetical**, stated under a named execution rule, with the
   SUPPORTED / UNSUPPORTED / NO_EVIDENCE split shown, NO_EVIDENCE kept in the denominator,
   and an execution-cost sensitivity band (Roll family) attached. A realised-return claim
   is not supportable from this data, full stop (DR-MICROSTRUCTURE-001).
6. **Commission 2% is a labelled modelling assumption** (Betfair's published Basic-package
   example rate), not a fact about any account — no account exists. Australian-based
   events carry a labelled approximation caveat.
7. **No scraping into anything that can touch a bet path.** The quarantine is structural.
8. **An LLM never estimates a probability, prices a bet, or sizes a stake.** All numbers
   from deterministic tested code.
9. **The site stays what it is:** GitHub Pages + Supabase Edge Function, single user, UK,
   owner-email sign-in only. `recommendation` pinned to `NOT_EVALUATED` by database
   constraint; `BET_CANDIDATE` has no reachable branch. No registration, billing, or
   order placement — ever, under this programme.
10. **Frozen before the tail is opened:** the 22-feature model, the walk-forward protocol,
    the T-600s horizon (reason recorded in TE-0013, not tuned), the flat-stake rule, the
    break-even rule with no required-edge buffer, the venue registry, the fill-evidence
    classes — **and, added by this round: the identity-bridge extension (S1), the
    coverage-gate policy and its interpretation (S4), the complete Roll estimator
    specification including every degree of freedom (S6/S7), and the confirmatory family
    count of §5.** The tail is scored by the frozen pipeline or not at all.
11. **Log score is the primary forecast metric.** Never accuracy. Day-clustered bootstrap
    intervals; Bonferroni across families screened in the same round (TE-0016 precedent);
    this round's family count is fixed in §5 before any run.
12. **No minimum-edge buffer, and no staleness or liquidity gate, is enacted on the live
    path without explicit founder approval.** S4/S5/S7 produce evidence and frozen
    candidate rules; enactment is a separate founder decision.

---

## 3. The core spine (unchanged from the first synthesis)

Four items form the spine; the nine vetted additions in §4 slot around them and several
must land **before** P1 touches the tail. **Execution order: P2 → P1 → P3 → P4**, with the
§4 pre-tail items interleaved as §5 specifies.

### P1 — Complete the archive: ingest the 2022–2026 BASIC tail and re-run settlement

**This is the programme.** TE-0016's closing line is the ranking argument: data beats
features from here. The tail roughly doubles the settlement sample (toward n\* ≈ 31,000),
extends coverage across four missing seasons, and is simultaneously the verification gate
for P3. The entire pipeline — identity bridge, `exchange_prices.py`, traded-through
falsification, liquidity strata — already exists and is tested. **S1 (§4) lands first:**
the identity-bridge extension and settlement-label cross-check are frozen before the tail
is joined, so the same ~9% join-loss mechanism does not recur over a sample that doubles
the corpus.

**Measurement plan.** Extend `exchange_prices_600s.jsonl` with the tail at the same frozen
T-600s horizon, same identity bridge (as extended and frozen by S1), same fill-evidence
classification, provenance and source digest printed at build (the TE-0013 two-roots
incident guard). Score the pooled 2015–2026 sample with the frozen 22-feature model and
frozen rule. Intervals: day-clustered block bootstrap, 2,000 draws.

**Pre-registered endpoints.**
- **Primary:** supported-fills-only hypothetical ROI, pooled sample, reported with the P2
  cost band and the full three-way split, NO_EVIDENCE retained in the denominator of all
  coverage reporting.
- **Secondary (declared now so they cannot be promoted later):** all-fills ROI; ROI by
  liquidity stratum; the market-probability control; re-anchor paired nats on post-2022
  covered rows (feeds P3); the frozen S4 coverage-gated reading; the frozen S7 Roll-floor
  gated reading; the S5 staleness-gated reading if its gate was frozen.

**Pre-registered acceptance rule.**
- (a) Cost-banded supported interval entirely above zero → the hypothetical edge is
  established at BASIC's evidential ceiling. Proceed to P3. It remains hypothetical; this
  data can never upgrade it to realised.
- (b) Interval entirely below zero → no hypothetical edge at these terms. The money track
  closes.
- (c) Interval spans zero with n_supported ≥ 31,000 → **FAIL_FUTILITY**: the effect, if
  any, is below the 2% design effect. The money track closes without re-specification.
- (d) Interval spans zero with n_supported < 31,000 → undecided, recorded as undecided.
  No further exchange data exists under the constraints, so no verdict is manufactured.
- **Alarm clause:** if the control clears zero positive on the pooled sample, the model
  result is treated as suspect (price-selection signature) and no claim of any kind is
  made until the discrepancy with TE-0014's control is explained.
- **Widening clause (S2):** if S2 finds adverse drift in excess of the Roll band, the
  primary interval is additionally widened by the measured delay cost, per S2's
  pre-registered rule, before any verdict letter above is read.

No re-tuning against the tail. No horizon search. No stratum, cohort, or period may be
promoted to a headline that the primary endpoint did not earn.

### P2 — The Roll execution-cost band (executed first in time)

P1's primary endpoint is unreportable to the DR-MICROSTRUCTURE-001 standard without it.
The estimator already exists (`tennis_edge/execution_cost.py`: `roll_spread`, MIN_PRINTS=6
pinned before results, positive-autocovariance refusal); what remains is the frozen
specification of every remaining degree of freedom (S6/S7 pins), wiring, and the restated
TE-0014 table.

**Measurement plan.** Transaction-only effective-spread proxy (Roll 1984 serial covariance
of print changes) computed per market from its own pre-off print series. Where the Roll
estimator is undefined (positive autocovariance), the market takes its liquidity stratum's
median band; a market in a stratum with no defined estimate is excluded from the banded
reading with an explicit reason — never silently assigned zero cost. **Coverage and
refusal counts are always reported with the band** — refusals concentrate in trending
(steaming) markets, so the band's own denominator is disclosed wherever the band is used.
The band is applied one-sided and adverse (LTP settlement is optimistic, so the band only
ever widens downward): hypothetical ROI is reported as [ROI − band, ROI].

**Pre-registered acceptance rule.** This is an instrument, not an edge test: it ships when
it is deterministic, unit-tested, and retroactively applied to TE-0014's published table —
restated with the band, not retracted. From that point the band is mandatory on every
money figure, including P1's primary endpoint.

### P3 — Deploy the measured model: exchange anchor + 22 features, one refit

Both halves are already measured: the re-anchor (+0.000773 paired; +0.000812 on the
deployment row) and the serve-detail + durability layers (+0.000202 over the deployed
10-feature model). Deployment also removes a live defect: the site's offset already *is*
an exchange price, served against coefficients fitted on Bet365 closes — a train/serve
mismatch that has existed since launch. One refit fixes both. The rank_gap serve-path fix
(S3) is a strict prerequisite piece of the same fidelity work and lands earlier.

**Measurement plan.** Refit the 22-feature artifact on exchange offsets over the full
covered corpus once the tail lands. Extend the per-player state snapshot with the
durability inputs. Re-emit the 500 golden vectors from the Python, extended to cover the
new absent-feature branches; the Deno test replays every one to 1e-12 in CI. Push via the
existing credential-free `tennis.pull_state()` mechanism.

**Pre-registered acceptance rule.** Deploy if and only if:
- (i) the pooled deployment row (exchange+features over b365+features) on 2017–2026 clears
  zero at the day-clustered 95% bar; **and**
- (ii) the tail-only (post-2022) paired estimate is not significantly negative at the same
  bar — the sign-stability guard TE-0015 said could not be tested without the tail; **and**
- (iii) golden-vector parity holds at 1e-12 across all 500 cases.

If (ii) fails, the site keeps serving the current fit and the failure is recorded — a
coefficient set verified through 2022 and contradicted after it does not go live on hope.
All §2 invariants survive deployment unchanged: `NOT_EVALUATED` pinned, `BET_CANDIDATE`
unreachable, append-only predictions, no credential anywhere.

### P4 — The coherence probe: one test, one stop rule, then done

**Deliberately last, with a realistic prior of death.** The literature's best-documented
failure mode — stale last-trade prices in thin derivative markets manufacturing apparent
mispricing — is present in our data **by construction**, and Match Odds leads price
discovery 82–100%+ at the same one-minute sampling our archive has
(DR-COHERENCE-METHOD-001). The solver stays what it is today — built, tested, unused —
unless this single probe survives. (The vetting round's set-market feature proposal died
precisely for skipping this probe's stop rule; see §8 item 23.)

**Precondition.** The tail archive contains the settlement-registry-v2 usable derivative
markets with sufficient pre-off prints. If it does not, the probe is not run and the layer
is not mourned.

**Measurement plan.** At each snapshot, fit latent serve parameters from derivatives only
(binding corrections §2.1–2.5 of DR-XMARKET-MATH-001 apply: format independently known,
identification ≠ coherence, one fitting definition, first-server nuisance handling, dual
generators). Form gap = logit(p_coherence) − logit(p_match_odds). Two pre-registered
questions on out-of-sample data: **(A)** does the gap add log-score value for the final
outcome conditional on contemporaneous Match Odds; **(B)** does the gap predict
short-horizon derivative convergence toward Match Odds.

**Pre-registered stop rule.** If (A)'s incremental gain fails to clear zero at the
Bonferroni-adjusted bar for its screening round, or (B) succeeds while (A) fails, the
layer is dead: the negative result is recorded, the test is never re-sliced, and the
solver remains unused. Surviving both earns only a follow-up *registration*, not
deployment — and per DR-XMARKET-INDEPENDENCE-001 the independent-information reading of
derivative prices stays closed (`NO_GO_UNPROVEN_INFORMATION_ORIGIN`) regardless of this
probe's outcome; reopening that closure would be its own governed decision on the new
evidence.

---

## 4. The vetted round: nine survivors, ranked by expected value per effort

Rank reflects expected value per unit effort **and** sequencing leverage (an item that
must land before the tail join earns its place partly by protecting P1). Costs are the
proposal estimates as corrected by the attacks. Each entry states: plan, binding
amendments, and the pre-registered acceptance rule. All day-clustered bootstraps use
2,000 draws. "The adjusted bar" means the §5 family-wise bar.

### S1 — Recover the unjoined archive matches; cross-check outcome labels against Betfair settlement *(data lens; ~1 day + one re-extract)*

**Why rank 1.** One day buys three things at once: it fixes the join **before** the tail
is processed (the same ~9% loss mechanism would otherwise recur across a sample that
doubles the corpus — the fix's yield roughly doubles by landing now); it independently
audits every settlement row's outcome label (the Ramirez/two-roots class of failure, where
one bad row inverts a headline); and it probes the name-joinability selection bias the
current 27,209-row covered set silently carries.

**Plan.**
1. Re-run `exchange_link.py`; dump the typed exclusion funnel for the 2,743 unjoined
   matches (UNRESOLVED_NAME / NO_MATCH_ON_DATE / AMBIGUOUS_MATCH / NO_PRICE_AT_HORIZON /
   ALREADY_CLAIMED). **Pre-register the realistic recovery ceiling from this funnel before
   touching the bridge** — review measurement: ~1,726 have no candidate market in the
   extract at all, ~417 lack a T-600s price, ~600 are recoverable. The recovered-cohort
   analysis is sized against the measured ceiling, never the headline 2,743.
2. Extend `sport_tennis/identity_bridge.py` with deterministic, round-trip-verified
   normalisation rules only (accents, hyphenated/particled surnames, double initials,
   Betfair first-name truncation). Never fuzzy scoring, never LLM resolution; ambiguity
   still refuses. **Rules are frozen on funnel evidence alone — whoever writes them sees
   no outcomes or P&L — then the scored run happens once.** Versioned bridge change, never
   in-place.
3. Label cross-check over all joined markets: Betfair runner WINNER/LOSER settlement
   status (`GradingView`, grading-time only) vs the corpus winner column, emitting three
   typed categories — **AGREE / DISAGREE / NO_BETFAIR_SETTLEMENT_STATUS** — with the third
   (voided/retirement markets carrying no winner status) handled per the
   DR-XMARKET-SETTLEMENT-001 completion-status policy, never silently retained.
   Disagreements quarantine the row with a per-row reason. Requires a versioned
   extract-format bump (GradingView is not currently serialised); header contract
   preserved.
4. Document and verify downstream deduplication of the exact row duplication in
   `match_odds.jsonl` (478,324 lines vs 239,168 distinct market_ids; every market yielded
   twice by `read_extract`), including its ~2× pollution of funnel counts.

**Guards.** No previously joined row may change quote or orientation; any row moving to a
typed refusal is enumerated and human-reviewed (a stricter rule legitimately converting a
join into a refusal is correct behaviour, not a regression to suppress).

**Acceptance rule.** The enlarged supported-fills interval is reported as an **interim
look under sequential accumulation toward n\* ≈ 31,000, never a settled verdict**. The
recovered cohort (skewing non-anglophone) is reported separately: divergence at the
adjusted bar is a selection-bias finding about the existing join; non-divergence is
reported as "no gross divergence detectable at this power" — never as "no selection bias"
(~600 bets carry a ±6pp interval). After quarantine, the locked benchmark regression is
rerun; the +0.001064 headline must be stable or the discrepancy is itself the finding.

### S2 — Full-archive intended-order CLV and delay-cost curve *(timing lens; ~1 day)*

**Why rank 2.** CLV is near-deterministic given the pick, so ~20k picks resolve drifts an
order of magnitude smaller than the 0.5–2 implied-probability-point steam signature —
where ROI would need 31,000 bets. It directly audits the most suspicious rows in the money
record (the 4,525 UNSUPPORTED fills at +3.99% — the steam signature) and produces the one
number the Roll-band convention is missing, **before** the tail verdict is read. Decisive
either way; both outcomes trigger a pre-defined action, so there is no keep-if-significant
filter.

**Plan.** Freeze the TE-0014 bet list from T-600s state only. Reuse `ltp_at` at T-300 and
T-120 on the same `MarketHistory` objects. Measure, day-clustered:
(a) signed logit drift on picked sides T-600→T-300/T-120 — **primary statistic: mean
signed drift per horizon, fixed now; median is secondary** — against the
market-probability control picks and an always-back-A placebo, in implied-probability
points, compared **distributionally per market** against the Roll band;
(b) the paired per-day ROI difference of the identical bet list settled at T-600s LTP vs
the later LTP (both sides share the fill assumption, so the pair isolates delay cost).

**Binding amendments.**
- **Three-branch verdict declared in advance:** (i) drift in excess of the Roll band →
  steam evidence; the P1 headline interval is formally widened by the measured delay cost
  before the tail verdict is read; (ii) drift positive but within the band →
  band-consistent execution cost — no strengthening of SUPPORTED, no widening beyond the
  band; (iii) drift ≈ 0 → the SUPPORTED class gains force. The middle branch exists so no
  post-hoc reading is available.
- **The selection-on-bounce null is named:** bets fire when the T-600 LTP is generous, so
  pure regression to the mid appears as adverse drift up to ~half the effective spread.
  Only drift **in excess of** the band is steam evidence.
- Coverage discipline: markets with no print by the later horizon are typed exclusions
  (from the timestamped print series, never `ltp_at` carry-forward); the verdict is scoped
  per coverage class — drift on covered rows is drift conditional on continued trading,
  which is the same class the SUPPORTED reading lives in.
- Roll-refusal counts reported alongside the band (refusals concentrate exactly where
  drift is largest; the comparison discloses that blindness).
- SPEC-095 discipline explicit: signal/intended-order CLV only; realised-fill CLV is never
  claimed for any bet; later prices never enter features or training; CLV is never a
  training target.

**Acceptance rule.** The three-branch verdict above, read at the adjusted bar, family 1 of
§5. All ~8 pre-specified contrasts belong to this single directional family.

### S3 — Close the serve-path gap: rank_gap in every served prediction *(product lens; ~1 day)*

**Why rank 3.** A code-verified live defect, not a hypothesis: training imputes missing
ranks (`or 500`) so **every one of the 63,676 measured rows had rank_gap**, while the site
serves the rank-absent branch on **every** prediction — coefficients fitted jointly with
rank_gap applied to inputs that lack it, the exact train/serve mismatch class TE-0011
refused to deploy over. The weekly ledger path builds rank_gap while the site does not, so
ledger and site currently score the same nominal model differently. The fix restores the
model that was actually measured; nothing is gated on significance.

**Plan.** During `live_state.build_state`, record each player's latest-known ranking from
their most recent corpus match row (knowledge-time safe: published with a strictly earlier
match). Thread through `PlayerState`, the state JSON, `tennis.pull_state`, and
`scoring.ts` `liveFeatures` — **reproducing the `or 500` imputation branch in TypeScript**
so parity holds for players with no known rank. Re-emit golden vectors including
rank-present and rank-absent branches, held to the existing 1e-12 Deno replay.

**Measurement (three arms, identical rows, day-clustered).**
(a) 22 vs 21 features, paired refit — the coherent marginal value of rank_gap (a lower
bound on the forfeiture);
(a′) **the fixed deployed 22-coefficient artifact scored with rank_gap withheld vs
present — the exact serve-path estimand, including the coefficient-mismatch term**;
(b) rank_gap from latest-prior-match rank vs fixture-time corpus rank — proxy validation,
**bucketed by rank staleness** to catch protected-ranking/injury-return cases.

**Acceptance rule.** Deploy the fix regardless of measured magnitude — it removes a
measured train/serve mismatch, and both branches of the outcome are actioned: a material
number quantifies what was being forfeited; a ~0 number is recorded and the field is
dropped at the next refit (itself re-measured). The two measurement runs carry a
Bonferroni correction between them internally; they gate nothing. A stale-beats-fresh or
sign-anomalous reading is a suspected harness bug per house rules.

### S4 — Information-coverage gate: refuse the cohort where the model measurably knows nothing *(selectivity lens; <1 day)*

**Why rank 4.** The cheapest survivor: one parameter-free, binary, decision-time-knowable
predicate ("both players carry a pyramid record") fixed by prior publication of the
forecast split (+0.000000 on the uncovered cohort) **before any money-by-cohort split
existed anywhere in the record** — verified: no such split appears in TE-0011..0016 or the
code. On uncovered rows the model *is* the anchor by construction (absent features
contribute nothing), so every fired bet there is estimation noise around the market minus
commission: removing the cohort cannot reduce expected profit and mechanically lowers n\*.

**Plan.** Paired settlement run on identical rows and days, gated vs ungated, same
22-feature model, same walk-forward; both cohorts reported with exclusions, three-way fill
split, hypothetical labels.

**Binding amendments.**
- **Report the measured uncovered share of fired exchange bets** — never the 16%
  OOS-match share (the exchange archive is main-tour-weighted; the fired-bet share may be
  far smaller, and the lift shrinks proportionally).
- The gate's justification is the **structural zero-information identity**; the paired
  money difference is a directional diagnostic and will plausibly not clear zero — that is
  stated now so a null cannot trigger either over-claiming or unprincipled retreat.
- The side predictions are harness-consistency checks, not evidence: (a) uncovered-cohort
  model-vs-control ROI difference ≈ 0 is near-tautological; (b) the coverage-weighted
  average identity is arithmetic. Prediction (b) is run on the **22-feature** model (the
  published zero was the 10-feature fit) and reported either way. If the uncovered cohort
  *earns* — the money edge living where the forecast edge is not — that is a suspected bug
  per house rules: stop and investigate.
- The gated 2015–22 reading is a **policy refinement of seen data, labelled as such** —
  excising a negative-expectation cohort predictably pushes the same sample over zero and
  is not new evidence.

**Acceptance rule.** The gated policy and its interpretation are **frozen now, before the
tail is joined**; the tail scored under the frozen gated policy (a declared P1 secondary)
is the confirmatory test. Adoption on the live path additionally requires the founder
approval of §2.12.

### S5 — LTP-age (staleness) stratification: ground the staleness refusal in evidence *(timing lens; ~0.5 day)*

**Why rank 5.** A stale anchor is an old opinion: the model "disagreeing" with an
out-of-date price manufactures phantom edge — the adverse-selection signature TE-0014
caught (silent stratum −2.60%). LTP age at the horizon is the first **live-knowable**
liquidity conditioning in the project (computed strictly from pre-cutoff prints), and a
prospective staleness refusal rule needs *some* frozen number; a measured one beats a
guessed one. Power for band heterogeneity is honestly thin — the deliverable is the frozen
rule and the cross-tabulation, not a harvested nat.

**Plan.** New versioned price-table kind (never an in-place edit) adding
`ltp_age_a/b` = cutoff − last pre-cutoff print's `publish_time_ms`. Bands pre-registered
now: {<60s, 60–600s, >600s}, with the **~60-second BASIC cadence quantisation declared**
(<60s means "printed within the last cadence interval"; sub-minute staleness is
unobservable in this data). Then, strictly sequenced:
1. Reading (1): paired log-loss gain of exchange+features over bare exchange per band on
   identical rows. **Primary endpoint: a single pre-registered monotone trend statistic
   across bands** at the adjusted bar; per-band CIs are descriptive. Per-band difference
   distributions shown (stale-band differences are heavier-tailed).
2. **Freeze the staleness-gate selection rule** — a stated function of the log-loss strata
   only — before any money is read.
3. Reading (2): per-band ROI and fill-class split; money reported with and without the
   frozen gate.

**Binding amendments.** Report the ltp-age × TE-0014 post-horizon-prints cross-tabulation;
the two stratifications are the same thinness variable either side of the horizon and are
**never cited as independent evidence**. Report band composition (odds band, tour, year)
so a stale-band effect is not an odds-band effect in disguise. Live-knowability claims are
scoped to the delayed-key observation path and timestamped manual entries — the Betfair UI
shows the last-traded price, not its age.

**Acceptance rule.** Trend statistic clears the adjusted bar (family 2 of §5) → the frozen
gate becomes the staleness-refusal candidate carried into prospective capture and
confirmed on the tail. Null → the threshold is still frozen, **explicitly labelled an
assumption, not a measurement** — a ±0.0015-nat null does not locate a boundary, and the
write-up says so.

### S6 — The site grades its own served predictions; every edge shown with its cost band *(product lens; ~2–3 days)*

**Why rank 6.** Zero nats, maximum trust: the predictions table is currently write-only,
so the full serving path (TypeScript port, real user-entered prices, real staleness, real
coverage) has never been scored end to end — a silent drift anywhere in that chain would
be invisible behind confident numbers. And the displayed edge is a point, while the
adopted DR-MICROSTRUCTURE-001 standard requires the band. This slice is also where P2's
band table reaches the user, and its by-product — TE-0014's table restated with the
band — closes the DR-mandated pending item.

**Plan (scorecard).** Weekly Action step after corpus refresh: join completed matches to
predictions by match_key under a **deterministic vintage policy declared before any
outcome is seen (last pre-match row)** — never select-the-best-vintage; append outcome
rows to a settled ledger (predictions never mutated); `/scorecard` endpoint and page
section with denominator and typed exclusions (unmatched names visible, via the identity
bridge). The paired day-clustered model-vs-market log-loss is **monitoring with intervals,
explicitly non-gating**: no thresholded alarm (any future formal halt rule must meet the
SPEC-096 anytime-valid standard); the page states single-user volume can gate nothing and
never compares its number to the 63,676-match intervals. **Display-only by construction:
the scorecard feeds nothing served — not MIN_EDGE, not staleness thresholds, nothing.**
Backfill replay over existing prediction rows proves key-matching and the never-mutate
property.

**Plan (band).** Frozen per-stratum Roll table from the BASIC print series, **keyed to a
pre-horizon-knowable liquidity proxy or pooled** — the TE-0014 post-horizon strata are not
observable at serve time, so a live prediction takes the widest applicable band or
"stratum unknown → conservative band", never a claimed stratum. Deterministic, golden-
vectored conversion of the Roll relative spread into probability points at the quoted
odds. Coverage and refusal counts printed with the table; "band not estimable" rendered
honestly. Edge displayed as [edge − band, edge].

**Acceptance rule.** An instrument, not a test: ships when deterministic, unit-tested,
golden-vectored, the end-to-end replay passes, and the TE-0014 band re-report is
published. No statistical bar; no family consumed.

### S7 — Roll-band edge floor and the edge-monotonicity diagnostic *(selectivity lens; ~1 day marginal on P2/S6)*

**Why rank 7.** The current rule bets any positive edge over break-even, including edges
smaller than the price's own measurement noise. The threshold is not a fitted constant —
it is the market's own measured cost, per market, so nothing is tuned against returns. The
attacks establish the honest expectation: **the gated archive reading will most likely
span zero** (gating shrinks n below n\*), so the archive run is exploratory and the value
is the frozen instrument plus the tail confirmation — and the monotonicity diagnostic,
which caps what any future minimum-edge policy could deliver before the founder is ever
asked to approve one.

**Pins, frozen before any gated computation.** Positive-autocovariance markets are a
**typed exclusion with their own reported cohort** (the gate is structurally blind exactly
in the trending/steam class it targets; that blindness is disclosed, never patched);
window start; half- vs full-spread choice; the probability-point conversion; and the edge
definition — this backtest emits a point probability, so the gate compares **point edge vs
Roll-implied half-spread**, recorded as such. Roll-coverage composition is cross-tabbed
against the TE-0014 strata so a gate "effect" is distinguishable from the known stratum
result.

**Plan.** Band around the existing headline first (P2/S6). Then: paired gated-vs-ungated
hypothetical ROI on identical days, day-clustered. Monotonicity: decile fired bets by
predicted edge; realized-net-return-vs-edge slope with day-clustered errors, reported as a
**CI under equivalence framing** — the negative capability claim ("edge magnitude carries
no selection value") is licensed only if the slope's upper confidence bound excludes a
pre-declared minimum useful slope, with the power arithmetic published. A flat point
estimate alone licenses nothing.

**Acceptance rule.** The 2015–22 run is labelled **exploratory** (its hypothesis was
motivated by TE-0014's classes on this same archive) and is stated in advance to be
expected to span zero — no narrative either way. The confirmatory test is the tail under
the frozen pinned spec (a declared P1 secondary). Any live minimum-edge buffer remains a
founder decision (§2.12); this work only produces the evidence.

### S8 — Price the weekly-cadence staleness penalty; move to daily rebuild if material *(product lens; 1-hour pre-check, then ~2–3 days)*

**Why rank 8.** Every published gain was measured with day-fresh engine state; the product
serves from a Monday snapshot, so a Friday prediction misses up to six days of results,
and `state_stale_days` is displayed without anyone knowing what a stale day costs. The
manipulation removes information only, so the effect is sign-constrained (stale beating
fresh = suspected harness bug), the harness has demonstrated resolving power at the
0.0002-nat decision threshold, and the fix, if taken, is a cron edit on free runners.

**Pre-check (1 hour, before any spend).** Verify provider cadence from the stored
Last-Modified/ETag provenance. If the sources publish weekly, the daily-recovery arm is
structurally ~zero: the sweep still runs once to price the penalty honestly (the number
the `state_stale_days` field silently raises), but the switch rule below cannot fire.

**Plan.** Strictly additive lag mode in the feature-build walk: the frozen baseline path
untouched, **lag included in the feature-cache key** (two-roots discipline), and lag=0
must reproduce the published numbers byte-for-byte as an explicit acceptance criterion.
Lags {0, 1, 3, 5, 7, Monday-schedule mode}; lag applied to **scored features only**
(training stays day-fresh, mirroring deployment). **Primary endpoint: Monday-schedule
mode vs lag=0 on the deployed 10-feature configuration** (22-feature secondary — a
"product penalty" quoted from an undeployed configuration measures a product that does not
exist). Estimand: average per-match penalty weighted by the historical match-day
distribution. Other lags are a descriptive dose-response curve; monotonicity is a validity
check. **No post-hoc day-of-week re-slicing** (a Friday-only penalty quoted from a null
average is the cherry-pick SPEC-038 bans). Trial logged in the ledger. Honesty note,
pre-stated: the serve and pyramid engines hold tournaments to week close by construction,
so the penalty loads on the Elo/durability engines — the mechanism's same-tournament-form
story is structurally muted.

**Acceptance rule (family 3 of §5).** Switch to daily iff (i) the Monday-mode penalty
interval excludes zero at the adjusted bar **and** (ii) the recovery achievable at the
**measured source-latency floor** — never at lag=1 per se — exceeds 0.0002 nats
(durability scale). A null is reported with its interval width and is never phrased
"certified no penalty" while the interval still covers 0.0002.

### S9 — Estimate the anchor temperature: δ = t−1 as a ridge-penalised pseudo-feature *(estimation lens; ~0.5 day)*

**Why rank 9 (last).** The best-formed estimation idea left: one nested parameter, shrunk
toward the incumbent (δ=0 reproduces the current model exactly), with the strongest
mechanistic prior any proposal carried (the b365 shrink-only control: β≈0.95, t≈60, worth
+0.00015 nats). It ranks last because the honest expectation is a recorded kill: the test
is well-powered only at the top of its own +0.0001–0.0003 range on 19,957 rows, the
22 price-correlated features already partially span the shrink direction, and the two
mechanisms cited (errors-in-variables attenuation, δ<0; favourite–longshot, δ>0) partially
cancel. Half a day and one family buys either a real layer-sized gain or an honest null.

**Plan.** Fifth model row in `experiments/exchange_anchor.py`: `anchor_logit` (the row's
own offset) added as an L2=25-penalised pseudo-feature — L2 untouched, MIN_TRAIN=3000
untouched — scored paired against exchange+features on the identical 19,957 rows.

**Pins.**
- The odds-in-features ban needs its **documented governed exception, written down
  explicitly**: the pseudo-feature is the row's own offset at identical knowledge time —
  zero new information, no new leakage surface — and the name would not trip
  `BANNED_FEATURE_TOKENS`, so the exception is declared, never slipped past the guard.
  Unlike dispersion (TE-0016), this has a live path: the served offset already is an
  exchange price, so a fitted temperature deploys as one number with no new live inputs.
- **The staleness interaction is dropped from this registration.** The only prints fields
  in the held price table are post-horizon (built for fill falsification, unknowable at
  T-600s); using them as a fit input is lookahead. δ-by-liquidity-stratum remains a
  post-hoc diagnostic only.
- Placebo: within-day permutation of the pseudo-feature, judged on the **placebo's CI**
  (≤ 0), not its point estimate. Per-year δ printed; sign stability required.

**Acceptance rule (family 4 of §5).** Pass requires all of: paired CI clears zero at the
adjusted bar; δ sign-stable across years (instability = recorded as noise even if the
pooled CI clears); placebo CI ≤ 0. A pass is **measurement-only**: serving the fitted δ
additionally requires demonstrated stability across liquidity strata, because train-time
noise (two stale LTP prints) differs from serve-time input (a fresh quoted back) and
attenuation-driven δ is specifically expected not to transfer. Fail on any criterion →
record and stop; the row is never re-run to a different answer.

---

## 5. Sequencing and the multiplicity ledger

**Order of operations.**

1. **Before the tail is joined** (the raw tail is on disk, unopened; the clock is
   running): S1 funnel + bridge freeze + label cross-check; S4 policy freeze; S6/S7 Roll
   estimator pins; S5 band registration; this section's family count. These land as
   commits whose hashes precede any `data2` join.
2. **Pre-tail measurements on data already scored:** P2 band + TE-0014 restatement; S2;
   S3; S4 readings (labelled); S5; S6; S7 exploratory run; S8 (after its pre-check); S9.
3. **The tail:** P1 under the frozen pipeline, with the frozen S4/S7 (and S5, if frozen)
   policies as declared secondaries; then P3's deployment decision.
4. **Last:** P4, under its own precondition and stop rule.

**Confirmatory families in this round — fixed now, before any run: four.**

| family | test | bar |
|---|---|---|
| 1 | S2 — CLV drift/delay verdict (all ~8 pre-specified contrasts, one directional hypothesis) | 98.75% |
| 2 | S5 — LTP-age monotone trend statistic | 98.75% |
| 3 | S8 — Monday-mode staleness penalty (primary endpoint) | 98.75% |
| 4 | S9 — anchor temperature δ (primary paired row) | 98.75% |

Everything else in §4 is a diagnostic, an instrument, an exploratory run, or a policy
freeze whose confirmation happens on the tail — declared as such above, and none may be
promoted to a confirmatory claim after the fact. Tail-round arms (P1 endpoints; S4/S7
confirmations; P3's rows) form the tail's own family accounting, declared in P1/P3 above.

---

## 6. True facts with nowhere to go

Held as evidence, not programme items. Each has a stated reactivation condition; none has
an active one.

- **Cross-book dispersion, +0.000082 nats [+0.000025, +0.000139]** at the adjusted bar —
  no live path (the site's input is a single Betfair price), a tenth of the smallest kept
  layer, and admitting it would spend a governed odds-ban exception on a measurement-only
  feature. Reactivates only if a free, lawful, live multi-book feed exists that crosses
  neither the scraping quarantine nor the no-paid-data rule. None does.
- **Pinnacle sharpness, +1.48% [+0.23%, +2.69%] vs control −2.08% on 38,078 bets** — the
  strongest evidence the forecast is real, and not money: the venue has been closed to UK
  customers since November 2014. Diagnostic forever.
- **Panel maximum, +3.41%** — not a venue; its own control earns +0.41% by shopping.
  Sharpness diagnostic only, test-enforced out of every settlement table.
- **Moderate liquidity stratum, +4.33% [+0.68%, +8.00%], clears zero** — reported in P1
  as a declared secondary, never promoted to a headline. A stratum chosen after the fact
  is a parameter — and the vetting round killed the attempt to launder it into a
  decision-time gate (§8, item 20).

---

## 7. Standing guards that carry forward

- `tennis_edge/venues.py`: nothing synthetic and nothing closed to the UK can enter a
  settlement table without deleting a test.
- Provenance printed on every feature build (root, vintage id, manifest digest) — the
  two-data-roots incident does not recur silently. Lag modes and new table kinds enter the
  cache key (S5, S8).
- Golden vectors: Python and TypeScript scoring agree to 1e-12 on every push or the build
  is red — extended by S3 (rank branches) and S6 (band conversion).
- Fill evidence: universe in = filled + excluded, every exclusion with a reason. Extended
  by S1 (label cross-check categories) and S2 (coverage classes).
- The settlement horizon is frozen at T-600s with its reason recorded; a horizon chosen
  against observed returns is a parameter, and the best one is always found afterwards.
- Roll bands never appear without their coverage and refusal counts (P2/S6/S7).

---

## 8. Killed, and staying dead

One line each. Reopening any of these requires new external evidence and a founder
decision — not enthusiasm, not a fresh session forgetting why it died.

From the prior record:

1. **Network / intransitivity residual** — measured significantly *negative* on our data:
   −0.000043 nats [−0.000077, −0.000007]; harmful, not neutral (TE-0016).
2. **Gradient-boosted combiner** — literature: beats the market on accuracy only, loses on
   proper scores; no evidence the class beats a market-anchored linear residual at our
   scale (DR-FORECAST-LIT-001).
3. **Neural / GNN / Bayesian point-model classes** — broad market-beating evidence does
   not exist; the published wins are subset stories or replication casualties
   (DR-FORECAST-LIT-001).
4. **Wikipedia buzz / crowd attention** — headline ROI collapsed under a one-row data
   correction and generated no profits after 2020; parked behind a multiplicity budget
   nothing currently justifies spending (DR-FORECAST-LIT-001).
5. **Cross-market arbitrage** — 5,799 exhaustive covers, zero locks, best −0.31%; closed
   by measurement.
6. **Derivative prices as independent information** —
   `NO_GO_UNPROVEN_INFORMATION_ORIGIN`; order origin is unobservable in the historical
   feed; coherence is a diagnostic class, never a predictor
   (DR-XMARKET-INDEPENDENCE-001).
7. **Late-horizon information** — spread tightens 44.9 → 3.5 ticks while log loss stays
   flat: execution gets cheaper late, no information arrives late; the horizon stays
   frozen (TE-0013).
8. **Challenger / ITF tier** — 3.67% ATP / 4.66% WTA round-trip cost against 1.12% on the
   main-tour exchange: a cost wall (README).
9. **LTP-settled "realised" returns** — a trade print is not a standing offer; never
   presentable as realised, from this data or any trace like it
   (DR-MICROSTRUCTURE-001).
10. **Queue or depth reconstruction from BASIC** — identification is impossible without
    book state; fill probability needs order-book data we do not have and will not buy
    (DR-MICROSTRUCTURE-001).
11. **Dispersion as a deployed feature** — true and undeployable; see §6; the governed
    exception it would cost is not spent on +0.00008 nats (TE-0016).
12. **Bookmaker-venue deployment (Bet365, Ladbrokes)** — both restrict winning accounts,
    so a proven edge cannot be exercised repeatedly; their columns are diagnostics
    (TE-0013).
13. **Pinnacle or panel statistics as money** — unreachable venue / not a venue;
    test-enforced out of settlement (TE-0013).
14. **Any paid data** — no paid data, ever; the lost ADVANCED corpus creates no
    entitlement; provider licences are conditional-on-contract at best and out of scope
    regardless (TE-0013, DR-CHATGPT-002).
15. **Any Betfair account activity** — ADR 0015, permanent, data purchase included.
16. **Kelly, lay, in-play, passive maker fills** — prohibited by construction, not policy.
17. **Tuning the settlement horizon, stake rule, or edge buffer against observed
    returns** — the best parameter is always found afterwards; everything is frozen in §2.
18. **More feature layers as the path forward** — the post-2018 literature is exhausted
    and our own screening round confirmed it: once a sharp anchor and a well-specified
    residual exist, broad headroom is vanishingly small. Data beats features (TE-0016).

Killed in this vetting round (both reviews or one fatal review; verified against code, not
against the proposals' own text):

19. **Horizon curve sweep of the re-anchor (T-3600s→T-120s)** — as registered, a panel of
    spans-zero contrasts would have been minted as a "horizon-robust" deployment fact:
    accept-the-null with no equivalence margin, an inverted power incentive (less power →
    "flatter"), an under-counted test family, and an unverified all-horizon intersection.
20. **Decision-time liquidity gate from pre-horizon print activity** — reverse-engineered
    from TE-0014's best post-hoc cell and tested on the same archive that generated it;
    its only kill criterion (activity autocorrelation) is near-unfailable; the freshness
    threshold was unfrozen; underpowered across most of its own predicted effect range.
21. **Informative-center ridge (shrink the 24k exchange fit toward the 90k b365
    coefficients)** — its headline claim is false: TE-0015's deployment blocker is
    post-2022 coefficient stability, which no estimator scored on 2017–2022 rows can
    address; success was defined as a third unadjusted look at the same decision rows,
    and TE-0015's own table shows the 24k fit *beating* the 90k fit (drift, not noise).
22. **Anytime-valid money confidence sequence seeded from 2015–22** — the sequence head is
    the hypothesis-generating, multiply-examined data, which voids the supermartingale
    guarantee; its validation criterion was circular (tune until it matches TE-0014); the
    weekly-ledger continuation chains a different estimand into the same interval.
23. **Cross-market coherence via set markets through the existing solver** — the named
    solver cannot consume set-market inputs, and any solved output reproduces Match Odds
    by construction (it is an identification equation), making the proposed feature
    degenerate; the registration defers set markets, the solver is import-quarantined, and
    the recorded lead-lag stop-rule protocol (now P4) was skipped entirely.
24. **Pyramid coverage extension from lower-tier files** — the Sackmann lower-tier
    archives are already ingested by the exact build that measured the +0.000000 cohort;
    `kaggle_itf` is rights-blocked for training/operational use (registry: measurement
    only, and it stays that way); the cohort test cannot resolve its own predicted effect,
    and its null was pre-wired to an invalid permanent retirement.

**Descendants the attacks themselves sanctioned** — each a *new* registration if ever
pursued, none a resurrection: an equivalence-framed horizon test (margin pre-registered
relative to the +0.000773 gain) as a tail-round arm; the pre-vs-post-horizon activity
cross-tab as unregistered descriptive work with confirmation only on the tail; the
informative-center estimator as one frozen, pre-registered arm of the tail re-measurement;
an anytime-valid monitor started **on data not yet seen** (tail onward, one primary
variant, estimand fixed per instrument); the read-only classification of the 10,209
no-pyramid rows as a half-day diagnostic with no measurement claim attached. None of these
is scheduled; none may be run without its own registration.

---

## 9. How the programme ends

Three ways, all acceptable, all pre-registered:

- **P1(a):** a cost-banded, falsification-surviving, delay-cost-audited, hypothetical
  exchange edge on the full 2015–2026 archive — the strongest claim this data can ever
  support, clearly labelled as its ceiling, served by the P3-deployed model on a private
  single-user page that grades itself and recommends nothing.
- **P1(b) or (c):** no edge, or an edge too small to matter — established cheaply and
  honestly, which was always the platform's stated job. The forecast result
  (+0.001064 nats) stands on its own as a measurement regardless.
- **P1(d):** undecided at the data's limit — recorded as undecided, with no verdict
  manufactured and no constraint bent to buy more data.

There is no fourth ending in which a constraint is softened to keep the programme alive.
