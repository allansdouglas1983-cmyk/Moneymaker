"""Does a rating model beat the market at Challenger/ITF level? (task #72)

Findings: docs/research/findings/TE-0001-challenger-itf-tier-efficiency.md

Answer: the thesis cannot be tested on free data. ITF quotes are 100% OddsPortal
aggregate and Challenger 94.2%, so the lower tiers have essentially no real-book price to
transact at — 152 Challenger matches and zero ITF matches carry two or more real books.
Where real prices do exist (main tour) this method loses 5.51% over 19,221 bets.

The corpus is research-quarantined (SPEC-100) with UNVERIFIED RIGHTS (SPEC-044/101): it
must never acquire an import path into l5_decision, l5b_risk or l6_broker, and it cannot
support any commercial output. This module is an experiment, not a package import.

History — three fixes and the economic test.

v1 reported b1 = 0.53 (t = 19.4) at ITF with Elo beating the market outright, which
contradicts the -0.027 measured for the same rating family on Tennis-Data main tour. That
is a suspected-bug signal, not a finding. This version:

1. Fixes the join key. v1 keyed on (tournament, player, player) with NO year, and
   tournament names repeat annually ("kosice_challenger"), so results and odds from
   different years could collide and matches were silently dropped.
2. Adds the economic test. b1 measures information, not money: a bet must clear the
   quoted price and the 7-8% lower-tier overround, so this simulates flat stakes at the
   actual quoted odds rather than the de-vigged probability.
3. Reports the odds-timing evidence, because an aggregate that is not a closing price is
   not something anyone could have transacted at.
"""
import collections
import csv
import io
import math
import zipfile
from typing import Iterable

ZIP = "/home/user/tennis_edge_data/kaggle_itf/dataset.zip"
MIN_PRIOR = 10


def tier(name: str) -> str:
    if "itf_juniors" in name:
        return "itf_juniors"
    if "_itf" in name or name.endswith("itf"):
        return "itf"
    if "challenger" in name:
        return "challenger"
    return "main"


def devig(o1: float, o2: float) -> float:
    lo, hi = 0.2, 5.0
    for _ in range(50):
        k = (lo + hi) / 2
        if o1 ** k + o2 ** k > 1:
            lo = k
        else:
            hi = k
    return float(min(max(o1 ** ((lo + hi) / 2), 1e-6), 1 - 1e-6))


def logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


Match = tuple[str, int, str, str, bool, str]
Odds = dict[tuple[str, ...], dict[str, tuple[float, float]]]


def load() -> tuple[dict[tuple[str, ...], Match], Odds, int, collections.Counter[bool]]:
    z = zipfile.ZipFile(ZIP)
    matches: dict[tuple[str, ...], Match] = {}
    dupes = 0
    with z.open("all_matches.csv") as fh:
        for r in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace")):
            if r["doubles"] == "t" or r["retirement"] == "t":
                continue
            if r["player_victory"] not in ("t", "f"):
                continue
            a, b = r["player_id"], r["opponent_id"]
            if not a or not b or a == b:
                continue
            lo, hi = sorted((a, b))
            # FIX: year + round in the key. Tournament names repeat annually.
            key = (r["start_date"], r["tournament"], r["round"], lo, hi)
            if key in matches:
                dupes += 1
                continue
            won_lo = (r["player_victory"] == "t") == (a == lo)
            matches[key] = (r["start_date"], int(r["round_num"] or 0), lo, hi,
                            won_lo, tier(r["tournament"]))

    odds: Odds = {}
    timing: collections.Counter[bool] = collections.Counter()
    with z.open("betting_moneyline.csv") as fh:
        for r in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace")):
            try:
                o1, o2 = float(r["odds1"]), float(r["odds2"])
            except ValueError:
                continue
            if not (0 < o1 < 1 and 0 < o2 < 1):
                continue
            t1, t2 = r["team1"], r["team2"]
            lo, hi = sorted((t1, t2))
            okey = (r["start_date"], r["tournament"], lo, hi)
            pair = (o1, o2) if t1 == lo else (o2, o1)
            odds.setdefault(okey, {})[r["book_name"]] = pair
            if r["betting_date"] and r["start_date"]:
                timing[r["betting_date"] >= r["start_date"]] += 1
    return matches, odds, dupes, timing


