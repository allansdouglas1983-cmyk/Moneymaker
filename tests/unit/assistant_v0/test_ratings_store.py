"""V0 release — frozen F2-v1 rating-store adapter (red tests first).

The store is a READER of an existing frozen F2-v1 rating snapshot supplied by the founder as
a local JSON file. It builds NO model and fits nothing: it resolves (tour, display name) to
(rating, prior_match_count) or None. Unresolved identities stay visible (the pipeline maps
them to IDENTITY_UNRESOLVED), and a malformed store refuses at load rather than guessing.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from assistant_v0 import ratings_store as RS


def _store(tmp_path: Path, payload: dict[str, object]) -> Path:
    p = tmp_path / "ratings.json"
    p.write_text(json.dumps(payload))
    return p


_VALID: dict[str, object] = {
    "rating_state_version": "F2_V1_FROZEN",
    "source": "docs/evidence/stage2b-f0-f2-runs",
    "players": {
        "ATP": {"A Player": {"rating": 1600.0, "matches": 40},
                "B Player": {"rating": 1500.0, "matches": 30}},
        "WTA": {"C Player": {"rating": 1550.0, "matches": 12}},
    },
}


def test_resolves_known_player_per_tour(tmp_path: Path) -> None:
    lookup = RS.load_rating_lookup(_store(tmp_path, _VALID))
    assert lookup("ATP", "A Player") == (1600.0, 40)
    assert lookup("ATP", "B Player") == (1500.0, 30)
    assert lookup("WTA", "C Player") == (1550.0, 12)


def test_unknown_player_or_tour_is_unresolved_never_guessed(tmp_path: Path) -> None:
    lookup = RS.load_rating_lookup(_store(tmp_path, _VALID))
    assert lookup("ATP", "Unknown Player") is None
    assert lookup("WTA", "A Player") is None          # right name, wrong tour -> unresolved
    assert lookup("ITF", "A Player") is None          # unknown tour -> unresolved


def test_tours_are_separate_namespaces(tmp_path: Path) -> None:
    """ATP and WTA rating states are never pooled (the frozen F2-v1 separation)."""
    payload = json.loads(json.dumps(_VALID))
    payload["players"]["WTA"]["A Player"] = {"rating": 1234.0, "matches": 7}
    lookup = RS.load_rating_lookup(_store(tmp_path, payload))
    assert lookup("ATP", "A Player") == (1600.0, 40)
    assert lookup("WTA", "A Player") == (1234.0, 7)


def test_missing_file_refuses(tmp_path: Path) -> None:
    with pytest.raises(RS.RatingStoreError):
        RS.load_rating_lookup(tmp_path / "absent.json")


@pytest.mark.parametrize("bad", [
    {"players": {}},                                                   # no version
    {"rating_state_version": "F2_V1_FROZEN"},                          # no players
    {"rating_state_version": "F2_V1_FROZEN", "players": []},           # players not a mapping
    {"rating_state_version": "F2_V1_FROZEN",
     "players": {"ATP": {"X": {"rating": "high", "matches": 3}}}},      # non-numeric rating
    {"rating_state_version": "F2_V1_FROZEN",
     "players": {"ATP": {"X": {"rating": 1500.0, "matches": -1}}}},     # negative history
    {"rating_state_version": "F2_V1_FROZEN",
     "players": {"ATP": {"X": {"rating": 1500.0}}}},                    # missing matches
])
def test_malformed_store_refuses_at_load(tmp_path: Path, bad: dict[str, object]) -> None:
    with pytest.raises(RS.RatingStoreError):
        RS.load_rating_lookup(_store(tmp_path, bad))


def test_store_is_read_only_and_deterministic(tmp_path: Path) -> None:
    p = _store(tmp_path, _VALID)
    before = p.read_bytes()
    l1 = RS.load_rating_lookup(p)
    l2 = RS.load_rating_lookup(p)
    assert l1("ATP", "A Player") == l2("ATP", "A Player")
    assert p.read_bytes() == before                    # loading never writes to the store


def test_store_digest_is_content_bound(tmp_path: Path) -> None:
    p = _store(tmp_path, _VALID)
    d1 = RS.rating_state_digest(p)
    assert d1.startswith("sha256:")
    assert RS.rating_state_digest(p) == d1                     # stable for identical content
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    changed = json.loads(json.dumps(_VALID))
    changed["players"]["ATP"]["A Player"]["rating"] = 1601.0
    assert RS.rating_state_digest(_store(other_dir, changed)) != d1
