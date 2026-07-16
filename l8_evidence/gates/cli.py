"""The pinned `gate evaluate` CLI (SPEC-093, §10; contract in l8_evidence/gates/README.md).

Exit codes: PASS 0, CONTINUE 1, FAIL_HARM 2, FAIL_FUTILITY 3, evaluator error 4.
The canonical-JSON result goes to stdout; an error goes to stderr and prints no verdict.
``--as-of`` defaults to today UTC, resolved once here and echoed in the result — the
evaluation core itself never reads a clock.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from l8_evidence.gates.evaluator import EvaluatorError, evaluate
from l8_evidence.gates.experiment import load_experiment
from l8_evidence.gates.facts import load_facts_registry
from l8_evidence.gates.outcomes import GateEvaluationError, GateOutcome
from l8_evidence.gates.spec import load_gate_spec

_EXIT_CODES = {
    GateOutcome.PASS: 0,
    GateOutcome.CONTINUE: 1,
    GateOutcome.FAIL_HARM: 2,
    GateOutcome.FAIL_FUTILITY: 3,
}
_EXIT_ERROR = 4


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gate", description="Deterministic promotion-gate evaluator (SPEC-093)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    ev = subparsers.add_parser("evaluate", help="evaluate one experiment against its gate")
    ev.add_argument("--spec", required=True, type=Path, help="versioned gate spec yaml")
    ev.add_argument("--experiment", required=True, help="experiment id (<root>/<id>.yaml)")
    ev.add_argument(
        "--experiment-root",
        type=Path,
        default=Path("ledger/experiments"),
        help="directory holding experiment records (default: ledger/experiments)",
    )
    ev.add_argument("--data-manifest", required=True, help="sha256:<64 hex> of the data")
    ev.add_argument("--model-manifest", required=True, help="sha256:<64 hex> of the model")
    ev.add_argument("--facts-registry", required=True, type=Path, help="docs/facts.yaml")
    ev.add_argument("--as-of", default=None, help="ISO date; defaults to today (UTC)")
    return parser


def _resolve_as_of(raw: str | None) -> date:
    if raw is None:
        return datetime.now(timezone.utc).date()
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise EvaluatorError(f"--as-of is not a valid ISO date: {raw!r}") from exc


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        as_of = _resolve_as_of(args.as_of)
        spec = load_gate_spec(args.spec)
        record_path = args.experiment_root / f"{args.experiment}.yaml"
        if not record_path.is_file():
            raise EvaluatorError(f"experiment record not found: {record_path}")
        experiment = load_experiment(record_path)
        if experiment.experiment_id != args.experiment:
            raise EvaluatorError(
                f"experiment_id {experiment.experiment_id!r} in {record_path} does not"
                f" match the requested id {args.experiment!r}"
            )
        facts = load_facts_registry(args.facts_registry)
        result = evaluate(
            spec=spec,
            experiment=experiment,
            facts=facts,
            data_manifest=args.data_manifest,
            model_manifest=args.model_manifest,
            as_of=as_of,
        )
    except (GateEvaluationError, OSError) as exc:
        print(f"[gate] error: {exc}", file=sys.stderr)
        return _EXIT_ERROR
    print(result.canonical_json())
    return _EXIT_CODES[result.outcome]


if __name__ == "__main__":
    raise SystemExit(main())
