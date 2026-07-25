# Personal Tennis Assistant V0 — quick start

**RESEARCH / SHADOW ONLY — NO BET RECOMMENDATION.**

Private, single-user, local, offline. No account, no server, no API key, no paid service, no
betting. V0 shows you the **market-implied probability** of a tennis Match Odds book you type
in yourself, optionally alongside the **frozen F2-v1 diagnostic** (clearly labelled, never the
answer), records what it believed **before** the match, and later scores how good those
probabilities were.

---

## 1. Prerequisites

- This repository, checked out locally.
- Python 3.11 and [`uv`](https://docs.astral.sh/uv/) (already used by the repo).
- Nothing else. No credentials, no network access, no subscription.

## 2. Setup (one command)

```bash
uv sync
```

Everything below runs from the repository root.

## 3. Create an assessment (one command)

Write a snapshot file with what you can see in the Betfair UI, then:

```bash
uv run python -m assistant_v0.cli assess \
  --snapshot docs/v0/sample/sample_snapshot.json \
  --reference-time-ms 1749999460000 \
  --out my_assessment.json
```

- `--snapshot` — your match file (copy `docs/v0/sample/sample_snapshot.json` and edit it).
- `--reference-time-ms` — "now" in Unix milliseconds; used only to compute the quote age.
  Get one with `python -c "import time; print(int(time.time()*1000))"`.
- `--out` — optional; where to write the deterministic JSON. It is also printed to stdout.

**Optional — add the F2-v1 diagnostic** by pointing at a frozen rating file
(`docs/v0/sample/sample_ratings.json` is a synthetic example):

```bash
  --ratings docs/v0/sample/sample_ratings.json
```

Without `--ratings`, the assistant is `MARKET_ONLY` — which is the honest default.

### The snapshot file

```json
{
  "competitor_a": "Player A",  "competitor_b": "Player B",
  "competitor_a_id": null,     "competitor_b_id": null,
  "tour": "ATP",
  "scheduled_start_ms": 1750000000000,
  "input_timestamp_ms": 1749999400000,
  "source": "MANUAL_BETFAIR_UI",
  "back_a": "1.90", "back_a_size": "120", "lay_a": "1.95", "lay_a_size": "95",
  "back_b": "2.04", "back_b_size": "88",  "lay_b": "2.12", "lay_b_size": "60",
  "market_status": "OPEN", "in_play": false,
  "market_id": "1.234", "event_id": "E1"
}
```

- `tour` — `ATP` or `WTA`.
- `source` — `MANUAL_BETFAIR_UI` (typed by hand) or `LOCAL_SNAPSHOT_JSON` (from a local file).
- Prices are **strings** and must be real Betfair ladder prices (e.g. `1.90`, not `1.905`).
- Sizes must be greater than zero on **both** sides of **both** players; otherwise the book is
  not two-sided and no probability is produced.
- `input_timestamp_ms` must not be after `scheduled_start_ms` — no entering a "pre-match"
  snapshot once the match has started.

## 4. Render the report (one command)

Add `--html` to the same `assess` command:

```bash
uv run python -m assistant_v0.cli assess \
  --snapshot my_match.json --reference-time-ms 1749999460000 \
  --html my_report.html
```

Open `my_report.html` in any browser. It is a plain static file — no server, no JavaScript
required. A rendered example ships at `docs/v0/sample/sample_report.html`.

## 5. Record it in your shadow ledger

Add `--ledger` and a unique `--record-id` to keep an immutable pre-match record:

```bash
uv run python -m assistant_v0.cli assess \
  --snapshot my_match.json --reference-time-ms 1749999460000 \
  --ledger ~/tennis_ledger.jsonl --record-id 2026-07-25-alcaraz-sinner
```

The pre-match record can never be rewritten and contains **no outcome field at all**.

## 6. Append the outcome after the match (one command)

```bash
uv run python -m assistant_v0.cli settle \
  --ledger ~/tennis_ledger.jsonl \
  --record-id 2026-07-25-alcaraz-sinner \
  --winner A
```

`--winner` is `A` or `B` (competitor A or B **as named in that snapshot**). This *appends* the
result and the scores; the original pre-match record is untouched. Settling the same record
twice is refused.

## 7. Inspect the ledger (one command)

```bash
uv run python -m assistant_v0.cli ledger --ledger ~/tennis_ledger.jsonl
```

Prints a deterministic summary: how many matches you recorded, how many were scored, how many
were excluded and why, and the mean **log loss** and **Brier score** for the market
probability and (separately) for the F2-v1 diagnostic. Lower is better for both.

## 8. Where files go

| What | Where |
|---|---|
| Your snapshots | wherever you put them (e.g. `~/tennis/snapshots/`) |
| JSON assessment | the `--out` path you choose |
| HTML report | the `--html` path you choose |
| Shadow ledger | the `--ledger` path you choose (a single append-only `.jsonl`) |
| Worked example | `docs/v0/sample/` in this repository |

Nothing is written anywhere you did not name. The tool never phones home.

## 9. Backing up your ledger

The ledger is one plain append-only JSONL file — one JSON object per line. To back it up:

```bash
cp ~/tennis_ledger.jsonl ~/backups/tennis_ledger.$(date +%Y%m%d).jsonl
```

Recommended: copy it after each settle, keep it in a directory you already back up, and never
hand-edit it. If a line is ever corrupted, keep the original file — the loader refuses rather
than silently repairing, and your earlier records remain readable above the damaged line.

## 10. Limitations — read this

- **The final probability is the market's.** F2-v1 is displayed as a labelled diagnostic
  (`MODEL_DIAGNOSTIC_NOT_MARKET_PROVEN`) and can never become or alter the final probability.
- **F2-v1 is not proven to beat the market.** It is a frozen historical baseline shown for
  interest and for measurement, nothing more.
- **No betting advice of any kind.** V0 computes no expected value, no edge, no stake, no ROI,
  no P&L, no CLV, and issues no tip or recommended side. Those fields do not exist in the code.
- **You type the prices.** The assistant has no market feed; it is exactly as current as the
  numbers you entered, and it tells you the quote age so you can judge that.
- **Single user, local only.** No accounts, no sharing, no public exposure, no multi-user access.
- **Statuses you can see:** `INSUFFICIENT_DATA`, `MARKET_UNAVAILABLE`, `MARKET_ONLY`,
  `MODEL_VIEW_ONLY`, `NO_BET_RESEARCH_ONLY`. There is no bet-candidate state, and none can be
  constructed.
- **A refusal is a result.** A crossed, suspended, in-play or one-sided book produces no
  probability rather than a guess.
