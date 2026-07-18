"""Reserved, quarantined home for Betfair tennis OUTCOME extraction (Stage-2A boundary).

No tennis outcome extractor exists yet, and none may exist until (a) the outcome-opening
protocol is authorised and (b) the relevant lockbox partition is opened under SPEC-092.
This module reserves the single place such extraction will live, and REFUSES until then —
the same "refuse until governed authorisation" discipline as ``l7_settle.tennis_rules``
(SPEC-084) and ``sport_core.benchmarks.selected_benchmark`` (no benchmark selected).

Its purpose is structural: it gives outcome extraction ONE named home that pre-lockbox
consumers are import-forbidden from reaching (Makefile ``verify``:
``check_import_quarantine --forbid l8_evidence.tennis_outcomes --from l3_features
l4_pricing``), mirroring the SPEC-021 ``reconciled_bsp`` quarantine. Feature builders and
price reconstructors therefore cannot even import the winner — accidental contamination is
prevented by construction, not by care.

When the outcome-opening slice lands (post-authorisation), the extraction API is designed
THERE, reads ``runner.status`` / ``settledTime`` / withdrawal fields (the OUTCOME_CONTROLLED
set in ``l8_evidence.outcome_fields``), maps them to ``l7_settle.outcomes.MarketOutcome`` /
the tennis ``TennisMatchOutcome`` vocabulary, and is reachable only at grading time. This
module intentionally commits to no such API yet.
"""
from __future__ import annotations

__all__ = ["OutcomeAccessNotAuthorisedError", "extract_match_outcome"]


class OutcomeAccessNotAuthorisedError(RuntimeError):
    """Raised by any call here. Tennis outcome access is blocked until the outcome-opening
    protocol is authorised and the lockbox partition is opened (SPEC-092). There is no
    default, no fallback, and no environment override — opening outcome access is a human,
    governed decision, never a runtime code path."""


def extract_match_outcome(*_args: object, **_kwargs: object) -> "None":  # noqa: ANN401 - reserved
    """Always refuses. The extraction API is designed in the authorised outcome-opening
    slice, not here; until then reading a tennis result is structurally impossible."""
    raise OutcomeAccessNotAuthorisedError(
        "tennis outcome extraction is not authorised: the outcome-opening protocol is not "
        "active and no lockbox partition is opened (Stage-2A; SPEC-092). This module is a "
        "reserved, import-quarantined boundary, not a working extractor."
    )
