# tools — CI enforcement scripts

**Spec:** SPECIFICATION.md §12.3, §12.4 · **Criticality:** evidence/support (they enforce the gates)

Deterministic scripts invoked by `.github/workflows/verify.yml` and the `Makefile`. **None
are implemented yet** — CI will fail red at these steps until they exist. Each should be a
small, auditable, deterministic program.

Referenced by CI (see `docs/CI-AND-TRUST.md` §3):

| Script | Purpose |
|---|---|
| `check_spec_coverage.py`     | active/verified SPEC-IDs have passing verification; causal declarations + property coverage for money IDs; no verification regressions |
| `check_facts_freshness.py`   | reject any `docs/facts.yaml` entry past its `recheck_by` |
| `check_import_quarantine.py` | forbid `research.scraping` imports from `l5_decision`/`l5b_risk`/`l6_broker` |
| `run_mutation.py`            | cosmic-ray on money modules; 100% non-equivalent gate mutants killed; classify survivors |
| `emit_traceability.py`       | emit the SPEC-ID → tests traceability matrix artifact |

> **Status: not yet implemented.** Natural next spec slice. Build with tests first.
