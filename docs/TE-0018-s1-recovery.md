# TE-0018 — S1 recovery analysis: the unjoined archive, measured before any rule is touched

**Date:** 2026-07-28. **Programme item:** TE-0017 §4 S1, step 1 (funnel dump and recovery
ceiling) and step 4 (duplication accounting), executed **before** the identity bridge is
extended and before anything is re-scored. **Inputs:** `match_odds2.jsonl` (extract of
`data2.tar`, digest `sha256:e02730e1…`), corpus `vintage-2026-07-26` (107,927 matches,
2001-12-31 → 2026-07-19), and the frozen pipeline pieces exactly as `build_prices` uses
them: `read_extract` → `link_markets(horizon_seconds=600, use_ladder=False,
source=LAST_TRADED)`. Analysis only: no code changed, no test changed, no bridge rule
changed. **No outcome, winner, settlement or P&L field was read anywhere in this
analysis** — the funnel is names, dates, typed exclusions and pre-off prices, so this
document may lawfully inform the S1 bridge-rule freeze (TE-0017 §4 S1: "whoever writes
them sees no outcomes or P&L").

## Headline counts

| quantity | count |
|---|---|
| Extract rows / distinct market_ids | 523,618 / 259,711 (every duplicate byte-identical) |
| Archive span (non-junk) | 2015-04-30 → 2022-07-03 |
| Corpus matches inside the span | 32,746 |
| Linked by the frozen pipeline, deduplicated | **29,862** (current shipped table: 27,209) |
| Unjoined corpus matches in span | **2,884** (pre-registered on the old extract: 2,743) |
| — no candidate market in the extract | 1,938 (review estimate ~1,726) |
| — candidate market but no two-sided T-600s price | 425 (review estimate ~417) |
| — **recovered by the S1 diagnostic (distinct corpus matches)** | **519** (pre-registered ceiling ~600) |
| — recoverable only with a double-initial rule (Halep/Pliskova twins) | 2 |
| **ALREADY_CLAIMED markets (dedup) → additional corpus matches recoverable** | 8,010 → **0** |
| **Junk-2099-date markets needing a typed exclusion** | **3** distinct (6 rows) |

The measured recovery, 519 distinct corpus matches (521 with the double-initial rule),
sits **inside** the pre-registered ~600 ceiling. Nothing here revises the ceiling; the
recovered-cohort analysis of TE-0017 §4 S1 is sized against 519 actual matches, and the
"±6pp interval on ~600 bets" power warning applies a fortiori.

## Finding 0 — `data2.tar` is not the 2022–2026 tail

TE-0017 describes `data2.tar` / `match_odds2.jsonl` as "the 2022–2026 archive tail". The
bytes say otherwise: the extract's MATCH_ODDS content runs **2015-04-30 → 2022-07-03**
(13,843 distinct singles markets after 2022-03-14, against 1,738 corpus matches in that
window) and contains nothing from 2023–2026. It is a **re-pull of the same 2015–2022 span
the shipped table already covers, plus ~3.5 months and ~8.6% more markets** (259,711
distinct vs 239,168 in `match_odds.jsonl`; both tars flag `source_truncated`). Two
consequences:

1. **This analysis did not open any 2022–2026 tail** — no such data exists in the file.
   The freeze discipline of TE-0017 §5 is intact; this run joined names and read pre-off
   prices on a span that was already joined and scored, plus a 3.5-month extension that
   was joined here but **not scored** (no settlement, no model, no outcomes touched).
2. **P1's premise needs a data re-inventory before anything else.** The tail that
   "roughly doubles the settlement sample" is not on disk. Under constraint §2.3/§2.4
   (no paid data, no account activity) the founder must resolve where — or whether — the
   2023–2026 BASIC data can lawfully be obtained before P1's n\* ≈ 31,000 arithmetic is
   quoted again.

## Duplication (S1 step 4)

`match_odds2.jsonl`: 523,618 data rows over 259,711 distinct market_ids — 257,595 ids
appear exactly twice, 2,104 exactly four times, 12 once. **Every duplicate row is
byte-identical to its first occurrence** (verified by per-id line hashing), so
first-occurrence dedup is lossless. The pollution of a naive funnel is exactly as S1
warned:

| funnel line (singles, in corpus range) | raw (as `read_extract` yields) | dedup | factor |
|---|---|---|---|
| universe | 523,618 | 259,711 | ×2.016 |
| linked | 29,862 | 29,862 | ×1 (identical set) |
| UNRESOLVED_NAME | 325,193 | 161,244 | ×2.017 |
| ALREADY_CLAIMED | 48,733 | 8,010 | ×6.08 |
| NO_MATCH_ON_DATE | 38,508 | 19,248 | ×2.00 |
| NO_PRICE_AT_HORIZON | 2,930 | 2,408 | ×1.22 |

Duplicates never change the **linked set** (the first copy claims the match; later copies
land ALREADY_CLAIMED), so dedup is a *reporting* fix, not a join fix — but ALREADY_CLAIMED
inflates ×6 because it absorbs the duplicate copy of every linked market as well as every
duplicate of a genuine relist. Any funnel quoted from this file without market_id dedup is
wrong by the factors above.

## ALREADY_CLAIMED: zero recoverable matches

After dedup, 8,010 ALREADY_CLAIMED markets remain (all singles, in range). Resolving each
one's runner pair through the same per-day bridge shows they point at **7,991 distinct
corpus matches, every one of which is already linked by a different market_id** (7,978
matches carry one extra market, 7 carry two, 6 carry three; 0 unidentifiable). These are
Betfair relists/parallel listings of the same fixture. **ALREADY_CLAIMED recovers zero
additional corpus matches.**

One determinism note for the implementing slice: 3,184 of the 8,010 extra markets carry
their own two-sided T-600s price, i.e. ~3.1k matches have two priced markets and the
linker keeps whichever comes first in file order. The S1 guard ("no previously joined row
may change quote or orientation") must therefore be checked against the *re-extracted*
file, whose member order decides which market prices those matches.

## UNRESOLVED_NAME: 519 recoverable corpus matches

161,244 dedup singles-in-range markets are UNRESOLVED_NAME. Per-name bridge reasons
(replicating the per-day scoping exactly):

| name-reason combination | markets |
|---|---|
| both sides NO_SOURCE_MATCH | 154,713 |
| one side resolved + NO_SOURCE_MATCH | 5,468 |
| no two ACTIVE runners (empty reason set) | 550 |
| HOMONYM_MULTIPLE_SOURCE + resolved | 287 |
| HOMONYM_MULTIPLE_BETFAIR + resolved | 111 |
| other combinations | 115 |

The mass (154,713 + most of 5,468) is lower-tier play (ITF/Challenger/qualifying) that the
Tennis-Data corpus does not cover — names absent from the day card by construction, not
name-normalisation failures. The recovery diagnostic separates the two honestly: a market
counts as recovered only if its runner pair identifies **exactly one** corpus match in the
±1-day window under a deterministic relaxed matcher, that match is **unclaimed** by the
strict run, and the market has a **two-sided T-600s LTP price** — the same conditions a
linked row must meet.

| recovery funnel over the 161,244 markets | count |
|---|---|
| no relaxed candidate pair (out-of-corpus play) | 160,483 |
| **RECOVERED (unique pair + unclaimed + priced)** | **519** |
| second market for an already-recovered match | 174 |
| unique pair but no two-sided T-600s price | 62 |
| pair's match already linked by another market | 4 |
| ambiguous pair even relaxed | 2 |

**Rule classes that produced the 519** (each deterministic and round-trip-verifiable,
matching the classes pre-named in TE-0017 §4 S1 step 2):

- **369** — hyphen/apostrophe relaxation, after which the existing bridge rule matches
  ("Carreno Busta" ↔ "Carreno-Busta P.", "Soler-Espinosa" ↔ "Soler Espinosa S.",
  "Duque-MariÑo" ↔ "Duque Marino M."); this class also contains homonym refusals that the
  pair context disambiguates ("Karolina Pliskova" + opponent + day → "Pliskova Ka.").
- **150** — surname-token subset + first-initial (Spanish/double surnames Tennis-Data
  truncates: "Roberto Bautista Agut" ↔ "Bautista R.", "Mirjana Lucic-Baroni" ↔
  "Lucic M.").
- **0** — the last-token fallback rule fired never on its own: the two classes above are
  the whole story.

The 2 ambiguous residuals are the Halep–Pliskova twins (Madrid 2018: Kristyna on
2018-05-09, Karolina on 2018-05-10, two markets inside one ±1-day window; TD separates
them only by two-letter initials "Kr."/"Ka."). A **longest-initial-prefix rule** (prefer
the source whose initials match the longer prefix of the Betfair first name) resolves both
deterministically → measured recovery ceiling **521**. The recovered cohort is visibly
non-anglophone (diacritics, particles, double surnames), exactly the selection-bias
probe S1 pre-registered.

The 62 priced-out recoveries would land as typed NO_PRICE_AT_HORIZON after the bridge
extension — correct behaviour, not loss.

## Junk-2099 dates: 3 markets need a typed exclusion

Three distinct markets (6 rows) carry off-times in 2099: `1.124047987` and `1.124047988`
(the same Kellovsky v Diaz-Figuer fixture listed twice) and `1.167784674` ("Test1 v
Test2" — a Betfair test market). Today they fall through as NO_MATCH_ON_DATE, which
conflates provider data damage with genuine coverage gaps. The extract/link should refuse
them with their own typed exclusion (e.g. `IMPLAUSIBLE_OFF_DATE`, off-time outside the
archive's plausible window) so that a future extract — where such junk may be more
frequent — cannot silently pollute the date funnel. Count today: **3 markets**.

Minor inventory, same discipline: 8 distinct markets have ≠2 runners and 550
singles-in-range markets have no two ACTIVE runners; both currently land in
UNRESOLVED_NAME, where a typed `NOT_TWO_ACTIVE_RUNNERS` would say what they are.

## Doubles in the day card: measured, negligible

Doubles markets (37,653 dedup; runner names containing "/") enter the per-day bridge card
and can in principle manufacture homonym refusals against singles sources. Measured by a
singles-only re-link: **+1 linked match, −2 UNRESOLVED_NAME** — real, and negligible.
Not the mechanism to chase; recorded so nobody chases it.

## What this changes, and what it does not

- The re-pull alone (no rule change) lifts the joinable set from 27,209 to **29,862**
  matches (+2,653, +9.8%) — of which the 2022-03-15 → 2022-07-03 extension contributes at
  most 1,738 — and the frozen S1 bridge extension adds at most **521** more, to a ceiling
  of 30,383 priced matches from this file. Any re-scored interval over this enlarged set
  is an **interim look under sequential accumulation** per the S1 acceptance rule, never
  a settled verdict.
- Nothing in this document is a bridge rule. The implementing slice freezes the two
  measured rule classes (hyphen/apostrophe relaxation; surname-token-subset) plus the
  longest-initial-prefix double-initial rule as a **versioned** bridge change, re-runs the
  scored pipeline **once**, and verifies the S1 guard that no previously joined row
  changes quote or orientation (including the 3,184 dual-priced relists above).
- The label cross-check (S1 step 3, GradingView vs corpus winner) remains to be done in
  the implementing slice — it requires the versioned extract-format bump and grading-time
  data this analysis deliberately did not touch.
- **Finding 0 goes to the founder:** the 2022–2026 tail the programme is sequenced around
  is not in `data2.tar`.

## Method appendix

Pipeline calls: `read_extract("…/match_odds2.jsonl")` → dedup by first occurrence of
market_id (byte-identity verified) → `link_markets(markets, load_corpus(latest_vintage(
"/home/user/tennis_edge_data").root)[0], horizon_seconds=600, use_ladder=False,
source=PriceSource.LAST_TRADED)`. Market classes: junk (off year ≥ 2090), doubles ("/" in
any runner name), ≠2 runners, singles-in-corpus-range. Relaxed matcher (diagnostic only,
never a shipped rule): td-norm-v1 normalisation, then apostrophes removed and hyphens
spaced on both sides; rule 1 = the bridge's split-point + initials-prefix rule on the
relaxed text; rule 2 = TD surname tokens ⊆ Betfair tokens after the first + first-initial
equality; rule 3 = last-surname-token + first-initial equality (never needed alone).
Recovery requires pair uniqueness in the ±1-day window, an unclaimed match (linked set +
prior recoveries, processed in file order), and `exchange_probability(…, 600s,
LAST_TRADED) is not None`. Price reads are pre-off; no grading-time field exists in the
extract schema. Intermediate artefacts (JSON checkpoints, run log) live in the session
scratchpad only; this document and its counts are the durable record.
