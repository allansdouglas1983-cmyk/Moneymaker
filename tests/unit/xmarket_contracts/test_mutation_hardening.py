"""STAGE3-0004 §14 — mutation-hardening edge tests for the promoted plumbing.

Targets behavioural survivors from the advice-critical mutation pass: the bool-vs-int/float
guards (a ``bool`` is a subclass of ``int`` and must be refused), exact comparison
boundaries, and loop completeness. PEP-563 type-annotation operator mutants (``X | Y`` in
annotations, never evaluated under ``from __future__ import annotations``) are equivalent and
are classified in ``specs/mutation-survivors-xmarket-contracts.yaml``, not killed here.
"""
from __future__ import annotations

import pytest

from xmarket_contracts import parsers as P
from xmarket_contracts import synchronizer as SY


# ---------------------------------------------------------------- parsers bool guards
def test_bool_runner_id_is_refused() -> None:
    # True is an int subclass; a bool id must be refused (kills the `isinstance(rid, bool)` guard)
    with pytest.raises(P.MarketParseError):
        P.parse_match_odds([{"id": True, "name": "A"}, {"id": 2, "name": "B"}])


def test_bool_hc_is_refused() -> None:
    with pytest.raises(P.MarketParseError):
        P.parse_total_games([{"id": 1, "name": "Over", "hc": True},
                             {"id": 2, "name": "Under", "hc": True}])


def test_non_dict_runner_refused() -> None:
    with pytest.raises(P.MarketParseError):
        P.parse_match_odds([{"id": 1, "name": "A"}, ("not", "dict")])


def test_total_games_every_line_paired_completeness() -> None:
    # a stray Over with no matching Under is caught by the symmetric-difference check
    runners = [{"id": 1, "name": "Over", "hc": 12.0}, {"id": 2, "name": "Under", "hc": 12.0},
               {"id": 1, "name": "Over", "hc": 12.5}]
    with pytest.raises(P.MarketParseError):
        P.parse_total_games(runners)


def test_game_handicap_all_magnitudes_present() -> None:
    # exactly two lines per magnitude across the whole ladder (loop must visit every giver)
    out = P.parse_game_handicap([
        {"id": 9, "name": "A", "hc": -4.5}, {"id": 8, "name": "B", "hc": 4.5},
        {"id": 9, "name": "A", "hc": 4.5}, {"id": 8, "name": "B", "hc": -4.5},
        {"id": 9, "name": "A", "hc": -5.5}, {"id": 8, "name": "B", "hc": 5.5},
        {"id": 9, "name": "A", "hc": 5.5}, {"id": 8, "name": "B", "hc": -5.5},
    ])
    assert sorted((ln.line, ln.giver_runner_id) for ln in out) == [
        (4.5, 8), (4.5, 9), (5.5, 8), (5.5, 9)]


def test_market_role_exact_known_map_no_silent_default() -> None:
    # every known key maps to a NON-review role; only unknown yields review (kills Eq/NotEq
    # flips that would collapse the map or default known types to review)
    for known in ("MATCH_ODDS", "COMBINED_TOTAL", "HANDICAP", "SET_WINNER", "SET_BETTING",
                  "SET_CORRECT_SCORE", "NUMBER_OF_SETS", "PLAYER_A_WIN_A_SET",
                  "PLAYER_B_WIN_A_SET", "TOURNAMENT_WINNER"):
        assert P.market_role(known) != P.UNKNOWN_REQUIRES_REVIEW


# ------------------------------------------------------------- synchronizer bool/edge
def test_bool_tv_is_ignored_not_treated_as_volume() -> None:
    # tv=True must NOT be recorded as matched volume 1.0 (bool is not numeric volume here)
    stream = [{"pt": 100, "mc": [{"id": "m", "marketDefinition": {"status": "OPEN",
               "inPlay": False, "marketType": "COMBINED_TOTAL", "eventId": "E1"}}]},
              {"pt": 200, "mc": [{"id": "m", "rc": [{"id": 1, "hc": 20.5,
               "batb": [[0, 1.9, 5.0]], "batl": [[0, 2.0, 5.0]], "tv": True}]}]}]
    snap = SY.reconstruct_as_of(stream, "m", cutoff_ms=1000)
    assert snap.quotes[0].matched_volume == 0.0


def test_best_level_picks_lowest_index_and_ignores_zero_size() -> None:
    # two levels: index 1 is best-priced but a zero-size level must not be chosen; the
    # min-by-level-index rule must pick level 0.
    stream = [{"pt": 100, "mc": [{"id": "m", "marketDefinition": {"status": "OPEN",
               "inPlay": False, "marketType": "COMBINED_TOTAL", "eventId": "E1"}}]},
              {"pt": 200, "mc": [{"id": "m", "rc": [{"id": 1, "hc": 20.5,
               "batb": [[0, 1.90, 50.0], [1, 1.80, 10.0]],
               "batl": [[0, 1.95, 40.0], [1, 2.10, 0.0]]}]}]}]
    snap = SY.reconstruct_as_of(stream, "m", cutoff_ms=1000)
    q = snap.quotes[0]
    assert q.best_back_price == 1.90 and q.back_levels == 2  # level 0 chosen; both priced
    assert q.best_lay_price == 1.95 and q.lay_levels == 1    # zero-size level dropped


def test_reconstruct_ignores_non_int_pt_and_selection() -> None:
    stream = [{"pt": "bad", "mc": [{"id": "m", "rc": [{"id": 1, "hc": 20.5, "batb": [[0, 1.9, 5.0]]}]}]},
              {"pt": 100, "mc": [{"id": "m", "marketDefinition": {"status": "OPEN",
               "inPlay": False, "marketType": "COMBINED_TOTAL", "eventId": "E1"}}]},
              {"pt": 200, "mc": [{"id": "m", "rc": [{"id": "notint", "hc": 20.5, "batb": [[0, 1.9, 5.0]]}]}]}]
    snap = SY.reconstruct_as_of(stream, "m", cutoff_ms=1000)
    assert snap.quotes == ()  # neither the string-pt nor the non-int selection produced a quote
