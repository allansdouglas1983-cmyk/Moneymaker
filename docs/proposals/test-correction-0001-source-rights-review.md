# Test-correction proposal 0001 — source rights review metadata (SPEC-044 / SPEC-101)

**Status:** PROPOSED — awaiting explicit founder approval. Per the standing rule, this
correction must land in its own dedicated change, never inside an ordinary
implementation task. Nothing in this proposal is implemented yet.

## Problem

`governance/output_rights.py` treats `SourceRights.rights_review_by = None` as *never
stale* (`is_stale` returns `False`), and the pinned test
`test_no_review_date_never_counts_as_stale` in
`tests/unit/governance/test_output_rights.py` locks that behaviour in. For an EXTERNAL
source, "no review date recorded" therefore means "valid forever" — a fail-open reading
of SPEC-044's "publication eligibility fails closed on missing or stale rights", flagged
by the 2026-07-16 fresh-context verifier (finding 3) and directed to a governed proposal
by the founder on the same date.

## Proposed correction

1. `SourceRights` gains two required review-provenance fields for external sources:
   `reviewed_at: date` (when the rights determination was made) and `recheck_by: date`
   (when it must be re-confirmed). `rights_review_by` is superseded by `recheck_by`
   with a recorded migration.
2. Missing review metadata FAILS CLOSED: an external source without both fields is
   ineligible for every use (internal and publication) — Gate −1 (SPEC-101) approval
   requires them present and `recheck_by` in the future.
3. `is_stale` becomes: stale iff `recheck_by <= as_of` OR either field is missing.
4. The pinned test `test_no_review_date_never_counts_as_stale` is REPLACED by tests
   asserting the fail-closed behaviour above. This is the test correction requiring
   the founder's sign-off, citing SPEC-044/SPEC-101.

## Blast radius

`governance/output_rights.py`, its unit/property tests, `docs/licensed-sources.yaml`
entries (each needs `reviewed_at`/`recheck_by`), `tools/check_licensed_sources`, and any
fixture constructing `SourceRights`. No trading or pricing module is affected.

## Approval

Approve by instructing: "test-correction 0001 approved" (optionally with amendments).
Until then, current behaviour stands and no external source is onboarded without
explicit review dates in `docs/licensed-sources.yaml` as an operational precaution.
