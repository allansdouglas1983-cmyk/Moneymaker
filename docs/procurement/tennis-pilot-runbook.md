# DR-TENNIS-MARKET-002B — pilot runbook: storage, checksum, ingestion, frozen analysis

**Not executable yet** — blocked on ADR 0015, ADR 0016 approval, price confirmation,
and founder month confirmation (see `tennis-pilot-purchase.md`). Prepared in advance
so execution is immediate once unblocked, mirroring the racing pilot's runbook
discipline (`docs/procurement/betfair-pilot-runbook.md`).

## Local storage and checksum (identical discipline to the racing pilot)

```
~/moneymaker-data/betfair/advanced/tennis-2026-04/raw/        # .bz2 files exactly as downloaded
~/moneymaker-data/betfair/advanced/tennis-2026-04/MANIFEST.sha256
~/moneymaker-data/betfair/advanced/tennis-2026-04/PROVENANCE.txt
```

```bash
cd ~/moneymaker-data/betfair/advanced/tennis-2026-04
find raw -type f -name '*.bz2' | sort | xargs sha256sum > MANIFEST.sha256
sha256sum MANIFEST.sha256          # the one digest that pins the whole corpus
wc -l MANIFEST.sha256              # file count: must match the portal's pre-purchase count
```

Record in `PROVENANCE.txt`: purchase date/time, statement reference, portal file
count, manifest digest, download completion time (UTC). Send the agent the digest,
count, and size — never the data. Local-only processing applies here exactly as it
does to the racing pilot (ADR 0015): no cloud, no CI, until Betfair's written
cloud/CI answer arrives.

## Ingestion command

Reuses the existing (sport-agnostic) ingestion tool — Betfair's `mcm` stream format
and manifest-gate discipline are identical across sports; only the portal-level
download filter (Tennis vs Horse Racing) differs, which happens before this step:

```bash
uv run python -m tools.ingest_historical \
  --source-dir ~/moneymaker-data/betfair/advanced/tennis-2026-04/raw \
  --manifest   ~/moneymaker-data/betfair/advanced/tennis-2026-04/MANIFEST.sha256 \
  --output-dir ~/moneymaker-data/betfair/advanced/tennis-2026-04/l0 \
  --provenance backfilled
```

> Status note: `tools/ingest_historical.py` has red tests committed
> (`tests/unit/tools/test_ingest_historical.py`) with its reviewed implementation
> held pending `make verify` green (Phase 3A / test-correction 0002 status) — same
> tool the racing pilot runbook depends on. Landing it is independent of the sport.

## Frozen pilot-analysis specification (pre-registered before any data is read)

This is a PILOT, not the primary experiment — its cohort is excluded from any
future tennis EXP corpus by construction. Metrics computed, all descriptive, none
gate-eligible:

1. **Market counts**: total Tennis MATCH_ODDS markets in the file set; split by
   tournament, cross-referenced against the known ATP/WTA calendar (§3 of the
   purchase spec) to classify ATP main-tour / WTA main-tour / Challenger /
   qualifying / doubles.
2. **Data completeness**: markets with a full pre-off `marketDefinition` +
   settlement record vs. markets with gaps; explicit count of each.
3. **Pre-match spread**: best-back/best-lay spread sampled at T-30m, T-10m, T-2m,
   T-60s relative to scheduled off, per market, aggregated by tour level.
4. **Quote depth**: displayed size at best-back/best-lay at the same four
   horizons, for a stated candidate fixed stake (a placeholder stake for
   measurement purposes only — no staking decision is made here).
5. **Total matched volume**: per market and aggregated by tour level/tournament.
6. **Clean pre-match book %**: fraction of markets with a two-sided quote at every
   sampled horizon (never one-sided or crossed) — reuses the crossed/one-sided
   book policy concepts from `specs/prices/info-price-v1.yaml`, evaluated
   descriptively here, not as a live pricing decision.
7. **FOK full-fill feasibility (descriptive)**: for the candidate fixed stake, the
   fraction of markets where displayed depth at decision-time best-back would have
   covered the full stake at each horizon — a scenario count, not an executed or
   simulated fill (SPEC-040/043's fill-probability modelling is Phase 5, untouched).
8. **Retirement/void frequency**: count of markets settled VOID vs. WINNER/LOSER,
   for this month/surface only (explicitly descriptive, not a general base rate —
   see `tennis-pilot-purchase.md` §5).
9. **Suspensions and delayed starts**: count and duration, from `marketDefinition`
   status transitions.
10. **Countries/tournaments represented**: enumerated list with market counts.

**Output**: a report (counts, rates, digests — no raw data) recommending an initial
universe (e.g. "ATP+WTA main-tour singles, Match Odds, pre-match, back-only" vs. a
narrower or broader alternative) with the evidence for the recommendation stated
plainly. This report is the primary input to DR-TENNIS-MARKET-002's decision;
DR-TENNIS-MARKET-002A's desk-research numbers remain SECONDARY throughout and are
never substituted for these measured values.

## What this pilot does NOT establish (DR-TENNIS-MARKET-002C, deferred)

Real account latency, actual FOK execution outcomes, real fill behaviour, or market
impact from live order flow — historical data cannot prove any of these. That
validation remains blocked until the existing pricing gates (1–2) pass and a
live-canary is separately approved; nothing in this pilot or its report shortcuts
that.
