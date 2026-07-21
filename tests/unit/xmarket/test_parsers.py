"""STAGE3-0002 §4/§17 — deterministic market-type selection parsers (red tests first).

These pin the CONTRACT of ``research.xmarket.parsers`` BEFORE the implementation is
(re)written, grounded in the real June ADVANCED corpus definition structure observed in
§3 (not the external research report):

* COMBINED_TOTAL ("Total Games") is an ``ASIAN_HANDICAP_DOUBLE_LINE`` market with ONE
  ``Over`` selection id and ONE ``Under`` selection id reused across every line; the line
  (games total) is carried by ``hc`` (12.0..65.0 observed, 0.5 step).
* HANDICAP ("Handicap") is an ``ASIAN_HANDICAP_DOUBLE_LINE`` GAME handicap: each of the
  two players appears at BOTH ``+m`` and ``-m`` for every magnitude m (observed max|hc|
  only ever 11.5 or 15.5; NEVER <= 3.0). Each magnitude therefore packs TWO priceable
  two-sided lines (either player can be the giver). A parser that collapses a magnitude to
  a single line silently drops half the market — forbidden (§3/§4 "never misclassify /
  never silently rename").
* A SET handicap (magnitudes <= 2.5 in tennis) MUST NOT be accepted as a GAME handicap.

Audit-only: parsers read definition STRUCTURE (marketType / runner id/name/hc). No price,
no outcome, no settlement is read or asserted here.
"""
from __future__ import annotations

from typing import Any

import pytest

from research.xmarket import parsers as P


# --------------------------------------------------------------------------- helpers
def _runner(rid: int, name: str, hc: float | None) -> dict[str, Any]:
    d: dict[str, Any] = {"id": rid, "name": name}
    if hc is not None:
        d["hc"] = hc
    return d


def _total_games_runners(lines: list[float], over_id: int = 7698572,
                         under_id: int = 7698577) -> list[dict[str, Any]]:
    """Real COMBINED_TOTAL shape: one Over id, one Under id, reused across every line."""
    out = []
    for ln in lines:
        out.append(_runner(over_id, "Over", ln))
        out.append(_runner(under_id, "Under", ln))
    return out


def _double_line_handicap_runners(mags: list[float], a_id: int = 9628236, b_id: int = 9607743,
                                  a_name: str = "A Tomljanovic",
                                  b_name: str = "Swan") -> list[dict[str, Any]]:
    """Real HANDICAP shape: for each magnitude m, all four of A@-m,B@+m,A@+m,B@-m."""
    out = []
    for m in mags:
        out.append(_runner(a_id, a_name, -m))
        out.append(_runner(b_id, b_name, +m))
        out.append(_runner(a_id, a_name, +m))
        out.append(_runner(b_id, b_name, -m))
    return out


_GAME_LADDER = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]
_SET_LADDER = [0.5, 1.5, 2.5]  # unambiguously a SET handicap: max 2.5 <= 3.0


# --------------------------------------------------------------------------- version
def test_parser_version_is_pinned() -> None:
    assert P.PARSER_VERSION == "xmarket-parsers-v1"


# ----------------------------------------------------------------------- market_role
def test_market_role_maps_every_observed_type_to_its_role() -> None:
    assert P.market_role("MATCH_ODDS") == P.PRIMARY_MATCH_ODDS
    assert P.market_role("COMBINED_TOTAL") == P.PRIMARY_IDENTIFYING_TOTAL_GAMES
    assert P.market_role("HANDICAP") == P.PRIMARY_IDENTIFYING_GAME_HANDICAP
    assert P.market_role("SET_WINNER") == P.AUXILIARY_SET_STRUCTURE
    assert P.market_role("NUMBER_OF_SETS") == P.AUXILIARY_SET_STRUCTURE
    assert P.market_role("PLAYER_A_WIN_A_SET") == P.AUXILIARY_SET_STRUCTURE
    assert P.market_role("PLAYER_B_WIN_A_SET") == P.AUXILIARY_SET_STRUCTURE
    assert P.market_role("SET_BETTING") == P.AUXILIARY_OTHER
    assert P.market_role("SET_CORRECT_SCORE") == P.AUXILIARY_OTHER
    assert P.market_role("TOURNAMENT_WINNER") == P.UNSUPPORTED


