# research — EXPLORATORY ONLY

**Spec:** SPECIFICATION.md §13 · **Requirements:** SPEC-100 (governance, active)

Exploratory analysis only. **There MUST be no import path from anything under `research/`
into `l5_decision`, `l5b_risk`, or `l6_broker`** — enforced by a static import-graph check
in CI (`tools/check_import_quarantine.py`), not by convention.

> **Status: not yet implemented.** Scaffold marker.
