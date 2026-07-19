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
    JUNE_M1_SEAL_AUTHORISATION_DIGEST,
    JuneLockboxSealedError,
    OutcomeAccessAuthorisation,
    OutcomeAccessNotAuthorisedError,
    OutcomeAccessScope,
    OutcomeScopeError,
    OutcomeUndeterminedError,
    SealAuthorisationMismatchError,
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


def _june_auth(*, seal_digest: str = JUNE_M1_SEAL_AUTHORISATION_DIGEST) -> OutcomeAccessAuthorisation:
    """The Stage-A June-M1 authorisation (Stage 2E; lockbox-june-2026-tennis-v2)."""
    return OutcomeAccessAuthorisation(
        scope=OutcomeAccessScope.JUNE_M1_TRANSFER,
        experiment_id="GATE-M1-JUNE-TRANSFER",
        model_manifest_sha256=_SHA,
        feature_manifest_sha256=_SHA,
        data_manifest_sha256=_SHA,
        gate_spec_version="probability-m1",
        granted_by="founder",
        granted_on=date(2026, 7, 18),
        seal_authorisation_digest=seal_digest,
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

    def test_scope_vocabulary_is_exactly_pre_june_and_the_one_authorised_june_scope(self) -> None:
        # GOVERNED CORRECTION (Stage 2E, lockbox-june-2026-tennis-v2; SPEC-092): the founder
        # created ONE explicit digest-bound authorisation for a single controlled June opening.
        # The vocabulary now contains EXACTLY the pre-June scope and the ONE June-M1 scope — no
        # generic JUNE / RESEARCH / MODEL / M2 / ROI / unrestricted outcome scope exists.
        assert [m.name for m in OutcomeAccessScope] == ["PRE_JUNE_DEVELOPMENT", "JUNE_M1_TRANSFER"]

    def test_june_scope_requires_the_exact_v2_seal_digest(self) -> None:
        # A JUNE_M1_TRANSFER authorisation is only valid carrying the exact v2 seal digest.
        with pytest.raises(ValueError):
            OutcomeAccessAuthorisation(
                scope=OutcomeAccessScope.JUNE_M1_TRANSFER,
                experiment_id="GATE-M1-JUNE-TRANSFER",
                model_manifest_sha256=_SHA, feature_manifest_sha256=_SHA,
                data_manifest_sha256=_SHA, gate_spec_version="probability-m1",
                granted_by="founder", granted_on=date(2026, 7, 18),
                seal_authorisation_digest=None,  # missing seal binding
            )

    def test_pre_june_scope_must_not_carry_a_seal_digest(self) -> None:
        # The pre-June path can never carry a June seal authorisation.
        with pytest.raises(ValueError):
            OutcomeAccessAuthorisation(
                scope=OutcomeAccessScope.PRE_JUNE_DEVELOPMENT,
                experiment_id="EXP-X", model_manifest_sha256=_SHA,
                feature_manifest_sha256=_SHA, data_manifest_sha256=_SHA,
                gate_spec_version="gates-v1", granted_by="founder",
                granted_on=date(2026, 7, 18),
                seal_authorisation_digest=JUNE_M1_SEAL_AUTHORISATION_DIGEST,
            )


class TestJuneM1TransferScope:
    """The ONE authorised, digest-bound June opening (Stage 2E; v2 seal). All streams synthetic."""

    def test_authorised_june_market_extracts_only_under_matching_seal_and_membership(self) -> None:
        ex = TennisOutcomeExtractor(
            _june_auth(),
            sealed_market_ids=frozenset({"1.900", "1.901"}),
            june_authorised_market_ids=frozenset({"1.900"}),
        )
        lines = [
            _line("1.900", "OPEN", _IN_JUNE, [{"id": 11, "status": "ACTIVE"}, {"id": 22, "status": "ACTIVE"}]),
            _line("1.900", "CLOSED", _IN_JUNE, [{"id": 11, "status": "WINNER"}, {"id": 22, "status": "LOSER"}], pt=2),
        ]
        out = ex.extract("1.900", lines)
        assert out.winner_selection_id == 11
        assert out.authorisation_digest == _june_auth().content_digest()

    def test_sealed_june_market_not_in_authorised_set_still_refuses(self) -> None:
        ex = TennisOutcomeExtractor(
            _june_auth(),
            sealed_market_ids=frozenset({"1.900", "1.901"}),
            june_authorised_market_ids=frozenset({"1.900"}),
        )
        with pytest.raises(JuneLockboxSealedError):
            ex.extract("1.901", [])  # sealed June market outside the authorised set

    def test_wrong_seal_digest_refuses_at_construction(self) -> None:
        with pytest.raises(SealAuthorisationMismatchError):
            TennisOutcomeExtractor(
                _june_auth(seal_digest="sha256:" + "00" * 32),
                sealed_market_ids=frozenset({"1.900"}),
                june_authorised_market_ids=frozenset({"1.900"}),
            )

    def test_june_scope_requires_a_nonempty_authorised_set(self) -> None:
        with pytest.raises(ValueError):
            TennisOutcomeExtractor(
                _june_auth(), sealed_market_ids=frozenset({"1.900"}),
                june_authorised_market_ids=frozenset(),
            )

    def test_pre_june_authorisation_still_refuses_every_june_market(self) -> None:
        # The other scope continues to refuse June — by membership AND by data.
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset({"1.900"}))
        with pytest.raises(JuneLockboxSealedError):
            ex.extract("1.900", [])
        ex2 = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        lines = [_line("1.902", "CLOSED", _IN_JUNE, [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}])]
        with pytest.raises(OutcomeScopeError):
            ex2.extract("1.902", lines)

    def test_pre_june_authorisation_cannot_carry_a_june_authorised_set(self) -> None:
        with pytest.raises(ValueError):
            TennisOutcomeExtractor(
                _auth(), sealed_market_ids=frozenset({"1.900"}),
                june_authorised_market_ids=frozenset({"1.900"}),
            )

    def test_june_anomalous_settlement_still_refuses(self) -> None:
        ex = TennisOutcomeExtractor(
            _june_auth(), sealed_market_ids=frozenset({"1.900"}),
            june_authorised_market_ids=frozenset({"1.900"}),
        )
        lines = [_line("1.900", "CLOSED", _IN_JUNE, [{"id": 11, "status": "WINNER"}, {"id": 22, "status": "WINNER"}])]
        with pytest.raises(OutcomeUndeterminedError):
            ex.extract("1.900", lines)

    def test_the_frozen_v2_seal_digest_is_pinned(self) -> None:
        assert JUNE_M1_SEAL_AUTHORISATION_DIGEST == (
            "sha256:f552c7bfafd8432693a26d01519ffac29e1d81d7554901041553952b2ddb88c8"
        )


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


