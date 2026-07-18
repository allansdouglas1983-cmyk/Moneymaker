# Tennis-Data acquisition + acceptance evidence (vintage-2026-07-18) — FROZEN

Founder-approved primary longitudinal results source (rights record:
docs/procurement/tennis-data-rights-and-gate-minus1.md — evidence file pending
ingestion). Raw files live OUTSIDE the repo (session workspace + founder private
archive); this dir holds manifests, provenance and audit outputs only.

- 47 raw files (ATP 2000–2026, WTA 2007–2026), byte-preserved under
  raw/vintage-2026-07-18/ (vintage discipline: provider changes => NEW vintage, never
  overwrite). Sorted per-file MANIFEST.sha256; manifest digest
  d9af2525055c61ecc9e010c04604a3359ebe2a1fe786cba9f496d972091d0ceb.
- PROVENANCE.json: per-file source URL, source file name, retrieval UTC timestamp,
  sha256, size, and observable provider version headers (Last-Modified/ETag).
- acceptance_report.json: the governed §3 audit (117,276 pre-June singles matches;
  boundary 2026-06-01 strict — 620 post-boundary rows COUNTED NEVER READ; 1 winner
  conflict excluded; 5 ambiguous rows; surfaces complete; odds columns catalogued by
  name/null-count only and QUARANTINED). Report digest
  102faf23ead5999a55b9c388a4cf0595935ee81c3ecea216b1e3b2716de524ff.
- identity_resolution_report.json: bridge run (td-norm-v1) vs June Betfair primary-
  universe runner NAMES (metadata only): 657/1,471 players mapped; per-market both-
  mapped 1,218/2,876 (42.4%; strict 50.5%); unresolved ledger with typed reasons.
- No June outcome was read; no bookmaker-odds value entered any pipeline.
