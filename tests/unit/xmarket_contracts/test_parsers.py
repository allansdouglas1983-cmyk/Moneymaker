"""STAGE3-0004 §10/§14 — PROMOTED cross-market selection parsers (red tests first).

Production re-home of the audit parsers behind neutral contracts, hardened to the
advice-critical bar. Preserves raw ``marketType`` (never renamed); type-specific selection
parsing; Set Handicap can NEVER become Game Handicap; Total Games line extraction;
malformed/ambiguous refuse. No probability, no outcome, no fitted maths.
"""
from __future__ import annotations

import dataclasses

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


@pytest.mark.parametrize("mags", [[0.5], [1.5, 2.5], [0.5, 1.5, 2.5]])
def test_set_handicap_below_threshold_refused(mags: list[float]) -> None:
    # INTEGRITY-CRITICAL (STAGE3-0006 §8): the guard is `max|line| <= _MAX_PLAUSIBLE_SET_HANDICAP`
    # (3.0). It must refuse a set handicap whose max magnitude lies STRICTLY BELOW 3.0, not only at
    # exactly 3.0. A `<=`->`==` mutant refuses only the single point 3.0 and would ACCEPT a genuine
    # set handicap (max 2.5) as a game handicap. The pre-existing 3.0/3.5 pair cannot distinguish
    # this; these strictly-interior cases do.
    with pytest.raises(P.MarketParseError):
        P.parse_game_handicap(_gh(mags))


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


# ---------------------------------------------------------------------------
# STAGE3-0006 §8 mutation-kill tests (behavioural survivors, section C).
# ---------------------------------------------------------------------------

def _fresh_int(n: int) -> int:
    """A fresh, non-interned int object equal in value to ``n`` (forces `is` != `==`)."""
    return int(str(n))


def _fresh_str(s: str) -> str:
    """A fresh, non-interned str object equal in value to ``s``."""
    return s.encode().decode()