class TestSealMutationHardening:
    """Kill behavioural survivors: seal-digest inequality direction, marketTime boundary,
    zero/multiple winners, sha length. All synthetic; no June outcome."""

    def test_seal_digest_lexically_greater_is_refused(self) -> None:
        # A wrong seal digest GREATER than the real one must still refuse (kills != -> <).
        with pytest.raises(SealAuthorisationMismatchError):
            TennisOutcomeExtractor(
                _june_auth(seal_digest="sha256:" + "ff" * 32),
                sealed_market_ids=frozenset({"1.900"}),
                june_authorised_market_ids=frozenset({"1.900"}),
            )

    def test_market_time_exactly_at_boundary_refuses(self) -> None:
        # marketTime exactly 2026-06-01 is IN June -> refuse (kills >= -> >).
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        lines = [_line("1.700", "CLOSED", "2026-06-01T00:00:00.000Z",
                       [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}])]
        with pytest.raises(OutcomeScopeError):
            ex.extract("1.700", lines)

    def test_zero_winners_refuses(self) -> None:
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        lines = [_line("1.555", "CLOSED", _PRE_JUNE,
                       [{"id": 1, "status": "LOSER"}, {"id": 2, "status": "LOSER"}])]
        with pytest.raises(OutcomeUndeterminedError):
            ex.extract("1.555", lines)

    def test_three_winners_refuses(self) -> None:
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        lines = [_line("1.555", "CLOSED", _PRE_JUNE,
                       [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "WINNER"}, {"id": 3, "status": "WINNER"}])]
        with pytest.raises(OutcomeUndeterminedError):
            ex.extract("1.555", lines)

    def test_sha256_of_wrong_length_refused_both_directions(self) -> None:
        base = dict(scope=OutcomeAccessScope.PRE_JUNE_DEVELOPMENT, experiment_id="X",
                    model_manifest_sha256=_SHA, feature_manifest_sha256=_SHA,
                    data_manifest_sha256=_SHA, gate_spec_version="g", granted_by="f",
                    granted_on=date(2026, 7, 18))
        for bad in ("sha256:" + "ab" * 31, "sha256:" + "ab" * 33):  # too short AND too long
            with pytest.raises(ValueError):
                OutcomeAccessAuthorisation(**{**base, "model_manifest_sha256": bad})  # type: ignore[arg-type]

    def test_extractor_skips_other_market_ids_in_a_shared_stream(self) -> None:
        # A CLOSED definition for a DIFFERENT market must not settle this market (kills id != -> ==).
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        lines = [_line("1.OTHER", "CLOSED", _PRE_JUNE, [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}])]
        with pytest.raises(OutcomeUndeterminedError):  # no CLOSED def for 1.555 -> undetermined
            ex.extract("1.555", lines)


