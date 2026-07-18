# Evidence freeze — June 2026 Betfair Tennis ADVANCED market-feasibility pilot

**Status:** FROZEN 2026-07-18. This directory is the permanent, immutable evidence record
of the Stage-1 market-feasibility pilot (authorised under ADR 0015's pilot carve-out:
one month, historical data only, no live activity). Nothing here is production code and
nothing here is importable by platform packages — `scripts/` is an archival record of
method, pinned to the digests below, not a library.

Closure artefacts that cite this directory: `specs/gates/market-m0.yaml` (Gate M0),
ADR 0018 (`docs/decisions/0018-june-tennis-market-feasibility-review.md`),
`specs/programme/baseline-v1.yaml`, `docs/architecture/stage2-probability-programme.md`.

## Chain of custody

| Artefact | Identity |
|---|---|
| Betfair order (portal cross-check) | Tennis (advanced), 1081 MB, 01 Jun 2026 – 30 Jun 2026, 20,482 markets |
| Delivered archive `data.tar` (private founder storage) | sha256 `bd69cd68fb5ac8cc6e1a0cb0d26d1fbf9b2e7179ff0fd9e1fdbdc8edb7b2c2ee` |
| Extracted corpus | 20,482 `.bz2` files; per-file manifest `corpus-file-sha256sums.txt` (this dir) |
| Corpus manifest digest | sha256 `d6d2f44b318aea425f3904ac83b8eb4a4bd067b7fe777c0375f107519162f9cc` |

Raw data storage follows the founder amendment in
`docs/procurement/tennis-pilot-purchase.md`: private, access-controlled founder storage;
pulled into the workspace only during analysis; **raw data never in this repository**
(this directory holds derived outputs and manifests only, per that same rule). Every
future workspace pull MUST verify against `corpus-file-sha256sums.txt`; the corpus was
re-verified in full **before and after** the price-analysis pass (all 20,482 pass).

## Frozen artefacts (in this directory)

| File | What it is | sha256 |
|---|---|---|
| `PRIMARY_JUNE_ANALYSIS_UNIVERSE_MANIFEST.csv` | One row per MATCH_ODDS market (3,521): date membership, MatchFormat, ClassificationEvidence, packaging status, universe membership, cohort tags | body digest (JSONL form) `ce9a147e64df0db5865dade4d78f0ae02cb93532c2f81518e9da313115029049` |
| `PRIMARY_JUNE_ANALYSIS_UNIVERSE_MANIFEST_header.json` | Universe rules + counts + digest (rules frozen, counts derived — never copied) | `760a2e8f9b7507357f4d205dc544192857e45f6a98ebaf9fcfe2f88c96086710` |
| `CANONICAL_REPLAY_MANIFEST.jsonl` | Every unique market (16,981) bound to exactly one canonical source + content hash — a market can never enter replay twice | `be2ae21a938fdc0ba2b4a9dfb21f6d4c8dcde699fab2f245383f19ed844bc617` |
| `CANONICAL_REPLAY_MANIFEST_header.json` | Replay-manifest counts + digests | — |
| `PILOT_REPORT.md` | The 15-section feasibility report delivered to the founder | `349cb6735383c0e4dd289a08bc23aa6446e6e28ad2d61816f6d44e2f4452e7e8` |
| `pilot_metrics.json` | Full machine-readable metrics behind every report table | `8fb1c8bfcec47ffd757fecd67112bef740146461f75be438cfbc80f9ecf7ca9e` |
| `corpus-file-sha256sums.txt` | Per-file corpus fingerprint (20,482 lines) | `d6d2f44b…` (above) |
| `scripts/` | The exact analysis method, archival copy (see below) | — |

## Regenerable intermediates (digest-pinned, not stored)

Bulk intermediates are deterministic functions of (raw corpus, `scripts/`) and are NOT
stored here; their digests pin them:

| Intermediate | sha256 |
|---|---|
| `full_corpus_metadata.jsonl` (16,955 market metadata records) | `08eb4befb9b64d9ab629a8aea630bc38add9e9341348fc920184e0e038a470c7` |
| `match_format_v2.jsonl` (frozen classifier output, 3,521 records) | `29d0c71dddf34fed159a8df3af18eab2824b9c4e7f3a48cdee9c0e141ae867c5` |
| `dedup_audit_output.jsonl` (packaging audit, 16,935 rows) | `b8d3470e9d3f86da0e5e1a884cd629eb13e43ccdee613f6c291d699508876564` |
| `recon_full.jsonl` (3,489 market reconstructions; replay result) | `3c1b64ab8d5c08f1bc654d690ac593ecb34dc073eb099f3d9abc7d4486a5d793` |

Determinism was proven by two independent full reconstruction runs producing
byte-identical `recon_full.jsonl` (same digest), and by per-market re-runs.

## Method archive (`scripts/`)

Pipeline order: `extract_metadata.py` → `run_full_scan.py` → `classify_v2.py`
(supersedes `classify.py`, kept for the audit trail of the founder's classifier
redesign decision) → `dedup_audit.py` + `extract_combined_only.py` →
`build_universe_manifest.py` → `build_canonical_replay_manifest.py` → `recon.py` +
`run_recon.py` (the governed as-of-published-marketTime horizon state machine) →
`aggregate.py` → `gen_report.py`. `final_report.py` is the earlier boundary-audit
driver (its date-membership section remains authoritative; its classifier section is
superseded by v2). Scripts reference the session workspace paths at which they ran;
they are frozen as run, not path-portable.

## Discipline attestation

- Universe, classifier and packaging policy were frozen and hashed **before** any
  price field was opened.
- No winners, settlement, P&L, returns, profitable subsets, selection rules, CLV or
  model performance were computed or inspected at any point in the pilot.
- Metadata extraction stops at the first `CLOSED` market definition and never reads
  `rc` price payloads; the price pass reads `batb`/`batl`/`trd`/`tv`/`ltp` and never
  reads runner win/lose status or any `sp*` (BSP) field.
- All prices handled as canonical integer tick indices (`price_contracts.ladder`,
  SPEC-053); all sizes as integer minor units. Zero off-ladder price events observed.
