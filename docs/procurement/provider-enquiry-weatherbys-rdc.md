# Provider enquiry draft — Weatherbys / Racecourse Data Company (official pre-race data)

**Status:** DRAFT for founder review and sending (founder decision 4, 2026-07-16).
Not sent by the agent. No commercial terms may be accepted without human review.
Suggested recipients: Weatherbys Data Supply (datasupply@weatherbys.co.uk or the
contact form on the Data Supply page) and/or Racecourse Data Company licensing
contact — the founder should confirm current addresses from the official sites.

---

**Subject:** Personal-use research enquiry — machine-readable GB all-weather pre-race
data with publication-time provenance

Dear Weatherbys Data Supply team,

I am a private individual conducting personal, non-commercial research into British
all-weather horse racing, building statistical models for my own private use. I am
interested in licensing official pre-race data and would appreciate answers to the
following before any commercial discussion:

**1. Product and coverage.** Do you offer a machine-readable feed or file extract
(API, JSON/CSV/XML files) covering GB all-weather racing (Lingfield, Kempton,
Wolverhampton, Southwell, Newcastle, Chelmsford) including: runners, trainers,
jockeys, going, distance, race class, official ratings, entries/declarations, and
non-runner announcements? What historical backfill is available (how many years)?

**2. Sample and dictionary.** Could you provide a sample payload and a data
dictionary for the relevant products?

**3. Publication-time provenance (essential for me).** My research depends on knowing
what information was published at what time before each race. Do your products carry
field-level timestamps (e.g. declaration publication times, non-runner announcement
times, the date each official rating took effect), or immutable point-in-time
snapshots? If not timestamped per field, is there a formal documented publication
schedule I can rely on (e.g. overnight declarations at 10:30, ratings each Tuesday)?

**4. Licence scope for personal research.** For a personal-use licence, please
confirm whether the following are permitted: offline research and analysis; training
statistical models; retention of the raw data for the licence term and beyond;
retention of models derived from the data; processing on my own local machines; and
processing on cloud infrastructure I rent (if that differs from local processing).
I do not require any publication, redistribution, or customer-facing rights.

**5. Pricing structures.** Please indicate pricing for: (a) a one-off historical
extract (e.g. one to three years of GB all-weather backfill); (b) a monthly
subscription suitable for a pilot; and (c) your minimum commitment, if any. I am an
individual researcher, so personal-scale pricing options are what I am looking for.

Thank you — happy to provide more detail on the research if useful.

Kind regards,
[Founder name]

---

**Reviewer notes (not part of the email):** if Weatherbys redirect to RDC for
licensing, the same questions apply verbatim. Responses feed
`docs/research/ledger.yaml` (DR-0002 unresolved items) and, if terms are acceptable,
a `docs/licensed-sources.yaml` entry under the test-correction-0001 review-date
discipline. Question 3's answer is decisive: no provable publication times = fails
SPEC-020/023 and the source is not usable regardless of price.