class TestExtractControlFlow:
    """Kill extract() market-id skip (!=->>), non-CLOSED handling, and empty-status winner set."""

    def test_smaller_id_closed_def_does_not_settle_target(self) -> None:
        # target "1.500"; stream carries only a CLOSED def for the LEXICALLY-SMALLER "1.100".
        # `!=` skips it -> undetermined; `>` (1.100 > 1.500 == False) would wrongly settle it.
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        lines = [_line("1.100", "CLOSED", _PRE_JUNE, [{"id": 77, "status": "WINNER"}, {"id": 88, "status": "LOSER"}])]
        with pytest.raises(OutcomeUndeterminedError):
            ex.extract("1.500", lines)

    def test_larger_id_closed_def_does_not_settle_target(self) -> None:
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        lines = [_line("1.900", "CLOSED", _PRE_JUNE, [{"id": 77, "status": "WINNER"}, {"id": 88, "status": "LOSER"}])]
        with pytest.raises(OutcomeUndeterminedError):
            ex.extract("1.500", lines)

    def test_open_status_is_not_treated_as_settlement(self) -> None:
        # kills == "CLOSED" -> >=/<=/is-not : an OPEN def (no WINNER) must not yield a winner.
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        lines = [_line("1.500", "OPEN", _PRE_JUNE, [{"id": 1, "status": "ACTIVE"}, {"id": 2, "status": "ACTIVE"}])]
        with pytest.raises(OutcomeUndeterminedError):
            ex.extract("1.500", lines)


def _dup(s: str) -> str:
    """Value-equal but guaranteed DIFFERENT string object (as a digest loaded at runtime)."""
    d = s.encode("utf-8").decode("utf-8")
    assert d == s and d is not s
    return d


def _multi_mc_line(entries: list[dict], *, pt: int = 1) -> str:
    """One stream message carrying several market-change (mc) entries verbatim."""
    return json.dumps({"op": "mcm", "pt": pt, "mc": entries})


