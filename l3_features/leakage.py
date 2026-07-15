"""Runtime half of the BSP-leakage guard (SPEC-021).

Reconciled BSP MUST NOT be reachable from any pre-off feature. SPEC-021 requires *two*
mechanisms: a static import-graph check (``tools/check_import_quarantine.py`` forbids
``l3_features`` reaching ``l8_evidence.reconciled_bsp``) and this runtime assertion.

The runtime guard detects a reconciled-BSP value **structurally**, by a taint marker, and
deliberately does **not** import the grading-only BSP module — importing it here would create
exactly the forbidden edge the static check exists to prevent. The marker string is kept in
sync with ``l8_evidence.reconciled_bsp.RECONCILED_BSP_TAINT``.
"""
from __future__ import annotations

# Kept identical to l8_evidence.reconciled_bsp.RECONCILED_BSP_TAINT. NOT imported from there:
# importing that module from l3_features is the forbidden edge (SPEC-021). A test asserts the
# two literals agree so they cannot silently drift apart.
_RECONCILED_BSP_TAINT = "l8_evidence.reconciled_bsp:RECONCILED_BSP"


class BSPLeakageError(RuntimeError):
    """A reconciled-BSP value reached a pre-off feature input (SPEC-021)."""


def is_reconciled_bsp(value: object) -> bool:
    """True if ``value`` carries the reconciled-BSP taint marker (class-level or instance)."""
    marker = getattr(type(value), "reconciled_bsp_taint", None)
    if marker is None:
        marker = getattr(value, "reconciled_bsp_taint", None)
    return marker == _RECONCILED_BSP_TAINT


def assert_no_bsp(value: object, *, field: str = "") -> None:
    """Reject a reconciled-BSP value used as a pre-off feature input (SPEC-021).

    Raises :class:`BSPLeakageError` if ``value`` is tainted; a no-op otherwise.
    """
    if is_reconciled_bsp(value):
        where = f" (feature {field!r})" if field else ""
        raise BSPLeakageError(
            f"reconciled BSP reached a pre-off feature{where}; BSP joins at grading only "
            "(SPEC-021)"
        )
