"""SPEC-033: horizon-specific models — deployment refuses a horizon mismatch.

A model trained on near-final prices cannot score T−10m without distribution mismatch
(§6.4). Every fitted model pins its horizon label; every scoring entry point requires the
caller to declare the horizon it is scoring at and refuses any difference. Labels are
opaque validated text — nominal-time bands (``T-2m``) or market-state-based labels
(``pre-off-liquid``), the latter preferred by §6.4.
"""
from __future__ import annotations


class HorizonMismatch(Exception):
    """A model was asked to score at a horizon it was not trained for (SPEC-033)."""


class HorizonLabel(str):
    """Opaque, validated horizon label. Equality is exact text equality."""

    __slots__ = ()

    def __new__(cls, value: str) -> "HorizonLabel":
        if not isinstance(value, str) or not value or value != value.strip():
            raise ValueError(f"horizon label must be non-empty trimmed text, got {value!r}")
        return super().__new__(cls, value)


def require_horizon_match(model_horizon: HorizonLabel, requested: HorizonLabel) -> None:
    """Refuse a horizon mismatch (SPEC-033: refusal, not a warning)."""
    if str(model_horizon) != str(requested):
        raise HorizonMismatch(
            f"model trained at horizon {str(model_horizon)!r} may not score horizon "
            f"{str(requested)!r} (SPEC-033: deployment refuses a horizon mismatch)"
        )
