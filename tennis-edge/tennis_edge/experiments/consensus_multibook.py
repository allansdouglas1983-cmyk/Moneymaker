"""Cross-book consensus deviation, tested against ten real books (task #72 follow-on).

Findings: docs/research/findings/TE-0001-challenger-itf-tier-efficiency.md

Why this run exists: consensus deviation — back a selection when one book's price is out
of line with the consensus of the others — is the only tennis method in the literature with
real-money verification behind it. Our earlier test of it used Tennis-Data, which carries
Pinnacle, B365 and two *aggregates* (Max, Avg). Betting into an aggregate is meaningless,
so that test was really two books wide and it measured CLV -1.59% with a deflated Sharpe of
0.048.

This corpus carries ten genuine books (Pinnacle, Bovada, 5Dimes, BetOnline, Sportsbetting,
Intertops, Bookmaker, YouWager, Heritage, JustBet) on 15,015 main-tour matches with five or
more of them quoting. That is the first data available here that can test the mechanism
properly.

Two constraints on what any result here can mean, stated before the numbers rather than
after:

* The window is 2008-2018. Several of these books are US-facing and some no longer trade;
  a UK individual could not open accounts at all of them today. A positive result would
  therefore be evidence about the *mechanism*, not a tradeable strategy.
* The corpus has UNVERIFIED RIGHTS and is research-quarantined (SPEC-100, SPEC-044,
  SPEC-101). It must never acquire an import path into l5_decision, l5b_risk or l6_broker,
  and it cannot support any commercial output.

The target book is always excluded from the consensus it is compared against — measuring a
book against a consensus that contains it is the circularity that made an earlier CLV
result meaningless.
"""
import collections
import csv
import io
import math
import zipfile

ZIP = "/home/user/tennis_edge_data/kaggle_itf/dataset.zip"

#: Aggregators, not books. You cannot place a bet at an aggregate.
AGGREGATORS = frozenset({"OddsPortal"})
MIN_CONSENSUS = 3
COMMISSION = 0.0          # bookmaker prices, not an exchange: no commission is charged


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


def load() -> tuple[dict[tuple[str, ...], bool],
                    dict[tuple[str, ...], dict[str, tuple[float, float]]]]:
    z = zipfile.ZipFile(ZIP)
    outcome: dict[tuple[str, ...], bool] = {}
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
            key = (r["start_date"], r["tournament"], lo, hi)
            if key in outcome:
                continue
            outcome[key] = (r["player_victory"] == "t") == (a == lo)

    quotes: dict[tuple[str, ...], dict[str, tuple[float, float]]] = {}
    with z.open("betting_moneyline.csv") as fh:
        for r in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace")):
            if r["book_name"] in AGGREGATORS:
                continue
            try:
                o1, o2 = float(r["odds1"]), float(r["odds2"])
            except ValueError:
                continue
            if not (0 < o1 < 1 and 0 < o2 < 1):
                continue
            t1, t2 = r["team1"], r["team2"]
            lo, hi = sorted((t1, t2))
            key = (r["start_date"], r["tournament"], lo, hi)
            quotes.setdefault(key, {})[r["book_name"]] = (
                (o1, o2) if t1 == lo else (o2, o1))
    return outcome, quotes


def main() -> None:
    outcome, quotes = load()
    usable = {k: v for k, v in quotes.items()
              if k in outcome and len(v) >= MIN_CONSENSUS + 1}
    print(f"matches with outcome and >={MIN_CONSENSUS + 1} real books: {len(usable):,}")
    by_tier = collections.Counter(tier(k[1]) for k in usable)
    print("  by tier: " + ", ".join(f"{t}={c:,}" for t, c in by_tier.most_common()))

    # Deviation of each book from the consensus of the OTHERS, in logit space.
    results: dict[float, list[tuple[float, bool]]] = collections.defaultdict(list)
    per_book: dict[str, list[tuple[float, bool]]] = collections.defaultdict(list)
    for key, books in usable.items():
        won_lo = outcome[key]
        fair = {b: devig(*p) for b, p in books.items()}
        for target, (imp_lo, imp_hi) in books.items():
            others = [v for b, v in fair.items() if b != target]
            if len(others) < MIN_CONSENSUS:
                continue
            consensus = sum(logit(p) for p in others) / len(others)
            for side, imp, won in ((0, imp_lo, won_lo), (1, imp_hi, not won_lo)):
                p_cons = 1 / (1 + math.exp(-(consensus if side == 0 else -consensus)))
                decimal = 1.0 / imp
                edge = p_cons * decimal * (1 - COMMISSION) - 1.0
                for threshold in (0.0, 0.02, 0.05, 0.10):
                    if edge > threshold:
                        payoff = ((decimal - 1.0) * (1 - COMMISSION)) if won else -1.0
                        results[threshold].append((payoff, won))
                        if threshold == 0.05:
                            per_book[target].append((payoff, won))

    print(f"\n{'edge >':>8}{'bets':>10}{'strike':>9}{'ROI':>10}{'SE':>8}{'t':>7}")
    for threshold in (0.0, 0.02, 0.05, 0.10):
        rows = results[threshold]
        if not rows:
            print(f"{threshold:>8.0%}{0:>10}   (none)")
            continue
        n = len(rows)
        payoffs = [p for p, _w in rows]
        mean = math.fsum(payoffs) / n
        var = math.fsum((p - mean) ** 2 for p in payoffs) / max(n - 1, 1)
        se = math.sqrt(var / n)
        strike = sum(1 for _p, w in rows if w) / n
        print(f"{threshold:>8.0%}{n:>10,}{strike:>9.3f}{mean:>9.2%}{se:>8.2%}"
              f"{(mean / se if se else float('nan')):>7.2f}")

    print(f"\nper-book at the 5% threshold ({'bets':>6} {'ROI':>8}):")
    for book, rows in sorted(per_book.items(), key=lambda kv: -len(kv[1])):
        n = len(rows)
        if n < 200:
            continue
        mean = math.fsum(p for p, _w in rows) / n
        print(f"  {book:<20}{n:>6,}{mean:>9.2%}")


if __name__ == "__main__":
    main()
