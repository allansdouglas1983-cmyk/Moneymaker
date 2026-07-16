# Provider enquiry draft — Timeform API

**Status:** DRAFT for founder review and sending (founder decision 4, 2026-07-16).
Not sent by the agent. No commercial terms may be accepted without human review.
Suggested route: the Timeform commercial/data-services contact on timeform.com, or
via Betfair Developer Support referencing the "Guide to the Timeform API" page
(the API is positioned for Betfair customers — the founder is one).

---

**Subject:** Timeform API — personal-use research enquiry, GB all-weather historical
data with publication-time provenance

Dear Timeform team,

I am a private individual and Betfair customer conducting personal, non-commercial
research into British all-weather racing, building statistical models for my own
private use. The Betfair developer pages indicate the Timeform API is available to
Betfair customers for private or commercial use. Before any commercial discussion I
would appreciate the following:

**1. Product and coverage.** Does the API (or a file-extract alternative) provide
machine-readable GB all-weather coverage (Lingfield, Kempton, Wolverhampton,
Southwell, Newcastle, Chelmsford) including runners, trainers, jockeys, going,
distance, race class, ratings (Timeform and/or official), entries/declarations, and
non-runner information? How far back does machine-readable historical backfill go?

**2. Sample and dictionary.** Could you share a sample payload and data dictionary
for the pre-race endpoints?

**3. Publication-time provenance (essential for me).** My research depends on
establishing what was knowable before each race. Are historical records preserved
with field-level publication timestamps or immutable pre-race snapshots (e.g. the
declaration-time card as it stood, non-runner announcement times, the date a rating
took effect)? Or is historical data stored as a single post-race-updated record? If
snapshots exist, at which stages (entry, declaration, final card)?

**4. Licence scope for personal research.** For private, personal use: please
confirm whether offline research, statistical model training, raw-data retention,
retention of derived models, and processing on my own local machines (and, if
different, on rented cloud infrastructure) are permitted. I do not require
publication, redistribution, or customer-facing rights.

**5. Pricing structures.** Current pricing for: (a) a one-off historical extract of
GB all-weather backfill; (b) a monthly pilot subscription; (c) minimum commitment.
Personal-scale options preferred — I am an individual, not a business.

Kind regards,
[Founder name]

---

**Reviewer notes (not part of the email):** Timeform is RDC-appointed for official
British pre-race data and Flutter-owned (operational synergy with Betfair, not a
licence shortcut). The 2014 price signal (£500–£1,500/month) is stale; treat any
quote near that level as a fund-or-descope decision point. Question 3 is decisive
for SPEC-020/023 usability.
