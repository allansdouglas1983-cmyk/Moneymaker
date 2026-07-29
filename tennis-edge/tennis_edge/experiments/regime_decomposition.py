"""TE-0033: composition or sharpening — decomposing the post-2023 decline. Diagnostic only.

Three independent diagnostics point at 2023/24: the exchange-anchor advantage halved once
2023-2026 entered (TE-0019), the model's gain concentrated on fresh prices (TE-0024), and
the fitted anchor temperature flipped sign (TE-0028). This registration asks the one
question they share: did the MIX of matches in the BASIC archive change (composition), or
did the same strata get harder (sharpening)? Nothing here changes any served model,
threshold or policy; a serving restriction to any stratum would need its own registration.

DECLARATIONS, fixed before the run
----------------------------------
- Rows: the standard feature cache joined to the v4 exchange table on
  (date, tour, player_a, player_b) — the S8/S9 join, unchanged.
- Strata (8 cells, declared coarse so every cell is populated in both eras):
  tour {ATP, WTA} x slam {Grand Slam, other} (corpus tier field) x exchange favourite
  band {<= 0.65, > 0.65} (favourite implied probability from the de-vig exchange prices;
  knowledge-time-safe). Rows failing the corpus tier join are a typed exclusion.
- Eras: PRE = scored years 2016-2023, POST = 2024-2026 (walk-forward scoring starts when
  MIN_TRAIN=3000 accumulates, as in every prior harness; the era boundary is the one the
  three prior diagnostics identified, not a fitted breakpoint).
- Q1 (the model's edge): per-row g = logscore(model on exchange offset) - logscore(
  exchange de-vig baseline), from expanding-year walk-forward fits (frozen machinery:
  ridge logistic, L2 untouched, names from rows).
- Q2 (the anchor's informativeness): per-row d = logscore(exchange de-vig baseline) -
  logscore(Bet365 de-vig baseline). No model, no folds; same rows.
- For each quantity, the exact Oaxaca identity over strata s with era weights w and
  per-stratum means m:
      Delta = M_post - M_pre
            = SUM_s (w_post,s - w_pre,s) * m_pre,s      [COMPOSITION]
            + SUM_s w_post,s * (m_post,s - m_pre,s)     [WITHIN = sharpening]
  Day-clustered bootstrap (seed 20260725, 2000 draws, days resampled within era) gives
  95% CIs for Delta, COMPOSITION and WITHIN. Two questions, each read alone at
  alpha = 0.05 — this is a diagnostic decomposition, not a gate family.
- Declared reading: COMPOSITION-DOMINATED if the WITHIN CI spans zero while COMPOSITION
  clears and carries the majority of Delta; SHARPENING-DOMINATED in the mirror case;
  MIXED otherwise. The per-stratum PRE/POST table is printed as the persistence map
  either way. One run, recorded whatever it says; no stratum is promoted to a serving
  rule by this record.
"""
from __future__ import annotations

import collections
import datetime as dt
import math
import os
import random
from pathlib import Path
from typing import cast

from tennis_edge.corpus import load_corpus
from tennis_edge.exchange_prices import ExchangePrice, read_prices
from tennis_edge.experiments.exchange_anchor import (
    MIN_TRAIN,
    _log_score,
    _predict,
    _swap_offset,
    exchange_logit,
)
from tennis_edge.experiments.residual_edge import fit
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.residual_features import build_residual_features

PRICES = Path("/home/user/tennis_edge_data/betfair_historical/"
              "exchange_prices_600s_v4.jsonl")
ALPHA = 0.05
SEED = 20260725
DRAWS = 2000
PRE_YEARS = range(2016, 2024)
POST_YEARS = range(2024, 2027)
FAV_SPLIT = 0.65


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(z, 35.0), -35.0)))


def _stratum(row: Row, price: ExchangePrice, slam: bool) -> str:
    p_a = _sigmoid(exchange_logit(price))
    fav = max(p_a, 1.0 - p_a)
    return (f"{row.tour}|{'slam' if slam else 'other'}|"
            f"{'fav>.65' if fav > FAV_SPLIT else 'fav<=.65'}")


def _decompose(samples: list[tuple[dt.date, int, str, float]],
               ) -> tuple[float, float, float]:
    """(delta, composition, within) over (day, era, stratum, value) samples; era 1=POST."""
    strata = sorted({s for _, _, s, _ in samples})
    sums: dict[tuple[int, str], float] = collections.defaultdict(float)
    counts: dict[tuple[int, str], int] = collections.defaultdict(int)
    era_n = collections.Counter(e for _, e, _, _ in samples)
    for _, era, stratum, value in samples:
        sums[(era, stratum)] += value
        counts[(era, stratum)] += 1
    delta = composition = within = 0.0
    for stratum in strata:
        n_pre, n_post = counts[(0, stratum)], counts[(1, stratum)]
        m_pre = sums[(0, stratum)] / n_pre if n_pre else 0.0
        m_post = sums[(1, stratum)] / n_post if n_post else 0.0
        w_pre = n_pre / era_n[0] if era_n[0] else 0.0
        w_post = n_post / era_n[1] if era_n[1] else 0.0
        delta += w_post * m_post - w_pre * m_pre
        composition += (w_post - w_pre) * m_pre
        within += w_post * (m_post - m_pre)
    return delta, composition, within


