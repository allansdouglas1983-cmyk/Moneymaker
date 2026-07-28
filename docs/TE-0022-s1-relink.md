# TE-0022 — S1 closed: the guard passed, 778 matches recovered, nothing moved

The TE-0018 implementing slice, executed: the frozen rule classes landed as
`exchange-link-bridge-v2` (tests committed red first; strict resolutions never overridden;
ties, same-day collisions and everything short of exactly-one-candidate refuse; the
last-token fallback deliberately absent), plus the two typed exclusions
(`IMPLAUSIBLE_OFF_DATE` for the 2099 junk, `NOT_TWO_ACTIVE_RUNNERS` for walkover shells).
The price-table header now records `link_bridge_version`; legacy tables still load.

## The guard

`tools/build_prices_v3.py` replays the v2 merge byte-for-byte (tail then data2,
first-occurrence dedup, doubles dropped) under the extended bridge, and refuses to write
the table if any previously joined row changes:

```
S1 GUARD — v2 rows: 47,818  shared: 47,818  changed: 0  lost: 0  new: 778
```

**Every v2 row survives byte-identical.** The ~4 relist-steal candidates TE-0018 flagged
did not materialise as changes. The v3 table (48,596 priced matches) differs from v2 by
the bridge extension's recoveries and nothing else — so every conclusion drawn from v2
(TE-0019, TE-0020) stands on the new table's shared subset without re-litigation.

778 recoveries against TE-0018's measured 519: the 519 was measured on `match_odds2`
alone; the tail file's span (notably 2023–2026, which that measurement never opened)
contributes the remainder. Spread: 2015:128, 2016:56, 2017:62, 2018:43, 2019:50, 2020:21,
2021:68, 2022:59, 2023:60, 2024:135, 2025:65, 2026:31.

## The interim look (sequential accumulation — NOT a settled verdict)

One authorised re-score over the enlarged table, per the S1 acceptance rule:

| reading | bets | ROI | 95% CI |
|---|---|---|---|
| model, supported only | 25,250 | +2.57% | [+0.91%, +4.33%] |
| model, all fills | 38,314 | +2.37% | [+0.94%, +3.70%] |
| control, supported only | 24,031 | −1.44% | [−2.84%, +0.01%] |
| control, all fills | 35,469 | −1.30% | [−2.44%, −0.08%] |

Essentially unchanged from TE-0019 (+2.63% → +2.57% supported-only), as adding 1.6% more
markets should be. TE-0019/TE-0020 remain the registered verdicts; the TE-0020 execution-
cost band applies to these rows exactly as it did to v2's, and none of these numbers is
quotable without it.

## The selection-bias probe

The recovered cohort — visibly non-anglophone names, the exact worry S1 pre-registered —
scored alone: 576 bets all-fills +1.37% [−11.10%, +15.60%]; 364 supported-only −1.43%
[−14.28%, +12.39%]. Wide and uninformative, precisely as the TE-0017 power warning said it
would be, and with **no anomaly**: the recovered matches do not earn suspiciously more
than the rest (the suspected-bug trigger), nor suspiciously less. The bridge extension
changed coverage, not results.

## Standing state

`exchange_prices_600s_v3.jsonl` (48,596 matches, bridge v2, header-versioned) is the
table for future pre-registered work. Still open from TE-0018: the label cross-check
(GradingView vs corpus winner) requires the versioned extract-format bump and is its own
slice; Finding 0 (the 2022–2026 "tail" premise) remains with the founder.
