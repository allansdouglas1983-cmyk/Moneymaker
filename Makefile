# Local convenience mirrors of the CI verification in docs/CI-AND-TRUST.md §3.
#
# Hooks and `make` are workflow convenience and fast feedback, NOT the trust boundary —
# CI on a runner the agent cannot edit is the boundary (docs/SPECIFICATION.md §12).
# These targets are RED until tools/ and the test suites exist. That is expected.

MANIFEST := docs/spec-manifest.yaml
MONEY := l4b_fill l5_decision l5b_risk l6_broker l7_settle l8_evidence governance price_contracts sport_core
EVIDENCE := l0_raw l1_reduce l3_features
ESCAPE_HATCHES := (notimplementederror|\btodo\b|\bfixme\b|\bxxx\b|\bhack\b|\bplaceholder\b|\bstub\b|raise\s+notimplemented|\bpass\b\s*(\#.*)?$$)

.PHONY: verify mutants replay build

verify:
	uv run python tools/check_spec_coverage.py --manifest $(MANIFEST) --enforce-states active,verified
	uv run python tools/check_spec_coverage.py --manifest $(MANIFEST) --enforce-states active,verified --require-causal-declarations --require-properties-for money
	uv run python tools/check_facts_freshness.py --registry docs/facts.yaml
	uv run python -m tools.check_licensed_sources --registry docs/licensed-sources.yaml
	uv run pytest tests/unit tests/integration tests/properties tests/stateful tests/failure_injection -q
	uv run ruff check --select ARG .
	uv run pylint --disable=all --enable=W0613 $(MONEY)
	! grep -rinE '$(ESCAPE_HATCHES)' $(MONEY) --include='*.py'
	! grep -rinE '$(ESCAPE_HATCHES)' $(EVIDENCE) --include='*.py'
	uv run python tools/check_import_quarantine.py --forbid research.scraping --from l5_decision l5b_risk l6_broker
	uv run python tools/check_import_quarantine.py --forbid l8_evidence.reconciled_bsp --from l3_features
	uv run mypy --strict .

mutants:
	uv run python tools/run_mutation.py --target l8_evidence/gates l7_settle --require-kill-non-equivalent --survivors-must-be-classified
	uv run python tools/run_mutation.py --target l5b_risk --report

replay:
	uv run pytest tests/replay_regression -q

build:
	@echo "make build: no build artefact defined yet (Phase 0 scaffold). See docs/SPECIFICATION.md §12." >&2
	@exit 1
