# tools — CI enforcement scripts

**Spec:** SPECIFICATION.md §12.3, §12.4 · **Design:** `docs/decisions/0001-verification-tooling.md`
**Criticality:** evidence/support (they enforce the gates; they are not money logic).

Deterministic scripts invoked by `.github/workflows/verify.yml` and the `Makefile`. Each has
a `main(argv) -> int` and testable pure functions; unit tests live in `tests/unit/tools/`.

| Script | Purpose | Status |
|---|---|---|
| `check_spec_coverage.py`     | active/verified SPEC-IDs have a referencing test; property test for money IDs; causal-declaration completeness; no unknown refs; no verification loss vs base | **implemented** |
| `check_facts_freshness.py`   | reject any `docs/facts.yaml` entry past its `recheck_by` (unpopulated facts pass) | **implemented** |
| `check_import_quarantine.py` | transitive static import-graph: forbid `research.scraping` from `l5_decision`/`l5b_risk`/`l6_broker` (SPEC-100) | **implemented** |
| `emit_traceability.py`       | emit the SPEC-ID → tests traceability matrix (Markdown, CI artifact) | **implemented** |
| `run_mutation.py`            | cosmic-ray on money modules; 100% non-equivalent gate mutants killed; classify survivors (`specs/mutation-survivors.yaml`) | **implemented** (ADR 0008) |

## Coverage convention
A test declares which SPEC-IDs it verifies with `@pytest.mark.spec("SPEC-050")` (function,
class, or module-level `pytestmark`). The manifest (`docs/spec-manifest.yaml`) is the
authoritative ID registry; every referenced ID must exist in it, and every enforced
`active`/`verified` ID must have ≥1 referencing test (a property test, under
`tests/properties/`, for `money` IDs).

## Expected state at bootstrap
`check_spec_coverage.py` currently reports the ~23 `active` IDs as uncovered — that is the
harness **working**: no Phase-1 implementation exists yet. `make verify` therefore stays red
until those IDs are implemented and covered. `check_facts_freshness.py` and
`check_import_quarantine.py` pass (registry unpopulated, no money code to violate the graph).