def newton_b1(xs: list[float], offsets: list[float],
              ys: list[int]) -> tuple[float, float]:
    b, h = 0.0, 0.0
    for _ in range(60):
        g = h = 0.0
        for x, off, y in zip(xs, offsets, ys):
            p = 1 / (1 + math.exp(-(off + b * x)))
            g += x * (y - p)
            h += x * x * p * (1 - p)
        if h <= 1e-12:
            break
        step = g / h
        b += step
        if abs(step) < 1e-10:
            break
    return b, (h ** -0.5 if h > 0 else float("nan"))


def main() -> None:
    matches, odds, dupes, timing = load()
    print(f"deduped singles matches: {len(matches):,}  (collisions dropped: {dupes:,})")
    print(f"odds keys: {len(odds):,}")
    print(f"betting_date on/after tournament start: {timing[True]:,}; before: {timing[False]:,}")
    print("  (an aggregate stamped after the tournament starts is not a pre-match "
          "closing price for every match in it)\n")

    ordered = sorted(matches.items(), key=lambda kv: (kv[1][0], kv[1][1]))
    rating: dict[str, float] = collections.defaultdict(lambda: 1500.0)
    played: collections.Counter[str] = collections.Counter()
    records: dict[str, list[tuple[float, float, int, float, float]]] = (
        collections.defaultdict(list))

    def apply(block: Iterable[tuple[tuple[str, ...], Match]]) -> None:
        for _k, (_d, _r, lo, hi, won_lo, _t) in block:
            e = 1 / (1 + 10 ** ((rating[hi] - rating[lo]) / 400))
            for player, exp, won in ((lo, e, won_lo), (hi, 1 - e, not won_lo)):
                k = 250 / ((played[player] + 5) ** 0.4)
                rating[player] += k * ((1 if won else 0) - exp)
                played[player] += 1

    block: list[tuple[tuple[str, ...], Match]] = []
    block_key: tuple[str, int] | None = None
    matched = 0
    for key, m in ordered:
        day, rnd, lo, hi, won_lo, tr = m
        if block_key is not None and (day, rnd) != block_key:
            apply(block)
            block = []
        block_key = (day, rnd)
        block.append((key, m))

        okey = (key[0], key[1], lo, hi)
        if okey in odds and played[lo] >= MIN_PRIOR and played[hi] >= MIN_PRIOR:
            matched += 1
            books = odds[okey]
            book = ("Pinnacle Sports" if "Pinnacle Sports" in books
                    else "OddsPortal" if "OddsPortal" in books else sorted(books)[0])
            o1, o2 = books[book]
            elo = 1 / (1 + 10 ** ((rating[hi] - rating[lo]) / 400))
            records[tr].append((devig(o1, o2), elo, 1 if won_lo else 0, o1, o2))
    apply(block)
    print(f"joined and scoreable: {matched:,}\n")

    print(f"{'tier':<12}{'scored':>8}{'over':>7}{'market':>9}{'elo':>9}{'b1':>8}{'t':>7}"
          f"{'bets':>8}{'ROI':>9}")
    for tr in ("main", "challenger", "itf"):
        data = records[tr]
        if len(data) < 200:
            print(f"{tr:<12}{len(data):>8}  (too few to score)")
            continue
        mll = ell = ov = 0.0
        xs: list[float] = []
        offs: list[float] = []
        ys: list[int] = []
        bets = 0
        profit = 0.0
        for market, elo, y, o1, o2 in data:
            ov += o1 + o2
            mll -= math.log(market if y else 1 - market)
            ell -= math.log(elo if y else 1 - elo)
            xs.append(logit(elo) - logit(market))
            offs.append(logit(market))
            ys.append(y)
            # Economic test at the ACTUAL quoted price, flat stakes, 5% edge required.
            for prob, imp, won in ((elo, o1, y == 1), (1 - elo, o2, y == 0)):
                decimal = 1.0 / imp
                if prob * decimal - 1.0 > 0.05:
                    bets += 1
                    profit += (decimal - 1.0) if won else -1.0
        b1, se = newton_b1(xs, offs, ys)
        n = len(data)
        roi = f"{100*profit/bets:+.2f}%" if bets else "n/a"
        print(f"{tr:<12}{n:>8,}{ov/n:>7.3f}{mll/n:>9.5f}{ell/n:>9.5f}"
              f"{b1:>8.4f}{b1/se:>7.2f}{bets:>8,}{roi:>9}")


if __name__ == "__main__":
    main()
