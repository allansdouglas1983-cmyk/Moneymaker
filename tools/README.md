# tools — CI enforcement scripts

**Spec:** SPECIFICATION.md §12.3, §12.4 · **Design:** `docs/decisions/0001-verification-tooling.md`
**Criticality:** evidence/support (they enforce the gates; they are not money logic).

Deterministic scripts invoked by `.github/workflows/verify.yml` and the `Makefile`. Each has
a `main(argv) -> int` and testable pure functions; unit tests live in `tests/unit/tools/`.

| Script | Purpose | Status |
|---|---|---|
| `check_spec_coverage.py`     | active/verified SPEC-IDs have a referencing test; property test for money IDs; causal-declaration completeness; no unknown refs; no verification loss vs base | **implemented** |
| `check_facts_freshness.py`   | reject any `docs/facts.yaml` entry past its `recheck_by` (unpopulated facts pass) | **implemented** |
| `check_import_quarantine.py` | transitive static import-graph incl. literal dynamic imports; fails closed on non-literal dynamic imports and unparseable reachable files (SPEC-100; also the SPEC-021 BSP quarantine) | **implemented** (hardened, ADR 0010) |
| `check_licensed_sources.py`  | standalone Gate -1 licensing check: every `operational` source must be `permitted` with full rights (SPEC-101); run as `python -m tools.check_licensed_sources` | **implemented** (ADR 0010) |
| `emit_traceability.py`       | emit the SPEC-ID → tests traceability matrix (Markdown, CI artifact) | **implemented** |
| `run_mutation.py`            | cosmic-ray on money modules; `l8_evidence/gates` + `l7_settle` enforced (100% non-equivalent kills; survivors classified + human-approved in `specs/mutation-survivors.yaml`) | **implemented** (ADR 0008/0010) |

## Coverage convention
A test declares which SPEC-IDs it verifies with `@pytest.mark.spec("SPEC-050")` (function,
class, or module-level `pytestmark`). The manifest (`docs/spec-manifest.yaml`) is the
authoritative ID registry; every referenced ID must exist in it, and every enforced
`active`/`verified` ID must have ≥1 referencing test (a property test, under
`tests/properties/`, for `money` IDs).

## Current state
All 23 active Phase-1 SPEC-IDs are implemented and covered; every checker passes and
`make verify` is green. (At bootstrap the coverage checker deliberately reported them all
uncovered — the harness working before the implementation existed.) Mutation runs execute in
disposable git worktrees so an interrupted run cannot leave a mutant applied to the working
tree (ADR 0010).
