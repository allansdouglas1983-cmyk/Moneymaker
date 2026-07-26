"""Closing line value against the exchange: does the market move toward our picks?

This is the highest-powered test available on a small sample, and it is the reason to run
it before any P&L test on 400 markets.

A bet's profit is dominated by whether one tennis match happened to go one way — variance
so large that several thousand bets are needed to see a few points of edge through it. But
whether the *price* moved toward the pick is nearly deterministic given the pick, so the
same information arrives with a fraction of the noise. A strategy with genuine edge beats
the closing line long before its P&L becomes readable, and one that cannot beat the closing
line is not going to be rescued by luck.

The measure here is honest about which of the CLV family it is (SPEC-095):

* **signal CLV** — the model's chosen side against the later price. Measured.
* **realised-fill CLV** — requires a real fill. NOT measured, and it must never be assigned
  to an unfilled order by pretending a price was taken.

Direction convention: positive means the price on the chosen side **shortened**, i.e. the
market moved toward us and the early price was better than the late one. That is the sign
of value; it does not mean money was made.
"""
import math
from dataclasses import dataclass

from tennis_edge.betfair import MarketHistory, read_markets
from tennis_edge.combine import logit
from tennis_edge.corpus import default_vintage_root, load_corpus
from tennis_edge.exchange_link import link_markets
from tennis_edge.refresh import latest_vintage

EARLY, LATE = 21_600, 600            # T-6h -> T-10m
CORPUS = ("/tmp/claude-0/-home-user-Moneymaker/"
          "b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted")


@dataclass(frozen=True)
class Pick:
    early: float
    late: float
    won: int
    side_is_a: bool


def _midpoint(history: MarketHistory, a: int, b: int, horizon: int) -> float | None:
    back_a = history.best_back_at(a, seconds_before_off=horizon)
    back_b = history.best_back_at(b, seconds_before_off=horizon)
    lay_a = history.best_lay_at(a, seconds_before_off=horizon)
    lay_b = history.best_lay_at(b, seconds_before_off=horizon)
    if back_a is None or back_b is None or lay_a is None or lay_b is None:
        return None
    imp_a = (1.0 / float(back_a.price) + 1.0 / float(lay_a.price)) / 2.0
    imp_b = (1.0 / float(back_b.price) + 1.0 / float(lay_b.price)) / 2.0
    total = imp_a + imp_b
    return imp_a / total if total > 0 else None


def _report(name: str, picks: list[Pick]) -> None:
    if len(picks) < 30:
        print(f"{name:<28}{len(picks):>7}   (too few to score)")
        return
    # Positive = the chosen side shortened, i.e. the market moved toward the pick.
    moves = [
        (logit(p.late) - logit(p.early)) if p.side_is_a
        else (logit(1 - p.late) - logit(1 - p.early))
        for p in picks
    ]
    n = len(moves)
    mean = math.fsum(moves) / n
    var = math.fsum((m - mean) ** 2 for m in moves) / (n - 1)
    se = math.sqrt(var / n)
    hit = sum(1 for m in moves if m > 0) / n
    strike = math.fsum(
        float(p.won if p.side_is_a else 1 - p.won) for p in picks) / n
    print(f"{name:<28}{n:>7,}{mean:>+11.4f}{mean / se:>8.2f}{hit:>10.1%}{strike:>10.1%}")


def main() -> None:
    markets = read_markets(CORPUS)
    vintage = latest_vintage(default_vintage_root())
    assert vintage is not None
    matches, _stats = load_corpus(vintage.root)
    linked = link_markets(markets, matches).linked

    rows: list[tuple[float, float, int]] = []
    for row in linked:
        a = row.selection_for_player_a
        b = (row.quote.selection_b if a == row.quote.selection_a
             else row.quote.selection_a)
        early = _midpoint(row.market, a, b, EARLY)
        late = _midpoint(row.market, a, b, LATE)
        if early is None or late is None:
            continue
        rows.append((early, late, 1 if row.match.winner_is_a else 0))

    print(f"markets with both horizons: {len(rows):,}\n")
    print(f"{'strategy':<28}{'n':>7}{'CLV':>11}{'t':>8}{'moved to':>10}{'won':>10}")

    # Control 1: always back A. Any systematic drift in the data shows up here, and every
    # other line must be read as a difference from it rather than in isolation.
    _report("always back A (control)",
            [Pick(e, late, y, True) for e, late, y in rows])

    # Control 2: always back the favourite. The classic longshot-bias direction.
    _report("always back favourite",
            [Pick(e, late, y, e >= 0.5) for e, late, y in rows])

    # Control 3: always back the outsider.
    _report("always back outsider",
            [Pick(e, late, y, e < 0.5) for e, late, y in rows])

    # The real question: do the extremes drift differently from the middle? If short prices
    # systematically shorten further, that is a tradeable direction; if not, there is
    # nothing here regardless of what any tennis model says.
    for lo, hi, label in ((0.0, 0.2, "back outsider p<0.2"),
                          (0.2, 0.4, "back side p 0.2-0.4"),
                          (0.6, 0.8, "back side p 0.6-0.8"),
                          (0.8, 1.0, "back favourite p>0.8")):
        picks = [Pick(e, late, y, True) for e, late, y in rows if lo <= e < hi]
        _report(label, picks)

    print("\nPositive CLV = the chosen side shortened, i.e. the market moved toward the "
          "pick.\nThat is the sign of value, not evidence that money was made. Realised-"
          "fill CLV\nis NOT reported: it requires a real fill and must never be assigned "
          "to an\nunfilled order by pretending a price was taken (SPEC-095).")


if __name__ == "__main__":
    main()
