# specs/prices — FROZEN price definitions

**Spec:** SPECIFICATION.md §4 · **Design:** `docs/decisions/0009-price-preregistration.md` · **Human-owned** (see `CODEOWNERS`).

The three prices (`p_market_info`, `odds_exec`, `p_close`), each versioned and **frozen before any
performance is examined** (§4). Changing a value is a new version + a new pre-registered experiment,
never an in-place edit after results are seen.

| File | Price | Role |
|---|---|---|
| `info-price-v1.yaml` | `p_market_info` | model input — normalised implied-prob midpoint of best back/lay, no size weighting in v1 |
| `exec-price-v1.yaml` | `odds_exec`     | transactable now — BACK, taker-v1 (FOK, full size), worst-acceptable bound, no partial fill |
| `close-v1.yaml`      | `p_close`       | diagnostic only — BSP + pre-suspension WAP(60s) |

**Status: frozen (v1).** Pre-registered as ADR 0009 **before any historical data was ingested or
examined** — the correct pre-registration posture (there is nothing to cherry-pick against). The
Phase-2 `p_market_info` builder consumes `info-price-v1`; the decision layer's `odds_exec` follows
`exec-price-v1`; grading uses `close-v1`.