def test_total_games_line_frozen_and_hashable() -> None:
    """L55 TotalGamesLine @dataclass(frozen=True) ReplaceTrueWithFalse::0."""
    line = P.parse_total_games(_tg([12.0]))[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        line.line = 0.0  # type: ignore[misc]
    assert isinstance(hash(line), int)


def test_game_handicap_line_frozen_and_hashable() -> None:
    """L62 GameHandicapLine @dataclass(frozen=True) ReplaceTrueWithFalse::1."""
    line = P.parse_game_handicap(_gh([4.5]))[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        line.line = 0.0  # type: ignore[misc]
    assert isinstance(hash(line), int)


def test_runner_empty_name_refused() -> None:
    """L75 `not isinstance(name, str) or not name` ReplaceOrWithAnd::2 — `and` would
    accept an empty name."""
    with pytest.raises(P.MarketParseError):
        P.parse_match_odds([_runner(1, "", None), _runner(2, "B", None)])


def test_total_games_non_list_runners_refused() -> None:
    """L85 `not isinstance(runners, list) or not runners` ReplaceOrWithAnd::4 — `and`
    lets a truthy non-list through (then TypeError, not MarketParseError)."""
    with pytest.raises(P.MarketParseError):
        P.parse_total_games(5)


def test_game_handicap_non_list_runners_refused() -> None:
    """L117 `not isinstance(runners, list) or not runners` ReplaceOrWithAnd::5."""
    with pytest.raises(P.MarketParseError):
        P.parse_game_handicap(5)


def test_total_games_name_sorting_below_over_refused() -> None:
    """L94 `side == "over"` Eq_LtE::0 — `<=` would treat any name lexically <= "over"
    (e.g. "later") as Over."""
    with pytest.raises(P.MarketParseError):
        P.parse_total_games([_runner(1, "Later", 12.0), _runner(2, "Under", 12.0)])


def test_total_games_name_below_under_refused() -> None:
    """L98 `side == "under"` Eq_LtE::1 / Eq_IsNot::1 — "aaa" <= "under" and identity
    mismatch would be admitted as Under."""
    with pytest.raises(P.MarketParseError):
        P.parse_total_games([_runner(1, "Over", 12.0), _runner(2, "Aaa", 12.0)])


def test_total_games_name_above_under_refused() -> None:
    """L98 `side == "under"` Eq_GtE::1 / Eq_IsNot::1 — "zzz" >= "under" and identity
    mismatch would be admitted as Under."""
    with pytest.raises(P.MarketParseError):
        P.parse_total_games([_runner(1, "Over", 12.0), _runner(2, "Zzz", 12.0)])


def test_total_games_unpaired_under_refused() -> None:
    """L104 `set(overs) ^ set(unders)` BitXor_Sub — `overs - unders` misses an unpaired
    *Under* line (13.0)."""
    with pytest.raises(P.MarketParseError):
        P.parse_total_games([_runner(7, "Over", 12.0), _runner(8, "Under", 12.0),
                             _runner(9, "Under", 13.0)])


def test_game_handicap_three_players_message() -> None:
    """L124 `len(names) != 2` NotEq_Lt::0 — mutant `<` falls through to the L134 backstop
    ("exactly two player ids"), so pin the L124 message."""
    with pytest.raises(P.MarketParseError, match="exactly two distinct players"):
        P.parse_game_handicap(_gh([4.5]) + [_runner(999, "C", -4.5)])


def test_game_handicap_single_player_message() -> None:
    """L124 `len(names) != 2` NotEq_Gt::0 — mutant `>` (len 1) falls through to L134, so
    pin the L124 message."""
    with pytest.raises(P.MarketParseError, match="exactly two distinct players"):
        P.parse_game_handicap([_runner(5, "A", -4.5), _runner(5, "A", 4.5)])


def test_game_handicap_name_maps_two_ids_smaller_second() -> None:
    """L130 `... setdefault(name, rid) != rid` NotEq_Lt::1 — second id smaller: `100 < 50`
    is False, so `<` would not refuse a name mapping to two ids."""
    runners = [_runner(100, "A", -4.5), _runner(50, "A", 4.5),
               _runner(200, "B", 4.5), _runner(200, "B", -4.5)]
    with pytest.raises(P.MarketParseError, match="maps to two ids"):
        P.parse_game_handicap(runners)


def test_game_handicap_name_maps_two_ids_larger_second() -> None:
    """L130 `... setdefault(name, rid) != rid` NotEq_Gt::1 — second id larger: `100 > 200`
    is False, so `>` would not refuse a name mapping to two ids."""
    runners = [_runner(100, "A", -4.5), _runner(200, "A", 4.5),
               _runner(300, "B", 4.5), _runner(300, "B", -4.5)]
    with pytest.raises(P.MarketParseError, match="maps to two ids"):
        P.parse_game_handicap(runners)


def test_game_handicap_name_two_equal_nonidentical_ids_accepted() -> None:
    """L130 `... != rid` NotEq_IsNot::0 — the same player's id given as two equal-but-
    non-identical int objects is one valid player; `is not` would wrongly refuse it."""
    a1, a2 = _fresh_int(9628236), _fresh_int(9628236)
    b1, b2 = _fresh_int(9607743), _fresh_int(9607743)
    runners = [_runner(a1, "A", -4.5), _runner(b1, "B", 4.5),
               _runner(a2, "A", 4.5), _runner(b2, "B", -4.5)]
    out = P.parse_game_handicap(runners)
    assert len(out) == 2


def test_game_handicap_id_maps_two_names_reverse_ordered() -> None:
    """L132 `... setdefault(rid, name) != name` NotEq_Lt::2 — id 100 -> 'Z' then 'A':
    `'Z' < 'A'` is False, so `<` would not refuse an id mapping to two names."""
    with pytest.raises(P.MarketParseError, match="maps to two names"):
        P.parse_game_handicap([_runner(100, "Z", -4.5), _runner(100, "A", 4.5)])


def test_game_handicap_id_maps_two_names_forward_ordered() -> None:
    """L132 `... setdefault(rid, name) != name` NotEq_Gt::2 — id 100 -> 'A' then 'Z':
    `'A' > 'Z'` is False, so `>` would not refuse an id mapping to two names."""
    with pytest.raises(P.MarketParseError, match="maps to two names"):
        P.parse_game_handicap([_runner(100, "A", -4.5), _runner(100, "Z", 4.5)])


def test_game_handicap_id_two_equal_nonidentical_names_accepted() -> None:
    """L132 `... != name` NotEq_IsNot::1 — the same player's name as two equal-but-
    non-identical str objects is one valid player; `is not` would wrongly refuse it."""
    runners = [_runner(9628236, _fresh_str("Alpha"), -4.5),
               _runner(9607743, _fresh_str("Beta"), 4.5),
               _runner(9628236, _fresh_str("Alpha"), 4.5),
               _runner(9607743, _fresh_str("Beta"), -4.5)]
    out = P.parse_game_handicap(runners)
    assert len(out) == 2


def test_game_handicap_giver_receiver_identity_pairing() -> None:
    """L159 `other = b_id if gid == a_id else a_id` Eq_Is::2 — with equal-but-non-identical
    ids `is` mispairs the receiver."""
    a1, a2 = _fresh_int(9628236), _fresh_int(9628236)
    b1, b2 = _fresh_int(9607743), _fresh_int(9607743)
    runners = [_runner(a1, "A", -4.5), _runner(b1, "B", 4.5),
               _runner(a2, "A", 4.5), _runner(b2, "B", -4.5)]
    out = P.parse_game_handicap(runners)
    by_giver = {ln.giver_runner_id: ln for ln in out}
    assert by_giver[9628236].receiver_runner_id == 9607743
    assert by_giver[9607743].receiver_runner_id == 9628236


def test_match_odds_three_runners_refused() -> None:
    """L175 `len(runners) != 2` NotEq_Lt::4 — `3 < 2` is False, so `<` would unpack 3
    runners into 2 (ValueError, not MarketParseError)."""
    with pytest.raises(P.MarketParseError):
        P.parse_match_odds([_runner(1, "A", None), _runner(2, "B", None), _runner(3, "C", None)])


def test_match_odds_three_runners_count_message() -> None:
    """L176 `n = len(runners) if isinstance(runners, list) else "?"` AddNot::29 — the
    negated isinstance would report "got ?" instead of "got 3"."""
    with pytest.raises(P.MarketParseError, match="got 3"):
        P.parse_match_odds([_runner(1, "A", None), _runner(2, "B", None), _runner(3, "C", None)])


def test_match_odds_ascending_ids_returned() -> None:
    """L179 `a[0] == b[0]` Eq_LtE::4 — with ascending ids `11 <= 22` is True and `<=`
    would wrongly refuse; baseline returns them sorted."""
    assert P.parse_match_odds([_runner(11, "A", None), _runner(22, "B", None)]) == (11, 22)


def test_match_odds_shared_equal_nonidentical_id_refused() -> None:
    """L179 `a[0] == b[0]` Eq_Is::3 — two equal-but-non-identical id objects share an id;
    `is` would miss it and return."""
    with pytest.raises(P.MarketParseError):
        P.parse_match_odds([_runner(_fresh_int(9628236), "A", None),
                            _runner(_fresh_int(9628236), "B", None)])