def test_market_role_unknown_type_fails_closed_and_never_renames() -> None:
    assert P.market_role("SOME_NEW_BETFAIR_TYPE") == P.UNKNOWN_REQUIRES_REVIEW
    assert P.market_role("match_odds") == P.UNKNOWN_REQUIRES_REVIEW  # case-sensitive: raw is raw


@pytest.mark.parametrize("bad", ["", 123, None])
def test_market_role_refuses_empty_or_non_string(bad: str) -> None:
    with pytest.raises(P.MarketParseError):
        P.market_role(bad)


# ------------------------------------------------------------------------ match_odds
def test_match_odds_returns_two_ids_sorted() -> None:
    runners = [_runner(22, "Player Z", None), _runner(11, "Player A", None)]
    assert P.parse_match_odds(runners) == (11, 22)


@pytest.mark.parametrize("n", [1, 3, 0])
def test_match_odds_wrong_runner_count_refuses(n: int) -> None:
    runners = [_runner(i + 1, f"P{i}", None) for i in range(n)]
    with pytest.raises(P.MarketParseError):
        P.parse_match_odds(runners)


def test_match_odds_shared_id_refuses() -> None:
    runners = [_runner(5, "A", None), _runner(5, "B", None)]
    with pytest.raises(P.MarketParseError):
        P.parse_match_odds(runners)


def test_set_betting_is_not_a_two_player_market() -> None:
    assert P.market_role("SET_BETTING") != P.PRIMARY_MATCH_ODDS
    set_betting_runners = [
        _runner(1, "A 2-0", None), _runner(2, "A 2-1", None),
        _runner(3, "B 2-0", None), _runner(4, "B 2-1", None),
    ]
    with pytest.raises(P.MarketParseError):
        P.parse_match_odds(set_betting_runners)


# ----------------------------------------------------------------------- total_games
def test_total_games_distinguishes_over_under_and_line() -> None:
    runners = _total_games_runners([12.0, 12.5, 13.0])
    lines = P.parse_total_games(runners)
    assert [ln.line for ln in lines] == [12.0, 12.5, 13.0]  # sorted by line
    for ln in lines:
        assert ln.over_runner_id == 7698572
        assert ln.under_runner_id == 7698577
        assert ln.over_runner_id != ln.under_runner_id


def test_total_games_missing_under_side_refuses() -> None:
    runners = [_runner(7698572, "Over", 12.0), _runner(7698572, "Over", 12.5),
               _runner(7698577, "Under", 12.0)]  # 12.5 Under missing
    with pytest.raises(P.MarketParseError):
        P.parse_total_games(runners)


def test_total_games_duplicate_line_refuses() -> None:
    runners = _total_games_runners([12.0]) + [_runner(7698572, "Over", 12.0)]
    with pytest.raises(P.MarketParseError):
        P.parse_total_games(runners)


def test_total_games_non_over_under_name_refuses() -> None:
    runners = [_runner(1, "Yes", 12.0), _runner(2, "No", 12.0)]
    with pytest.raises(P.MarketParseError):
        P.parse_total_games(runners)


def test_total_games_absent_hc_refuses() -> None:
    runners = [_runner(7698572, "Over", None), _runner(7698577, "Under", None)]
    with pytest.raises(P.MarketParseError):
        P.parse_total_games(runners)


@pytest.mark.parametrize("bad", [[], "notalist", None])
def test_total_games_empty_or_non_list_refuses(bad: object) -> None:
    with pytest.raises(P.MarketParseError):
        P.parse_total_games(bad)


def test_total_games_row_order_does_not_change_output() -> None:
    lines = [12.0, 12.5, 13.0, 13.5]
    a = P.parse_total_games(_total_games_runners(lines))
    b = P.parse_total_games(_total_games_runners(list(reversed(lines))))
    assert a == b