def _boot_ci(samples: list[tuple[dt.date, int, str, float]],
             ) -> dict[str, tuple[float, float]]:
    by_day: dict[dt.date, list[tuple[dt.date, int, str, float]]] = \
        collections.defaultdict(list)
    for s in samples:
        by_day[s[0]].append(s)
    pre_days = sorted({d for d, r in by_day.items() if r[0][1] == 0})
    post_days = sorted({d for d, r in by_day.items() if r[0][1] == 1})
    rng = random.Random(SEED)
    stats: dict[str, list[float]] = {"delta": [], "composition": [], "within": []}
    for _ in range(DRAWS):
        draw: list[tuple[dt.date, int, str, float]] = []
        for pool in (pre_days, post_days):
            for _ in pool:
                draw.extend(by_day[pool[rng.randrange(len(pool))]])
        d, c, w = _decompose(draw)
        stats["delta"].append(d)
        stats["composition"].append(c)
        stats["within"].append(w)
    out = {}
    lo_i, hi_i = int(DRAWS * ALPHA / 2), int(DRAWS * (1 - ALPHA / 2)) - 1
    for key, values in stats.items():
        values.sort()
        out[key] = (values[lo_i], values[hi_i])
    return out


def _report(title: str, samples: list[tuple[dt.date, int, str, float]]) -> None:
    delta, composition, within = _decompose(samples)
    ci = _boot_ci(samples)

    def _line(name: str, value: float) -> None:
        lo, hi = ci[name]
        state = "clears" if lo > 0 or hi < 0 else "spans zero"
        print(f"  {name:<12} {value:+.6f}  CI95=[{lo:+.6f},{hi:+.6f}]  {state}")

    print(f"\n{title}")
    _line("delta", delta)
    _line("composition", composition)
    _line("within", within)

    comp_clears = ci["composition"][0] > 0 or ci["composition"][1] < 0
    within_clears = ci["within"][0] > 0 or ci["within"][1] < 0
    if comp_clears and not within_clears and abs(composition) > abs(delta) / 2:
        print("  reading: COMPOSITION-DOMINATED")
    elif within_clears and not comp_clears and abs(within) > abs(delta) / 2:
        print("  reading: SHARPENING-DOMINATED")
    else:
        print("  reading: MIXED / UNRESOLVED")

    strata = sorted({s for _, _, s, _ in samples})
    print(f"  {'stratum':<22} {'n_pre':>7} {'m_pre':>10} {'n_post':>7} {'m_post':>10}")
    for stratum in strata:
        pre = [v for _, e, s, v in samples if e == 0 and s == stratum]
        post = [v for _, e, s, v in samples if e == 1 and s == stratum]
        m_pre = math.fsum(pre) / len(pre) if pre else float("nan")
        m_post = math.fsum(post) / len(post) if post else float("nan")
        print(f"  {stratum:<22} {len(pre):>7,} {m_pre:>+10.6f} "
              f"{len(post):>7,} {m_post:>+10.6f}")


def main() -> None:
    os.environ.setdefault("TENNIS_EDGE_DATA", "/home/user/tennis_edge_data")
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    prices = {(p.date, p.tour, p.player_a, p.player_b): p for p in read_prices(PRICES)}
    matches, _stats = load_corpus()
    slam_by_key = {(m.match_date, m.tour, m.player_a, m.player_b):
                   m.tier == "Grand Slam" for m in matches}

    covered: list[tuple[Row, ExchangePrice, bool]] = []
    no_tier = 0
    for r in rows:
        key = (r.date, r.tour, r.player_a, r.player_b)
        if key not in prices:
            continue
        if key not in slam_by_key:
            no_tier += 1
            continue
        covered.append((r, prices[key], slam_by_key[key]))
    print(f"joined rows: {len(covered):,} (typed exclusion NO_TIER_JOIN: {no_tier:,})")

    by_year: dict[int, list[tuple[Row, ExchangePrice, bool]]] = \
        collections.defaultdict(list)
    for item in covered:
        by_year[item[0].date.year].append(item)

    q1: list[tuple[dt.date, int, str, float]] = []
    q2: list[tuple[dt.date, int, str, float]] = []
    train: list[tuple[Row, ExchangePrice]] = []
    for year in sorted(by_year):
        if len(train) >= MIN_TRAIN and (year in PRE_YEARS or year in POST_YEARS):
            era = 1 if year in POST_YEARS else 0
            beta = fit([_swap_offset(r, exchange_logit(p)) for r, p in train], names)
            for row, price, slam in by_year[year]:
                offset = exchange_logit(price)
                stratum = _stratum(row, price, slam)
                model = _predict(row, offset, beta)
                exch = _sigmoid(offset)
                b365 = _sigmoid(row.market_logit)
                q1.append((row.date, era, stratum,
                           _log_score(model, row.won) - _log_score(exch, row.won)))
                q2.append((row.date, era, stratum,
                           _log_score(exch, row.won) - _log_score(b365, row.won)))
            print(f"  {year}: trained {len(train):,}, scored {len(by_year[year]):,}",
                  flush=True)
        train.extend((r, p) for r, p, _s in by_year[year])

    _report("Q1  model-minus-exchange gain: POST minus PRE, decomposed", q1)
    _report("Q2  exchange-minus-Bet365 informativeness: POST minus PRE, decomposed", q2)
    print("\nDiagnostic only: no serving rule changes; any stratum restriction would")
    print("require its own registration on this record's persistence map.")


if __name__ == "__main__":
    main()
