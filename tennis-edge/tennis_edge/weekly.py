"""The weekly job: refresh, evaluate every unseen match, append, report.

Ordering is the whole safety property. State is rebuilt strictly forward through the corpus,
and every match is decided from state that has observed only *earlier* days. The rating
engine and serve estimator are both day-batched, so a result cannot inform a decision made
the same day either.

The job is idempotent by construction: matches already in the ledger are skipped, so a run
that dies halfway, or a Routine that fires twice, changes nothing on the second pass.

Run with ``python -m tennis_edge.weekly`` (add ``--dry-run`` to evaluate without writing).
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from tennis_edge.archive import restore as restore_archive
from tennis_edge.corpus import Match, default_vintage_root, group_by_day, load_corpus
from tennis_edge.ledger import Ledger, LedgerRow, Summary, match_key, summarise
from tennis_edge.policy import (
    DEVIG_METHOD,
    POLICY_VERSION,
    Decision,
    Status,
    _reference_price,
    decide,
    policy_digest,
)
from tennis_edge.policy_v2 import POLICY_VERSION as POLICY_VERSION_V2
from tennis_edge.policy_v2 import decide_v2, policy_digest_v2
from tennis_edge.pyramid import PyramidRatings
from tennis_edge.residual_model import ResidualModel, load_model
from tennis_edge.ratings import RatingEngine, elo_expected
from tennis_edge.refresh import latest_vintage, refresh
from tennis_edge.sackmann import available_files, load_matches
from tennis_edge.serve_stats import ServeEstimator

__all__ = ["DEFAULT_LEDGERS", "WeeklyResult", "resolve_ledger_path", "run", "main"]

#: One ledger per policy vintage, never a shared file.
#:
#: Two frozen rules now exist and their records must not merge. A ledger is only worth
#: keeping because every row can be traced to the exact rule that produced it, and mixing
#: vintages under one path destroys that even though each row still carries its own version
#: field — the *file* stops meaning anything, and the summary at the bottom of a run becomes
#: an average over two different policies. The path names the vintage so the separation is
#: visible in a directory listing rather than only in the rows.
DEFAULT_LEDGERS = {
    POLICY_VERSION: "docs/evidence/tennis-edge/ledger.jsonl",
    POLICY_VERSION_V2: "docs/evidence/tennis-edge/ledger-v2.jsonl",
}


def is_in_sample(match_date: dt.date, *, trained_through: dt.date | None) -> bool:
    """True when a match was inside the frozen model's training window.

    v1 has no model and therefore no boundary, so backfilling its ledger over history stays
    legitimate — the rule genuinely predates the data. v2's model was fitted *through* a
    date, so every match at or before it is in-sample, and scoring one would put a number in
    the ledger that looks prospective and is not.

    This is why a v2 ledger starts empty and fills from the next refresh onward. That is the
    correct behaviour and not a defect: a prospective record has to begin at the moment the
    rule was frozen, not at the moment someone decided to look.
    """
    return trained_through is not None and match_date <= trained_through


def resolve_ledger_path(policy_version: str, explicit: str | None) -> Path:
    """The ledger this run should write to, refusing a policy it does not know.

    An unknown version is refused rather than defaulted, because defaulting would write
    decisions from an unregistered rule into a registered rule's file.
    """
    if policy_version not in DEFAULT_LEDGERS:
        raise ValueError(
            f"unknown policy {policy_version!r}; registered: {sorted(DEFAULT_LEDGERS)}"
        )
    return Path(explicit) if explicit else Path(DEFAULT_LEDGERS[policy_version])

_ARCHIVE_FROM = dt.date(2003, 1, 1)
_MIN_SERVE_POINTS = 300.0

#: Matches before this are corpus history used to build state, not rows to evaluate. The
#: ledger starts here so it stays a readable record rather than a re-dump of 25 years.
LEDGER_FROM = dt.date(2024, 1, 1)


@dataclass(frozen=True)
class WeeklyResult:
    """What one run did."""

    vintage_id: str
    refreshed: bool
    evaluated: int
    appended: int
    summary: Summary
    dry_run: bool

    def report(self) -> str:
        head = "DRY RUN — nothing written" if self.dry_run else f"appended {self.appended:,}"
        return (
            f"vintage {self.vintage_id} ({'refreshed' if self.refreshed else 'unchanged'})\n"
            f"evaluated {self.evaluated:,} matches not previously seen; {head}\n"
            + self.summary.report()
        )


def _code_commit() -> str:
    """The commit the policy is running from — the ledger's integrity anchor."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False,
            cwd=Path(__file__).resolve().parent.parent,
        )
        return result.stdout.strip() or "unknown"
    except OSError:  # pragma: no cover - git absent is not worth failing a run over
        return "unknown"


