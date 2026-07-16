"""SPEC-045: exportable prediction contract with independent status dimensions (ADR 0013).

Read-only analytics-consumer package. See :mod:`analytics_contracts.export_contract`.
"""
from __future__ import annotations

from analytics_contracts.export_contract import (
    CONTRACT_SCHEMA_VERSION,
    AttributionUnavailable,
    ExplanationReference,
    ExportablePrediction,
    ExportContractError,
    ForecastAvailability,
    PublicationEligibility,
    RecommendationStatus,
    RunnerProbabilityExport,
    UnavailableForecast,
    build_export,
    build_unavailable,
    display_decimal,
    map_eligibility_to_publication_status,
)

__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "AttributionUnavailable",
    "ExplanationReference",
    "ExportablePrediction",
    "ExportContractError",
    "ForecastAvailability",
    "PublicationEligibility",
    "RecommendationStatus",
    "RunnerProbabilityExport",
    "UnavailableForecast",
    "build_export",
    "build_unavailable",
    "display_decimal",
    "map_eligibility_to_publication_status",
]
