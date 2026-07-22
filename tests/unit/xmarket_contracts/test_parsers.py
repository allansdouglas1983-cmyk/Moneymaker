"""STAGE3-0004 §10/§14 — PROMOTED cross-market selection parsers (red tests first).

Production re-home of the audit parsers behind neutral contracts, hardened to the
advice-critical bar. Preserves raw ``marketType`` (never renamed); type-specific selection
parsing; Set Handicap can NEVER become Game Handicap; Total Games line extraction;
malformed/ambiguous refuse. No probability, no outcome, no fitted maths.
"""
from __future__ import annotations

import pytest

from xmarket_contracts import parsers as P


def _runner(rid: int, name: str, hc: float | None) -> dict[str, object]:
    d: dict[str, object] = {"id": rid, "name": name}
    if hc is not None:
        d["hc"] = hc
    return d


def _tg(lines: list[float], over: int = 7698572, under: int = 7698577) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for ln in lines:
        out.append(_runner(over, "Over", ln))
        out.append(_runner(under, "Under", ln))
    return out


def _gh(mags: list[float], a: int = 9628236, b: int = 9607743) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for m in mags:
        out.append(_runner(a, "A", -m))
        out.append(_runner(b, "B", +m))
        out.append(_runner(a, "A", +m))
        out.append(_runner(b, "B", -m))
    return out


_GAME = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]


def test_parser_version_pinned() -> None:
    assert P.PARSER_VERSION == "xmarket-contracts-parsers-v1"


def test_market_role_preserves_raw_and_fails_closed() -> None:
    assert P.market_role("MATCH_ODDS") == P.PRIMARY_MATCH_ODDS
    assert P.market_role("COMBINED_TOTAL") == P.PRIMARY_IDENTIFYING_TOTAL_GAMES
    assert P.market_role("HANDICAP") == P.PRIMARY_IDENTIFYING_GAME_HANDICAP
    assert P.market_role("SET_WINNER") == P.AUXILIARY_SET_STRUCTURE
    assert P.market_role("SET_CORRECT_SCORE") == P.AUXILIARY_OTHER
    assert P.market_role("TOURNAMENT_WINNER") == P.UNSUPPORTED
    assert P.market_role("NEW_TYPE") == P.UNKNOWN_REQUIRES_REVIEW  # fail closed, never renamed
    assert P.market_role("match_odds") == P.UNKNOWN_REQUIRES_REVIEW  # raw is raw (case-sensitive)


@pytest.mark.parametrize("bad", ["", 5, None])
def test_market_role_refuses_non_string(bad: object) -> None:
    with pytest.raises(P.MarketParseError):
        P.market_role(bad)  # type: ignore[arg-type]


def test_total_games_over_under_and_line() -> None:
    lines = P.parse_total_games(_tg([12.0, 12.5, 13.0]))
    assert [ln.line for ln in lines] == [12.0, 12.5, 13.0]
    assert all(ln.over_runner_id == 7698572 and ln.under_runner_id == 7698577 for ln in lines)


@pytest.mark.parametrize("mut", [
    lambda: [_runner(1, "Over", 12.0)],                                    # missing Under
    lambda: _tg([12.0]) + [_runner(7698572, "Over", 12.0)],               # duplicate Over
    lambda: [_runner(1, "Yes", 12.0), _runner(2, "No", 12.0)],            # non-Over/Under
    lambda: [_runner(7698572, "Over", None), _runner(7698577, "Under", None)],  # no line
    lambda: [],                                                            # empty
])
def test_total_games_refusals(mut) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(P.MarketParseError):
        P.parse_total_games(mut())


def test_total_games_row_order_invariant() -> None:
    a = P.parse_total_games(_tg([12.0, 12.5, 13.0]))
    b = P.parse_total_games(list(reversed(_tg([12.0, 12.5, 13.0]))))
    assert a == b


def test_game_handicap_double_line_two_lines_per_magnitude() -> None:
    out = P.parse_game_handicap(_gh(_GAME))
    assert len(out) == 2 * len(_GAME)
    assert {ln.giver_runner_id for ln in out if ln.line == 4.5} == {9628236, 9607743}
    for ln in out:
        assert ln.line > 0.0 and ln.giver_runner_id != ln.receiver_runner_id


def test_set_handicap_boundary_at_3_0_refuses_and_3_5_accepts() -> None:
    # max|hc| == 3.0 is a SET handicap -> refuse; > 3.0 is a GAME handicap -> accept.
    with pytest.raises(P.MarketParseError):
        P.parse_game_handicap(_gh([1.5, 3.0]))
    assert {ln.line for ln in P.parse_game_handicap(_gh([1.5, 3.5]))} == {1.5, 3.5}


def test_game_handicap_giver_is_negative_hc() -> None:
    out = P.parse_game_handicap(_gh([4.5]))
    by_giver = {ln.giver_runner_id: ln for ln in out}
    assert by_giver[9628236].receiver_runner_id == 9607743
    assert by_giver[9607743].receiver_runner_id == 9628236


@pytest.mark.parametrize("mut", [
    lambda: _gh([5.5]) + [_runner(9628236, "A", -4.5)],                   # dangling giver
    lambda: _gh([4.5]) + [_runner(999, "C", -4.5)],                       # 3rd player
    lambda: _gh([4.5]) + [_runner(9628236, "A", None)],                   # no line
    lambda: _gh([4.5]) + [_runner(9628236, "A", 0.0), _runner(9607743, "B", 0.0)],  # zero line
    lambda: [],                                                            # empty
])
def test_game_handicap_refusals(mut) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(P.MarketParseError):
        P.parse_game_handicap(mut())


def test_match_odds_two_ids_sorted_and_refusals() -> None:
    assert P.parse_match_odds([_runner(22, "Z", None), _runner(11, "A", None)]) == (11, 22)
    with pytest.raises(P.MarketParseError):
        P.parse_match_odds([_runner(5, "A", None), _runner(5, "B", None)])   # shared id
    with pytest.raises(P.MarketParseError):
        P.parse_match_odds([_runner(1, "A", None)])                          # wrong count


def test_determinism_repr() -> None:
    assert repr(P.parse_game_handicap(_gh([4.5, 5.5]))) == repr(P.parse_game_handicap(_gh([4.5, 5.5])))