def _require_serve_archive() -> None:
    """Refuse to run without the serve archive, rather than quietly changing architecture.

    :func:`_model_view` degrades to the rating blend alone when serve statistics are missing
    for a pairing, which is correct for an individual match. But if the whole archive is
    absent — a fresh container, an unset ``TENNIS_EDGE_DATA``, a half-restored corpus — then
    *every* row would be priced by a different model than the one the policy was frozen
    against, and the ledger would record that under the same policy digest. Silently
    substituting one architecture for another is exactly the failure the digest exists to
    prevent, so this stops instead.

    The archive is large and lives outside the repository, so its absence is a routine
    environment problem, not an exotic one.
    """
    files = available_files(families=("main", "qual_chall"))
    if not files:
        raise RuntimeError(
            "no Sackmann match files found: the serve archive is missing, so the point "
            "model could not contribute to any decision. Refusing rather than recording a "
            "rating-only ledger under the point-model policy digest. Restore the archive "
            "with `python -m tennis_edge.archive` or set TENNIS_EDGE_DATA."
        )


def _logit(p: float) -> float:
    clipped = min(max(p, 1e-12), 1.0 - 1e-12)
    return math.log(clipped / (1.0 - clipped))


def _model_view(
    engine: RatingEngine, estimator: ServeEstimator, match: Match, day: dt.date
) -> float | None:
    """The model's probability for player A, or None when it cannot price the match.

    Where serve statistics are available the point model and the rating blend are averaged
    in logit space; otherwise the rating blend stands alone. Neither is trusted on its own —
    the policy shrinks whatever comes back hard toward the market.
    """
    import math

    elo = elo_expected(
        engine.blended(match.tour, match.player_a, match.surface),
        engine.blended(match.tour, match.player_b, match.surface),
    )
    if engine.matches_played(match.tour, match.player_a) < 5:
        return None
    if engine.matches_played(match.tour, match.player_b) < 5:
        return None
    estimate = estimator.estimate(match.tour, match.player_a, match.player_b, day)
    if estimate is None or estimate.coverage < _MIN_SERVE_POINTS:
        return elo
    point = estimate.match_probability(best_of=match.best_of)

    def logit(p: float) -> float:
        clipped = min(max(p, 1e-9), 1.0 - 1e-9)
        return math.log(clipped / (1.0 - clipped))

    return 1.0 / (1.0 + math.exp(-0.5 * (logit(elo) + logit(point))))


