# TE-0017 — The edge programme: four survivors, ranked, and what stays dead

**Date:** 2026-07-28. **Inputs:** TE-0011 through TE-0016; DR-TENNIS-FORECAST-LIT-001,
DR-TENNIS-MICROSTRUCTURE-001, DR-TENNIS-COHERENCE-METHOD-001, DR-TENNIS-XMARKET-{SETTLEMENT,
INDEPENDENCE,MATH}-001; `tennis-edge/README.md`.

This document is the synthesis of the adversarially-vetted proposals into a final programme.
Every acceptance rule below is **pre-registered here, before the deciding data is scored**.
The 2022–2026 archive tail is incoming; nothing in this document may be revised after that
data is opened. Research informed these decisions; it proves no gate. No number below is a
realised return and none ever will be from this data.

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
| Sample required to resolve a 2% return (5%/80%) | n\* ≈ 31,000 exchange bets | TE-0012 |
| Exchange data held | BASIC last-trade traces only; 27,209 matches priced at T-600s, 2015-07-01 → 2022-03-14 | TE-0014 |
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
    break-even rule with no required-edge buffer, the venue registry, and the
    fill-evidence classes. The tail is scored by the frozen pipeline or not at all.
11. **Log score is the primary forecast metric.** Never accuracy. Day-clustered bootstrap
    intervals; Bonferroni across families screened in the same round (TE-0016 precedent).

---

## 3. Survivors, ranked by expected value per effort

Four items survived adversarial vetting. Everything else is in §6.

### P1 — Complete the archive: ingest the 2022–2026 BASIC tail and re-run settlement

**Rank 1. This is the programme.** TE-0016's closing line is the ranking argument: data
beats features from here. The tail roughly doubles the settlement sample (toward
n\* ≈ 31,000), extends coverage across four missing seasons, and is simultaneously the
verification gate for P3. The entire pipeline — identity bridge, `exchange_prices.py`,
traded-through falsification, liquidity strata — already exists and is tested. Effort is
ingestion plus compute. No other act has comparable resolving power at any price.

**Measurement plan.** Extend `exchange_prices_600s.jsonl` with the tail at the same
frozen T-600s horizon, same identity bridge scoped per day, same fill-evidence
classification, provenance and source digest printed at build (the TE-0013 two-roots
incident guard). Score the pooled 2015–2026 sample with the frozen 22-feature model and
frozen rule. Intervals: day-clustered block bootstrap, 2,000 draws.

**Pre-registered endpoints.**
- **Primary:** supported-fills-only hypothetical ROI, pooled sample, reported with the P2
  cost band and the full three-way split, NO_EVIDENCE retained in the denominator of all
  coverage reporting.
- **Secondary (declared now so they cannot be promoted later):** all-fills ROI; ROI by
  liquidity stratum; the market-probability control; re-anchor paired nats on post-2022
  covered rows (feeds P3).

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

No re-tuning against the tail. No horizon search. No stratum, cohort, or period may be
promoted to a headline that the primary endpoint did not earn.

### P2 — The Roll execution-cost band (executed first in time)

**Rank 2 by expected value; first in execution order,** because P1's primary endpoint is
unreportable to the DR-MICROSTRUCTURE-001 standard without it. Effort is small; the value
is that every money number the project ever states becomes defensible to an external
standard rather than a self-set one.

**Measurement plan.** Transaction-only effective-spread proxy (Roll 1984 serial covariance
of print changes) computed per market from its own pre-off print series. Where the Roll
estimator is undefined (positive autocovariance), the market takes its liquidity stratum's
median band; a market in a stratum with no defined estimate is excluded from the banded
reading with an explicit reason — never silently assigned zero cost. The band is applied
one-sided and adverse (LTP settlement is optimistic, so the band only ever widens
downward): hypothetical ROI is reported as [ROI − band, ROI].

**Pre-registered acceptance rule.** This is an instrument, not an edge test: it ships when
it is deterministic, unit-tested, and retroactively applied to TE-0014's published table —
restated with the band, not retracted. From that point the band is mandatory on every
money figure, including P1's primary endpoint.

### P3 — Deploy the measured model: exchange anchor + 22 features, one refit

**Rank 3.** Both halves are already measured: the re-anchor (+0.000773 paired;
+0.000812 on the deployment row) and the serve-detail + durability layers (+0.000202 over
the deployed 10-feature model). Deployment also removes a live defect: the site's offset
already *is* an exchange price, served against coefficients fitted on Bet365 closes — a
train/serve mismatch that has existed since launch. One refit fixes both. Effort is
medium: state-snapshot extension (h2h, retirement, workload), TypeScript port, golden
vectors, database push. Measurement risk is near zero — the gains are already measured;
what remains is engineering fidelity.

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

**Rank 4, deliberately last, with a realistic prior of death.** The literature's
best-documented failure mode — stale last-trade prices in thin derivative markets
manufacturing apparent mispricing — is present in our data **by construction**, and Match
Odds leads price discovery 82–100%+ at the same one-minute sampling our archive has
(DR-COHERENCE-METHOD-001). The solver stays what it is today — built, tested, unused —
unless this single probe survives.

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

**Execution order: P2 → P1 → P3 → P4.**

---

## 4. True facts with nowhere to go

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
  is a parameter.

---

## 5. Standing guards that carry forward

- `tennis_edge/venues.py`: nothing synthetic and nothing closed to the UK can enter a
  settlement table without deleting a test.
- Provenance printed on every feature build (root, vintage id, manifest digest) — the
  two-data-roots incident does not recur silently.
- Golden vectors: Python and TypeScript scoring agree to 1e-12 on every push or the build
  is red.
- Fill evidence: universe in = filled + excluded, every exclusion with a reason.
- The settlement horizon is frozen at T-600s with its reason recorded; a horizon chosen
  against observed returns is a parameter, and the best one is always found afterwards.

---

## 6. Killed, and staying dead

One line each. Reopening any of these requires new external evidence and a founder
decision — not enthusiasm, not a fresh session forgetting why it died.

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
11. **Dispersion as a deployed feature** — true and undeployable; see §4; the governed
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

---

## 7. How the programme ends

Three ways, all acceptable, all pre-registered:

- **P1(a):** a cost-banded, falsification-surviving, hypothetical exchange edge on the
  full 2015–2026 archive — the strongest claim this data can ever support, clearly
  labelled as its ceiling, served by the P3-deployed model on a private single-user page
  that recommends nothing.
- **P1(b) or (c):** no edge, or an edge too small to matter — established cheaply and
  honestly, which was always the platform's stated job. The forecast result
  (+0.001064 nats) stands on its own as a measurement regardless.
- **P1(d):** undecided at the data's limit — recorded as undecided, with no verdict
  manufactured and no constraint bent to buy more data.

There is no fourth ending in which a constraint is softened to keep the programme alive.