# --------------------------------------------------------------------- game_handicap
def test_game_handicap_double_line_produces_two_lines_per_magnitude() -> None:
    runners = _double_line_handicap_runners(_GAME_LADDER)
    lines = P.parse_game_handicap(runners)
    assert len(lines) == 2 * len(_GAME_LADDER)
    for ln in lines:
        assert ln.line > 0.0
        assert ln.giver_runner_id != ln.receiver_runner_id
    givers_at_4_5 = {ln.giver_runner_id for ln in lines if ln.line == 4.5}
    assert givers_at_4_5 == {9628236, 9607743}


def test_game_handicap_giver_is_the_negative_hc_player() -> None:
    runners = _double_line_handicap_runners([4.5])  # single magnitude, but 4.5 > 3.0
    lines = P.parse_game_handicap(runners)
    assert len(lines) == 2
    by_giver = {ln.giver_runner_id: ln for ln in lines}
    assert by_giver[9628236].receiver_runner_id == 9607743
    assert by_giver[9607743].receiver_runner_id == 9628236
    assert all(ln.line == 4.5 for ln in lines)


def test_set_handicap_is_never_accepted_as_game_handicap() -> None:
    runners = _double_line_handicap_runners(_SET_LADDER)  # max|hc| 2.5 <= 3.0
    with pytest.raises(P.MarketParseError):
        P.parse_game_handicap(runners)


def test_game_handicap_unpaired_giver_refuses() -> None:
    runners = _double_line_handicap_runners([5.5])  # valid pair, max>3
    runners.append(_runner(9628236, "A Tomljanovic", -4.5))  # dangling giver, no B@+4.5
    with pytest.raises(P.MarketParseError):
        P.parse_game_handicap(runners)


def test_game_handicap_more_than_two_players_refuses() -> None:
    runners = _double_line_handicap_runners([4.5])
    runners.append(_runner(999, "Third Player", -4.5))
    with pytest.raises(P.MarketParseError):
        P.parse_game_handicap(runners)


def test_game_handicap_player_mapped_to_two_ids_refuses() -> None:
    runners = _double_line_handicap_runners([4.5])
    runners.append(_runner(8888, "A Tomljanovic", -5.5))
    runners.append(_runner(9607743, "Swan", 5.5))
    with pytest.raises(P.MarketParseError):
        P.parse_game_handicap(runners)


def test_game_handicap_absent_hc_refuses() -> None:
    runners = _double_line_handicap_runners([4.5])
    runners.append(_runner(9628236, "A Tomljanovic", None))
    with pytest.raises(P.MarketParseError):
        P.parse_game_handicap(runners)


def test_game_handicap_zero_line_refuses() -> None:
    runners = _double_line_handicap_runners([4.5])
    runners.append(_runner(9628236, "A Tomljanovic", 0.0))
    runners.append(_runner(9607743, "Swan", 0.0))
    with pytest.raises(P.MarketParseError):
        P.parse_game_handicap(runners)


@pytest.mark.parametrize("bad", [[], "notalist", None])
def test_game_handicap_empty_or_non_list_refuses(bad: object) -> None:
    with pytest.raises(P.MarketParseError):
        P.parse_game_handicap(bad)


def test_game_handicap_row_order_does_not_change_output() -> None:
    runners = _double_line_handicap_runners(_GAME_LADDER)
    a = P.parse_game_handicap(runners)
    b = P.parse_game_handicap(list(reversed(runners)))
    assert a == b


# --------------------------------------------------------------------- determinism
def test_repeated_calls_are_byte_identical_in_repr() -> None:
    tg = _total_games_runners([12.0, 12.5])
    gh = _double_line_handicap_runners([4.5, 5.5])
    assert repr(P.parse_total_games(tg)) == repr(P.parse_total_games(tg))
    assert repr(P.parse_game_handicap(gh)) == repr(P.parse_game_handicap(gh))


def test_runner_with_non_dict_entry_refuses() -> None:
    with pytest.raises(P.MarketParseError):
        P.parse_match_odds([_runner(1, "A", None), ("not", "a", "dict")])
