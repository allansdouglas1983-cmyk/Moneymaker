"""Reconciled Betfair Starting Price — grading only (SPEC-021, SPEC-095).

Reconciled BSP is known only *after* the market is reconciled, so it MUST NOT enter any
pre-off feature. It lives here, in the evidence/grading layer, and the static import-graph
check (SPEC-021, ``tools/check_import_quarantine.py``) forbids any path from ``l3_features``
to this module. As a second line of defence, values carry a class-level taint marker that the
L3 runtime guard (``l3_features.leakage``) detects **without importing this module**, so the
runtime assertion cannot itself create a forbidden import edge.

BSP joins at grading time only.
"""
from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

# Well-known taint marker. Duplicated as a plain string literal in l3_features.leakage so the
# runtime guard needs no import of this grading-only module (that import is itself forbidden).
RECONCILED_BSP_TAINT: str = "l8_evidence.reconciled_bsp:RECONCILED_BSP"


class ReconciledBSP(BaseModel):
    """A reconciled BSP for one selection. Grading-only; never a pre-off feature input."""

    model_config = ConfigDict(frozen=True)

    #: Class-level marker (not a field) read structurally by the L3 leakage guard.
    reconciled_bsp_taint: ClassVar[str] = RECONCILED_BSP_TAINT

    selection_id: int
    bsp: Decimal
