# specs/prices — FROZEN price definitions

**Spec:** SPECIFICATION.md §4 · **Human-owned** (see `CODEOWNERS`).

`info-price-v1.yaml`, `exec-price-v1.yaml`, `close-v1.yaml`. These fix the three prices
(`p_market_info`, `odds_exec`, `p_close`) and **must be frozen BEFORE any performance is
examined** (Phase 0). Changing `p_market_info` after seeing results is changing the model.

> **Deliberately not fabricated by the agent.** The field values (midpoint space, stale-data
> threshold, normalisation, spread adjustment, latency assumption, …) are researcher
> pre-registration decisions. Templates are in SPECIFICATION.md §4.1–§4.3. To be authored
> and frozen by a human in Phase 0.
