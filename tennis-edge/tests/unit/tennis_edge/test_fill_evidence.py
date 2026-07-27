"""Does the trade record support the fill the backtest just credited itself with?

A Betfair Historical BASIC file is a last-trade trace: it says what *somebody* was matched
at, not what was available to us. Settling a backtest at those prices and reporting a return
assumes every claimed fill happened, and that assumption is invisible in the output — it
looks exactly like a return that was earned.

These tests pin the falsification that replaces the assumption. A claimed back at price P is
SUPPORTED when the market later trades at P or better before the off, because then somebody
demonstrably was matched there. It is UNSUPPORTED when later trades exist and all of them are
worse. And it is NO_EVIDENCE when nothing traded afterwards at all — which is a third state
and not a polite word for either of the others. Collapsing it into UNSUPPORTED punishes quiet
markets for being quiet; collapsing it into SUPPORTED credits fills nobody witnessed.

None of this recovers order-book depth. It converts an unstated assumption into a stated,
falsifiable one, which is the most a trace can honestly carry.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from tennis_edge.betfair import InPlayRefusedError, LtpObservation, MarketHistory, Runner
from tennis_edge.fill_evidence import (
    FillEvidence,
    FillSupport,
    LiquidityStratum,
    stratify,
    traded_through,
)

#: Scheduled off. Every observation below is expressed as seconds before it.
OFF_MS = 1_700_000_000_000
SELECTION = 101
OTHER = 202


def _at(seconds_before_off: int) -> int:
    return OFF_MS - seconds_before_off * 1000


def _market(prints: list[tuple[int, int, str]]) -> MarketHistory:
    """``prints`` is (seconds_before_off, selection_id, price), earliest first."""
    return MarketHistory(
        market_id="1.234", event_id="9", event_name="A v B", market_type="MATCH_ODDS",
        country_code="GB", market_time_ms=OFF_MS,
        runners=(Runner(selection_id=SELECTION, name="A"),
                 Runner(selection_id=OTHER, name="B")),
        observations=tuple(
            LtpObservation(publish_time_ms=_at(s), selection_id=sid, price=Decimal(p))
            for s, sid, p in prints
        ),
        went_in_play=False,
    )


class TestTradedThrough:
    def test_a_later_print_at_the_same_price_supports_the_fill(self) -> None:
        """Somebody was matched there after we claim to have been. That is the evidence."""
        market = _market([(600, SELECTION, "3.0"), (300, SELECTION, "3.0")])
        evidence = traded_through(market, SELECTION, Decimal("3.0"),
                                  seconds_before_off=600)
        assert evidence.support is FillSupport.SUPPORTED

    def test_a_later_print_at_a_better_price_supports_the_fill(self) -> None:
        """Backing is better at longer odds, so a later print ABOVE the claim supports it:
        if 3.2 was matched, 3.0 was reachable."""
        market = _market([(600, SELECTION, "3.0"), (120, SELECTION, "3.2")])
        evidence = traded_through(market, SELECTION, Decimal("3.0"),
                                  seconds_before_off=600)
        assert evidence.support is FillSupport.SUPPORTED
        assert evidence.best_subsequent == Decimal("3.2")

    def test_later_prints_all_worse_leave_the_fill_unsupported(self) -> None:
        """The price shortened and never came back. Nobody is witnessed at 3.0 after us."""
        market = _market([(600, SELECTION, "3.0"), (400, SELECTION, "2.9"),
                          (100, SELECTION, "2.7")])
        evidence = traded_through(market, SELECTION, Decimal("3.0"),
                                  seconds_before_off=600)
        assert evidence.support is FillSupport.UNSUPPORTED
        assert evidence.best_subsequent == Decimal("2.9")

    def test_no_later_prints_is_its_own_state_not_a_verdict(self) -> None:
        """A market that goes quiet has told us nothing. Calling that UNSUPPORTED would
        punish illiquidity we did not observe; calling it SUPPORTED would credit a fill
        nobody witnessed."""
        market = _market([(600, SELECTION, "3.0")])
        evidence = traded_through(market, SELECTION, Decimal("3.0"),
                                  seconds_before_off=600)
        assert evidence.support is FillSupport.NO_EVIDENCE
        assert evidence.best_subsequent is None
        assert evidence.subsequent_prints == 0

    def test_the_claim_instant_itself_never_counts_as_its_own_evidence(self) -> None:
        """The price was chosen BECAUSE it printed at that moment. Letting that print
        support the claim would make every fill self-certifying and the test vacuous."""
        market = _market([(600, SELECTION, "3.0")])
        evidence = traded_through(market, SELECTION, Decimal("3.0"),
                                  seconds_before_off=600)
        assert evidence.support is FillSupport.NO_EVIDENCE

    def test_another_selection_trading_through_proves_nothing_about_ours(self) -> None:
        """Match Odds has two runners and their prices move opposite ways. Reading the
        wrong selection's prints would report support exactly when the market moved
        against us."""
        market = _market([(600, SELECTION, "3.0"), (200, OTHER, "3.5")])
        evidence = traded_through(market, SELECTION, Decimal("3.0"),
                                  seconds_before_off=600)
        assert evidence.support is FillSupport.NO_EVIDENCE

    def test_earlier_prints_are_not_evidence_for_a_later_claim(self) -> None:
        """Trading at 3.0 an hour before we bet says nothing about whether 3.0 was still
        there when we did."""
        market = _market([(3600, SELECTION, "3.2"), (600, SELECTION, "2.8")])
        evidence = traded_through(market, SELECTION, Decimal("2.8"),
                                  seconds_before_off=600)
        assert evidence.support is FillSupport.NO_EVIDENCE

    def test_prints_after_the_off_can_never_support_a_pre_off_fill(self) -> None:
        """The reader drops in-play observations, but nothing stops a caller constructing a
        history with one. A post-off print must not rescue a pre-off claim."""
        market = _market([(600, SELECTION, "3.0"), (-30, SELECTION, "4.0")])
        evidence = traded_through(market, SELECTION, Decimal("3.0"),
                                  seconds_before_off=600)
        assert evidence.support is FillSupport.NO_EVIDENCE

    def test_a_negative_horizon_is_refused_rather_than_answered(self) -> None:
        market = _market([(600, SELECTION, "3.0")])
        with pytest.raises(InPlayRefusedError):
            traded_through(market, SELECTION, Decimal("3.0"), seconds_before_off=-1)

    def test_a_float_price_is_refused(self) -> None:
        """Money is exact. A float claim price would round its way past the comparison."""
        market = _market([(600, SELECTION, "3.0"), (300, SELECTION, "3.0")])
        with pytest.raises(TypeError):
            traded_through(market, SELECTION, 3.0,  # type: ignore[arg-type]
                           seconds_before_off=600)

    def test_an_off_ladder_claim_price_is_refused(self) -> None:
        """3.01 is not a Betfair price. A claim at one is a defect upstream, and answering
        it would hide that defect behind a plausible verdict."""
        market = _market([(600, SELECTION, "3.0"), (300, SELECTION, "3.0")])
        with pytest.raises(ValueError):
            traded_through(market, SELECTION, Decimal("3.01"), seconds_before_off=600)

    def test_support_is_monotone_in_the_claim_price(self) -> None:
        """Claiming a worse price can never turn support off: if 3.2 later traded, then a
        claim at 3.0 is supported by the same print that supports a claim at 3.2."""
        market = _market([(600, SELECTION, "3.0"), (120, SELECTION, "3.2")])
        for claim in (Decimal("2.5"), Decimal("3.0"), Decimal("3.2")):
            assert traded_through(market, SELECTION, claim,
                                  seconds_before_off=600).support is FillSupport.SUPPORTED
        assert traded_through(market, SELECTION, Decimal("3.5"),
                              seconds_before_off=600).support is FillSupport.UNSUPPORTED

    def test_the_evidence_carries_the_count_it_was_decided_on(self) -> None:
        """A verdict from one print and a verdict from forty are different verdicts, and
        the caller cannot tell them apart unless the count travels with the answer."""
        market = _market([(600, SELECTION, "3.0"), (500, SELECTION, "3.1"),
                          (400, SELECTION, "2.9"), (300, SELECTION, "3.0")])
        evidence = traded_through(market, SELECTION, Decimal("3.0"),
                                  seconds_before_off=600)
        assert evidence.subsequent_prints == 3
        assert evidence.support is FillSupport.SUPPORTED


class TestLiquidityStratum:
    def test_strata_are_ordered_and_cover_every_count(self) -> None:
        """Every non-negative print count lands in exactly one stratum, so nothing can be
        silently dropped from a stratified report."""
        seen = [stratify(n) for n in range(0, 200)]
        assert all(isinstance(s, LiquidityStratum) for s in seen)
        assert seen[0] is LiquidityStratum.SILENT

    def test_a_single_print_is_not_the_same_as_many(self) -> None:
        """One print may be one small trade. Averaging it with a heavily traded market is
        how a fragile subset disappears into a headline."""
        assert stratify(1) is not stratify(50)

    def test_stratum_never_decreases_as_prints_increase(self) -> None:
        order = list(LiquidityStratum)
        previous = 0
        for count in range(0, 500):
            current = order.index(stratify(count))
            assert current >= previous
            previous = current


class TestFillEvidenceType:
    def test_evidence_is_immutable(self) -> None:
        """A verdict that can be edited after the fact is not a verdict."""
        market = _market([(600, SELECTION, "3.0"), (300, SELECTION, "3.0")])
        evidence = traded_through(market, SELECTION, Decimal("3.0"),
                                  seconds_before_off=600)
        with pytest.raises(Exception):
            evidence.support = FillSupport.UNSUPPORTED  # type: ignore[misc]

    def test_only_supported_evidence_reports_itself_as_creditable(self) -> None:
        """The single predicate a settlement loop is allowed to branch on, so that the
        NO_EVIDENCE case cannot be quietly folded into the credited side."""
        assert FillEvidence(support=FillSupport.SUPPORTED, best_subsequent=Decimal("3.0"),
                            subsequent_prints=1).creditable
        for support in (FillSupport.UNSUPPORTED, FillSupport.NO_EVIDENCE):
            assert not FillEvidence(support=support, best_subsequent=None,
                                    subsequent_prints=0).creditable
