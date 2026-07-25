"""The market benchmark, locked.

Every model this project builds is measured against the de-vigged sharp closing line. If
that number moves silently — a loader change, a de-vig change, a corpus revision — then every
comparison made before and after is meaningless, and a model can appear to "beat the market"
purely because the market got redefined. So the benchmark is pinned to five decimals here.

A change to these numbers is not a test failure to paper over. It means either the corpus or
the pricing changed, and the new figure has to be understood and re-pinned deliberately, in
its own commit, with the reason recorded.

Skipped when the corpus is not present locally — raw provider data is never committed.
"""
from __future__ import annotations

import datetime as dt

import pytest

from tennis_edge.backtest import evaluate_market
from tennis_edge.corpus import Match, default_vintage_root, load_corpus
from tennis_edge.devig import DevigMethod

_START = dt.date(2010, 1, 1)
_END = dt.date(2026, 12, 31)

#: Pinned on Tennis-Data vintage-2026-07-18, Pinnacle closing prices, 2010-01-01..2026-12-31.
_EXPECTED: dict[DevigMethod, float] = {
    DevigMethod.PROPORTIONAL: 0.57587,
    DevigMethod.POWER: 0.57539,
    DevigMethod.SHIN: 0.57549,
}
_EXPECTED_N = 75_419
_BENCHMARK_CASES: list[tuple[DevigMethod, float]] = sorted(
    _EXPECTED.items(), key=lambda item: item[0].value
)


@pytest.fixture(scope="module")
def corpus() -> list[Match]:
    root = default_vintage_root() / "tennis_data"
    if not root.exists():
        pytest.skip(f"no local Tennis-Data corpus at {root}")
    matches, _ = load_corpus()
    return [m for m in matches if _START <= m.match_date <= _END]


@pytest.mark.parametrize("method,expected", _BENCHMARK_CASES)
def test_market_benchmark_log_loss_is_unchanged(
    corpus: list[Match], method: DevigMethod, expected: float
) -> None:
    card = evaluate_market(corpus, book="pinnacle", method=method)
    assert card.n == _EXPECTED_N, "the benchmark sample changed; re-pin deliberately"
    assert card.log_loss == pytest.approx(expected, abs=5e-6), (
        f"{method.value} benchmark moved from {expected} to {card.log_loss:.5f}"
    )


def test_power_devig_gives_the_best_calibrated_market(corpus: list[Match]) -> None:
    """The empirical reason POWER is the default: it is the margin model under which the
    closing line comes out almost perfectly calibrated. If another method ever calibrates
    better on this corpus, the default should change — and this test will say so."""
    cards = {m: evaluate_market(corpus, book="pinnacle", method=m) for m in _EXPECTED}
    power = cards[DevigMethod.POWER]
    assert abs(power.calibration.slope - 1.0) < 0.02
    for method, card in cards.items():
        if method is DevigMethod.POWER:
            continue
        assert abs(power.calibration.slope - 1.0) < abs(card.calibration.slope - 1.0)
        assert power.decomposition.reliability <= card.decomposition.reliability


def test_the_market_is_hard_to_beat_and_we_say_so_in_a_test(corpus: list[Match]) -> None:
    """A guard against optimism: the benchmark must stay well below the log loss of any
    trivial forecast. If a 'model' ever scores near 0.69 it is predicting nothing."""
    card = evaluate_market(corpus, book="pinnacle", method=DevigMethod.POWER)
    assert card.log_loss < 0.60
    assert card.accuracy > 0.65