def _decide_residual(
    match: Match, engine: RatingEngine, estimator: ServeEstimator,
    pyramid: PyramidRatings, day: dt.date, model: ResidualModel,
) -> Decision:
    """Price one match under v2 and express it in the ledger's decision shape.

    The features are built by exactly the same expressions as
    :mod:`tennis_edge.residual_features`, from state advanced the same way. That duplication
    is deliberate and narrow: the builder there works over a whole corpus at once, this needs
    a single match, and the alternative — a predictor whose features came from a different
    code path than the harness that validated it — is an untested model wearing a tested
    one's confidence interval.

    ``blended_probability_a`` carries the model's corrected probability, because under v2
    that *is* the answer rather than a blend of two candidates.
    """
    from tennis_edge.backtest import market_probability
    from tennis_edge.pyramid import pyramid_features

    reference = _reference_price(match)
    book = None if reference is None else reference[0]
    pair = None if reference is None else reference[1]
    market = None if book is None else market_probability(match, book=book,
                                                          method=DEVIG_METHOD)
    features: dict[str, float] = {}
    if market is not None:
        tour, a, b = match.tour, match.player_a, match.player_b
        if (engine.matches_played(tour, a) >= 5
                and engine.matches_played(tour, b) >= 5):
            elo = elo_expected(engine.blended(tour, a, match.surface),
                               engine.blended(tour, b, match.surface))
            features = {
                "elo_residual": _logit(elo) - _logit(market),
                "surface_elo_gap": (engine.surface_elo(tour, a, match.surface)
                                    - engine.surface_elo(tour, b, match.surface)) / 400.0,
                "weighted_elo_gap": (engine.weighted_elo(tour, a)
                                     - engine.weighted_elo(tour, b)) / 400.0,
                "rank_gap": (math.log1p(match.rank_b or 500)
                             - math.log1p(match.rank_a or 500)),
            }
            estimate = estimator.estimate(tour, a, b, day)
            if estimate is not None and estimate.coverage >= _MIN_SERVE_POINTS:
                point = estimate.match_probability(best_of=match.best_of)
                features["point_model_residual"] = _logit(point) - _logit(market)
            features.update(pyramid_features(pyramid, tour, a, b, day, match.surface))

    verdict = decide_v2(
        market_probability_a=market, features=features,
        odds_a=float(pair[0]) if pair else None,
        odds_b=float(pair[1]) if pair else None,
        model=model,
    )
    return Decision(
        status=Status(verdict.status.value), book=book,
        market_probability_a=verdict.market_probability_a,
        model_probability_a=verdict.model_probability_a,
        blended_probability_a=verdict.model_probability_a,
        quoted_odds=verdict.quoted_odds, side=verdict.side,
        expected_value=max(verdict.edge_a, verdict.edge_b), reason=verdict.reason,
    )


