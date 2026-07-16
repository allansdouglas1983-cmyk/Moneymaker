# Betfair ADVANCED pilot — purchase, download, checksum and ingestion runbook

**Preconditions (ALL must hold before step 1):** GAMSTOP cooling-off complete; the
founder's EXISTING Betfair account restored through the official process; lawful
access confirmed by the founder; the founder's final confirmation of the selected
month (documented default: **January 2026**). Executed by the FOUNDER on their LOCAL
machine — nothing here runs in CI, cloud, or this repository's containers (ADR 0015 /
local-only constraint until Betfair's written cloud/CI answer).

## 1. Pre-purchase coverage check (metadata only)

On https://historicdata.betfair.com (logged in), select: Sport **Horse Racing**, Plan
**ADVANCED**, Month **January 2026**, filter Country **GB**, Market type **WIN**, File
type **M**. The portal shows the file/market count for the selection BEFORE payment.

- Expected band: roughly **180–280** GB WIN all-weather-season markets. (January is
  AW-dominated but the GB filter includes any turf fixtures that survived weather.)
- Count far outside the band → STOP, report the number to the agent before buying.
- Do not open any data preview beyond counts; no prices, no outcomes.

## 2. Purchase

Buy exactly: **ADVANCED / Horse Racing / January 2026 — £69.00**, billed to the
Betfair account (statement line `ADVANCED Horse Racing Jan 2026`). Nothing else. Keep
the confirmation email/statement entry for the budget record.

## 3. Download (local machine only)

Via the portal's My Data (or the Historical Data API `DownloadListOfFiles` flow) with
the same filter (GB / WIN / M-files). Suggested local layout (OUTSIDE any git repo):

```
~/moneymaker-data/betfair/advanced/2026-01/raw/   # the .bz2 files exactly as downloaded
~/moneymaker-data/betfair/advanced/2026-01/MANIFEST.sha256
~/moneymaker-data/betfair/advanced/2026-01/PROVENANCE.txt
```

## 4. Checksum process (immediately after download, before anything reads the data)

```bash
cd ~/moneymaker-data/betfair/advanced/2026-01
find raw -type f -name '*.bz2' | sort | xargs sha256sum > MANIFEST.sha256
sha256sum MANIFEST.sha256          # record this ONE digest — it pins the whole corpus
wc -l MANIFEST.sha256              # file count: must match the portal's pre-purchase count
du -sh raw                         # size sanity
```

Record in `PROVENANCE.txt`: purchase date/time, statement reference, portal file count,
the manifest digest, download completion time (UTC), and the runbook version used.
Send the agent: the manifest digest, file count, and total size. The manifest digest
(never the data) is what enters the repository's records — it makes every later
conclusion pin to an exact immutable corpus.

Re-verification any time: `sha256sum -c MANIFEST.sha256`.

## 5. Ingestion (local, deterministic, backfill-provenance)

Betfair historical files are bz2-compressed line-delimited `mcm` JSON in the Exchange
Stream format. Ingestion wraps each line as an l0 raw record with **backfill
provenance** (SPEC-023: backfilled data declares its true publication time — the `pt`
field — and is marked `provenance: backfilled`, never passed off as live-captured).

```bash
# from the repo checkout on the local machine:
uv run python -m tools.ingest_historical \
  --source-dir ~/moneymaker-data/betfair/advanced/2026-01/raw \
  --manifest   ~/moneymaker-data/betfair/advanced/2026-01/MANIFEST.sha256 \
  --output-dir ~/moneymaker-data/betfair/advanced/2026-01/l0 \
  --provenance backfilled
```

The tool (a) refuses to run if any file fails its manifest checksum, (b) is
deterministic (same input → byte-identical output + ingestion report digest),
(c) never mutates the raw files, (d) emits an ingestion report (files, lines, markets,
first/last `pt`, output digest) — send the report to the agent, not the data.

> Status: `tools/ingest_historical.py` is being built now under the authorised
> offline-plumbing scope, red-tests-first, exercised against SYNTHETIC stream-format
> fixtures only. This runbook will not be executable until that slice lands green —
> it will land well before the cooling-off + restoration window closes.

## 6. After ingestion

Reducer replay (l1) over the l0 output, then feature-build dry-run (l3) — commands to
be appended to this runbook when the ingestion slice lands. Results (digests + counts
only) come back to the agent for the pilot report. No lockbox is defined over pilot
data; the pilot cohort is pre-registered as PILOT and excluded from EXP-0001's corpus.

## What this runbook never does

No live API, no order endpoints, no Live App Key, no deposits, no cloud upload, no
CI fixtures from raw data, no additional purchases beyond the single confirmed month.
