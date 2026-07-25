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
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from tennis_edge.corpus import Match, default_vintage_root, group_by_day, load_corpus
from tennis_edge.ledger import Ledger, LedgerRow, Summary, match_key, summarise
from tennis_edge.policy import POLICY_VERSION, Status, decide, policy_digest
from tennis_edge.ratings import RatingEngine, elo_expected
from tennis_edge.refresh import latest_vintage, refresh
from tennis_edge.sackmann import available_files, load_matches
from tennis_edge.serve_stats import ServeEstimator

__all__ = ["WeeklyResult", "run", "main"]

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
            "(see tennis_edge/sackmann.py) or set TENNIS_EDGE_DATA."
        )


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


def run(
    *,
    ledger_path: Path | str,
    data_root: Path | str | None = None,
    do_refresh: bool = True,
    dry_run: bool = False,
    now_utc: dt.datetime | None = None,
    ledger_from: dt.date = LEDGER_FROM,
) -> WeeklyResult:
    """Execute one weekly cycle."""
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
    _require_serve_archive()
    estimator.queue(
        load_matches(
            families=("main", "qual_chall"), since=_ARCHIVE_FROM, require_serve_stats=True
        )
    )

    commit = _code_commit()
    digest = policy_digest()
    recorded = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh: list[LedgerRow] = []

    for day, batch in group_by_day(matches):
        estimator.advance_to(day)
        if day >= ledger_from:
            for match in sorted(batch, key=lambda m: (m.tour, m.player_a, m.player_b)):
                key = match_key(match.match_date, match.tour, match.player_a, match.player_b)
                if key in known:
                    continue
                decision = decide(match, _model_view(engine, estimator, match, day))
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
                        policy_version=POLICY_VERSION, policy_digest=digest,
                        code_commit=commit, data_vintage=vintage.vintage_id,
                        recorded_utc=recorded,
                    )
                )
        # Observed only AFTER every decision for the day has been made.
        engine.observe(batch)

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
    parser.add_argument("--ledger", default=str(Path("docs/evidence/tennis-edge/ledger.jsonl")))
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--no-refresh", action="store_true",
                        help="evaluate against the local vintage without contacting the source")
    parser.add_argument("--dry-run", action="store_true",
                        help="evaluate and report without writing to the ledger")
    parser.add_argument("--from-date", default=None,
                        help="evaluate matches on or after this ISO date (default 2024-01-01)")
    args = parser.parse_args(argv)

    result = run(
        ledger_path=args.ledger, data_root=args.data_root,
        do_refresh=not args.no_refresh, dry_run=args.dry_run,
        ledger_from=dt.date.fromisoformat(args.from_date) if args.from_date else LEDGER_FROM,
    )
    print(result.report())
    print("\nNOTE: frozen-policy out-of-sample evaluation. Results and prices arrive in the "
          "same weekly file, so this is not a prospective record and nothing here is advice.")
    if result.summary.status_counts.get(Status.RECOMMEND_A.value, 0) or \
            result.summary.status_counts.get(Status.RECOMMEND_B.value, 0):
        print("Recommendations are measured, not acted on. No stake is implied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