class TestExtractControlFlowHardening:
    """Kill the L273 non-CLOSED comparison mutants (need a WINNER present), the exact-WINNER match
    (== -> >=), the keyword-only marker, the seal != -> is-not, and the three inner continue->break."""

    def _ext(self):
        return TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())

    def test_open_with_winner_is_not_settled(self) -> None:
        # OPEN > "CLOSED" lexically: kills == -> >= and == -> is-not. A WINNER is present, so a mutant
        # that treats OPEN as a settlement WOULD return; the exact == must refuse (undetermined).
        lines = [_line("1.500", "OPEN", _PRE_JUNE, [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}])]
        with pytest.raises(OutcomeUndeterminedError):
            self._ext().extract("1.500", lines)

    def test_abandoned_with_winner_is_not_settled(self) -> None:
        # "ABANDONED" < "CLOSED" lexically: kills == -> <=. WINNER present; only exact "CLOSED" settles.
        lines = [_line("1.500", "ABANDONED", _PRE_JUNE, [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}])]
        with pytest.raises(OutcomeUndeterminedError):
            self._ext().extract("1.500", lines)

    def test_non_winner_status_lexically_after_winner_is_not_counted(self) -> None:
        # A CLOSED market with one real WINNER and a runner whose status is lexically > "WINNER"
        # ("ZED" > "WINNER"): kills st == "WINNER" -> st >= "WINNER" (mutant counts 2 -> undetermined).
        lines = [_line("1.500", "CLOSED", _PRE_JUNE,
                       [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "ZED"}])]
        out = self._ext().extract("1.500", lines)
        assert out.winner_selection_id == 1

    def test_sealed_market_ids_is_keyword_only(self) -> None:
        # `*` -> `/` would make sealed_market_ids positional; it must stay keyword-only.
        with pytest.raises(TypeError):
            TennisOutcomeExtractor(_auth(), frozenset())   # type: ignore[misc]

    def test_june_seal_matches_by_value_not_identity(self) -> None:
        # seal digest checked by EQUALITY: a value-equal DIFFERENT-object seal (as loaded at runtime)
        # MUST be accepted. Kills != -> is-not (which would reject the equal-but-distinct digest).
        ex = TennisOutcomeExtractor(
            _june_auth(seal_digest=_dup(JUNE_M1_SEAL_AUTHORISATION_DIGEST)),
            sealed_market_ids=frozenset({"1.900"}),
            june_authorised_market_ids=frozenset({"1.900"}),
        )
        assert ex is not None   # construction succeeded past the seal-equality guard

    def test_auth_content_digest_exact_value(self) -> None:
        # Kills sort_keys=True -> False in OutcomeAccessAuthorisation.content_digest (reorders keys).
        assert _auth().content_digest() == "sha256:1438b957591bbfe7738ed20b19b92a89ae4d1a240b0e8a5a216c96e37323e4de"

    def test_blank_line_before_closed_is_skipped_not_terminal(self) -> None:
        # kills the empty-line `continue` -> `break`: a blank line must be skipped, not end the stream.
        lines = ["", _line("1.500", "CLOSED", _PRE_JUNE,
                           [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}])]
        assert self._ext().extract("1.500", lines).winner_selection_id == 1

    def test_foreign_mc_before_target_mc_in_same_message(self) -> None:
        # kills the id-mismatch `continue` -> `break`: a non-target mc ahead of the target mc in the
        # SAME message must be skipped, not terminate the mc loop.
        md_closed = {"status": "CLOSED", "marketTime": _PRE_JUNE, "marketType": "MATCH_ODDS",
                     "runners": [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}]}
        line = _multi_mc_line([
            {"id": "1.OTHER", "marketDefinition": {"status": "CLOSED", "marketTime": _PRE_JUNE,
                                                   "runners": [{"id": 9, "status": "WINNER"}]}},
            {"id": "1.500", "marketDefinition": md_closed},
        ])
        assert self._ext().extract("1.500", [line]).winner_selection_id == 1

    def test_mc_without_definition_before_defined_mc_in_same_message(self) -> None:
        # kills the md-None `continue` -> `break`: a target mc with no marketDefinition ahead of the
        # target mc WITH one must be skipped, not terminate the mc loop.
        md_closed = {"status": "CLOSED", "marketTime": _PRE_JUNE, "marketType": "MATCH_ODDS",
                     "runners": [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}]}
        line = _multi_mc_line([
            {"id": "1.500"},                                   # no marketDefinition
            {"id": "1.500", "marketDefinition": md_closed},
        ])
        assert self._ext().extract("1.500", [line]).winner_selection_id == 1


class TestFrozenTennisDataclasses:
    """§7: OutcomeAccessAuthorisation and ExtractedMatchOutcome are frozen. Kills
    ReplaceTrueWithFalse on @dataclass(frozen=True)."""

    def test_authorisation_is_frozen(self) -> None:
        import dataclasses
        a = _auth()
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.experiment_id = "other"   # type: ignore[misc]
        assert isinstance(hash(a), int)

    def test_extracted_outcome_is_frozen(self) -> None:
        import dataclasses
        ex = TennisOutcomeExtractor(_auth(), sealed_market_ids=frozenset())
        out = ex.extract("1.500", [_line("1.500", "CLOSED", _PRE_JUNE,
                                          [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}])])
        with pytest.raises(dataclasses.FrozenInstanceError):
            out.winner_selection_id = 2   # type: ignore[misc]
        # (ExtractedMatchOutcome carries a dict field -> intentionally unhashable; the frozen setattr
        # guard above is the discriminator for frozen=True vs the mutated frozen=False.)
