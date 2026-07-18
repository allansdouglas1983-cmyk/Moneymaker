"""Founder decision 4 (2026-07-18): the governed tennis outcome extractor.

Authorised scope is PRE-JUNE DEVELOPMENT ONLY. June lockbox outcomes remain structurally
sealed: the scope vocabulary cannot express a June opening (a separate founder
authorisation would have to add it as a governed change), sealed membership refuses by
market_id, and any observed marketTime on/after 2026-06-01 refuses by data even for a
market missing from the membership list. Every extraction is bound to the experiment,
model, feature, data and gate manifests via the authorisation record, whose digest is
stamped onto the extracted outcome.

ALL streams in these tests are SYNTHETIC — no real corpus file, no June outcome, is read.
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from l8_evidence.tennis_outcomes import (
    JuneLockboxSealedError,
    OutcomeAccessAuthorisation,
    OutcomeAccessNotAuthorisedError,
    OutcomeAccessScope,
    OutcomeScopeError,
    OutcomeUndeterminedError,
    TennisOutcomeExtractor,
    extract_match_outcome,
    load_sealed_market_ids,
)
from sport_core.outcomes import ChoiceSetResolution

pytestmark = [pytest.mark.spec("SPEC-092"), pytest.mark.spec("SPEC-023")]

_SHA = "sha256:" + "ab" * 32


def _auth() -> OutcomeAccessAuthorisation:
    return OutcomeAccessAuthorisation(
        scope=OutcomeAccessScope.PRE_JUNE_DEVELOPMENT,
        experiment_id="EXP-STAGE2-F2-weighted-elo",
        model_manifest_sha256=_SHA,
        feature_manifest_sha256=_SHA,
        data_manifest_sha256=_SHA,
        gate_spec_version="gates-v1",
        granted_by="founder",
        granted_on=date(2026, 7, 18),
    )


def _line(market_id: str, status: str, market_time: str, runners: list[dict[str, object]], *, settled: str | None = None, pt: int = 1) -> str:
    md: dict[str, object] = {
        "status": status,
        "marketTime": market_time,
        "runners": runners,
        "marketType": "MATCH_ODDS",
    }
    if settled is not None:
        md["settledTime"] = settled
    return json.dumps({"op": "mcm", "pt": pt, "mc": [{"id": market_id, "marketDefinition": md}]})


_PRE_JUNE = "2026-05-20T10:00:00.000Z"
_IN_JUNE = "2026-06-03T10:00:00.000Z"


class TestAuthorisationRecord:
    def test_valid_record_has_digest(self) -> None:
        a = _auth()
        assert a.content_digest().startswith("sha256:")

    @pytest.mark.parametrize(
        "field,value",
        [
            ("experiment_id", ""),
            ("model_manifest_sha256", "deadbeef"),
            ("feature_manifest_sha256", "sha256:short"),
            ("data_manifest_sha256", ""),
            ("gate_spec_version", ""),
            ("granted_by", ""),
        ],
    )
    def test_invalid_fields_refused(self, field: str, value: str) -> None:
        kwargs: dict[str, object] = dict(
            scope=OutcomeAccessScope.PRE_JUNE_DEVELOPMENT,
            experiment_id="EXP-X",
            model_manifest_sha256=_SHA,
            feature_manifest_sha256=_SHA,
            data_manifest_sha256=_SHA,
            gate_spec_version="gates-v1",
            granted_by="founder",
            granted_on=date(2026, 7, 18),
        )
        kwargs[field] = value
        with pytest.raises(ValueError):
            OutcomeAccessAuthorisation(**kwargs)  # type: ignore[arg-type]

    def test_scope_vocabulary_cannot_express_june(self) -> None:
        # The structural seal: there is no June member to pass.
        assert [m.name for m in OutcomeAccessScope] == ["PRE_JUNE_DEVELOPMENT"]


class TestExtraction:
    def test_pre_june_winner_extracts(self) -> None:
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset({"1.999"}))
        lines = [
            _line("1.555", "OPEN", _PRE_JUNE, [{"id": 1, "status": "ACTIVE"}, {"id": 2, "status": "ACTIVE"}]),
            _line(
                "1.555",
                "CLOSED",
                _PRE_JUNE,
                [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}],
                settled="2026-05-20T12:34:56.000Z",
                pt=2,
            ),
        ]
        out = ex.extract("1.555", lines)
        assert out.resolution is ChoiceSetResolution.WINNER_KNOWN
        assert out.winner_selection_id == 1
        assert out.settled_time == "2026-05-20T12:34:56.000Z"
        assert out.authorisation_digest == _auth().content_digest()

    def test_sealed_market_refused_even_with_valid_authorisation(self) -> None:
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset({"1.555"}))
        with pytest.raises(JuneLockboxSealedError):
            ex.extract("1.555", [])

    def test_june_market_time_refused_by_data_even_if_not_in_seal_list(self) -> None:
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        lines = [
            _line("1.777", "OPEN", _IN_JUNE, [{"id": 1, "status": "ACTIVE"}, {"id": 2, "status": "ACTIVE"}]),
            _line("1.777", "CLOSED", _IN_JUNE, [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}], pt=2),
        ]
        with pytest.raises(OutcomeScopeError):
            ex.extract("1.777", lines)

    def test_no_closed_definition_refuses(self) -> None:
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        lines = [_line("1.555", "OPEN", _PRE_JUNE, [{"id": 1, "status": "ACTIVE"}, {"id": 2, "status": "ACTIVE"}])]
        with pytest.raises(OutcomeUndeterminedError):
            ex.extract("1.555", lines)

    def test_anomalous_settlement_pattern_refuses_never_guesses(self) -> None:
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        # two WINNERs on a two-runner match-odds market: anomalous — refuse, never map
        lines = [
            _line("1.555", "CLOSED", _PRE_JUNE, [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "WINNER"}]),
        ]
        with pytest.raises(OutcomeUndeterminedError):
            ex.extract("1.555", lines)


class TestModuleLevelStaysRefusing:
    def test_unauthorised_convenience_path_always_refuses(self) -> None:
        with pytest.raises(OutcomeAccessNotAuthorisedError):
            extract_match_outcome("1.234", {"anything": "here"})


class TestSealLoader:
    def test_loads_the_sealed_june_membership(self) -> None:
        ids = load_sealed_market_ids()
        assert len(ids) == 2876
        assert all(i.startswith("1.") for i in ids)