def run(
    *,
    ledger_path: Path | str,
    data_root: Path | str | None = None,
    do_refresh: bool = True,
    do_restore: bool = True,
    dry_run: bool = False,
    now_utc: dt.datetime | None = None,
    ledger_from: dt.date = LEDGER_FROM,
    policy_version: str = POLICY_VERSION,
    model_path: Path | str | None = None,
) -> WeeklyResult:
    """Execute one weekly cycle under the named policy vintage.

    ``policy_version`` selects the frozen rule. v2 additionally needs the frozen model
    artefact, because its digest folds the model in — a v2 run without one would be a
    different rule wearing v2's label, which is precisely what the digest exists to prevent.
    """
    residual_model = None
    if policy_version == POLICY_VERSION_V2:
        if model_path is None:
            raise RuntimeError(
                "policy v2 needs a frozen model (--model). Its digest includes the "
                "coefficients, so running without one would record decisions under a "
                "digest that does not describe the rule that made them."
            )
        residual_model = load_model(model_path)
    root = Path(data_root) if data_root is not None else default_vintage_root()
    now = now_utc or dt.datetime.now(dt.timezone.utc)

    refreshed = False
    if do_refresh:
        outcome = refresh(root, now_utc=now)
        refreshed = outcome.changed
        print(outcome.report(), file=sys.stderr)
    vintage = latest_vintage(root)
    if vintage is None:
        raise RuntimeError(f"no Tennis-Data vintage under {root}")

    matches, stats = load_corpus(vintage.root)
    print(stats.summary(), file=sys.stderr)

    ledger = Ledger(ledger_path)
    known = ledger.keys()
    engine = RatingEngine()
    estimator = ServeEstimator()
    if do_restore:
        print(restore_archive().report(), file=sys.stderr)
    _require_serve_archive()
    estimator.queue(
        load_matches(
            families=("main", "qual_chall"), since=_ARCHIVE_FROM, require_serve_stats=True
        )
    )

    pyramid = PyramidRatings()
    if residual_model is not None:
        pyramid.queue(load_matches(families=("main", "qual_chall", "futures"),
                                   since=_ARCHIVE_FROM))

    commit = _code_commit()
    digest = (policy_digest() if residual_model is None
              else policy_digest_v2(residual_model))
    recorded = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    trained_through = None if residual_model is None else residual_model.trained_through
    in_sample = 0
    fresh: list[LedgerRow] = []

    for day, batch in group_by_day(matches):
        estimator.advance_to(day)
        if residual_model is not None:
            pyramid.advance_to(day)
        if day >= ledger_from:
            for match in sorted(batch, key=lambda m: (m.tour, m.player_a, m.player_b)):
                key = match_key(match.match_date, match.tour, match.player_a, match.player_b)
                if key in known:
                    continue
                if is_in_sample(match.match_date, trained_through=trained_through):
                    in_sample += 1
                    continue
                decision = (
                    decide(match, _model_view(engine, estimator, match, day))
                    if residual_model is None
                    else _decide_residual(match, engine, estimator, pyramid, day,
                                          residual_model)
                )
                fresh.append(
                    LedgerRow(
                        match_key=key, match_date=match.match_date.isoformat(),
                        tour=match.tour, player_a=match.player_a, player_b=match.player_b,
                        tier=match.tier, surface=match.surface,
                        status=decision.status.value, book=decision.book,
                        market_probability_a=decision.market_probability_a,
                        model_probability_a=decision.model_probability_a,
                        blended_probability_a=decision.blended_probability_a,
                        quoted_odds=decision.quoted_odds, side=decision.side,
                        expected_value=decision.expected_value, reason=decision.reason,
                        winner_is_a=match.winner_is_a,
                        policy_version=policy_version, policy_digest=digest,
                        code_commit=commit, data_vintage=vintage.vintage_id,
                        recorded_utc=recorded,
                    )
                )
        # Observed only AFTER every decision for the day has been made.
        engine.observe(batch)

    if in_sample:
        print(f"skipped {in_sample:,} matches inside the model's training window "
              f"(through {trained_through}) — those are in-sample and would not be "
              f"evidence", file=sys.stderr)
    appended = 0 if dry_run else ledger.append(fresh)
    all_rows = list(ledger.rows()) if not dry_run else [*ledger.rows(), *fresh]
    return WeeklyResult(
        vintage_id=vintage.vintage_id, refreshed=refreshed, evaluated=len(fresh),
        appended=appended, summary=summarise(all_rows), dry_run=dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Frozen-policy out-of-sample evaluation over newly published matches. "
                    "This is not a tipping service and issues no betting advice."
    )
    parser.add_argument("--policy", default=POLICY_VERSION,
                        choices=sorted(DEFAULT_LEDGERS),
                        help="which frozen vintage to run; each writes its own ledger")
    parser.add_argument("--model", default="artifacts/residual-model.json",
                        help="frozen model artefact, required by policy v2")
    parser.add_argument("--ledger", default=None,
                        help="override the policy's default ledger path")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--no-refresh", action="store_true",
                        help="evaluate against the local vintage without contacting the source")
    parser.add_argument("--no-archive-restore", action="store_true",
                        help="skip the Sackmann archive restore (it is a no-op when the "
                             "local corpus already verifies)")
    parser.add_argument("--dry-run", action="store_true",
                        help="evaluate and report without writing to the ledger")
    parser.add_argument("--from-date", default=None,
                        help="evaluate matches on or after this ISO date (default 2024-01-01)")
    args = parser.parse_args(argv)

    result = run(
        ledger_path=resolve_ledger_path(args.policy, args.ledger),
        data_root=args.data_root,
        do_refresh=not args.no_refresh, do_restore=not args.no_archive_restore,
        dry_run=args.dry_run,
        ledger_from=dt.date.fromisoformat(args.from_date) if args.from_date else LEDGER_FROM,
        policy_version=args.policy,
        model_path=args.model if args.policy == POLICY_VERSION_V2 else None,
    )
    print(f"policy {args.policy}")
    print(result.report())
    print("\nNOTE: frozen-policy out-of-sample evaluation. Results and prices arrive in the "
          "same weekly file, so this is not a prospective record and nothing here is advice.")
    if result.summary.status_counts.get(Status.RECOMMEND_A.value, 0) or \
            result.summary.status_counts.get(Status.RECOMMEND_B.value, 0):
        print("Recommendations are measured, not acted on. No stake is implied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
