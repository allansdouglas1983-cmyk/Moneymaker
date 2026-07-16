"""SPEC-036: separate probability outputs (p_fundamental / p_market_info / p_combined).

Three DISTINCT runner-level probability kinds, mirroring SPEC-051's three-price separation
one layer up: ``FundamentalProbability`` (the independent model opinion, no market input),
``MarketProbability`` (a frozen versioned information price wrapped from l5's
``MarketInfoPrice`` — never labelled a model prediction: it carries a ``price_version``, not
a ``model_digest``), and ``CombinedProbability`` (the stage-two market-aware opinion). They
share no base beyond pydantic's ``BaseModel`` and no overlapping optional field that would let
one alias another, so a field typed to one kind statically and dynamically rejects an
instance of a different kind (pydantic strict mode does not coerce between sibling model
classes).

Missingness is explicit: ``RunnerProbabilities`` holds each kind as ``Optional`` plus a
mandatory non-empty reason when absent. Accessors (`fundamental()`, `market_info()`,
`combined()`) are the sanctioned read path and raise ``MissingProbabilityError`` — they never
substitute another kind's value.

Race-level normalisation (SPEC-036's "summing to 1 across active runners within tolerance")
applies per PRESENT kind: a kind is either fully present across every runner passed to
``RaceProbabilityOutputs`` or fully absent race-wide — ambiguity resolution documented in the
implementing task's final report. Partial presence is refused (``PartialPresenceError``)
rather than silently treated as present-with-gaps.

Per ADR 0012 decision 2, floats stay INSIDE the l4 fitters; the builders in this module are
the boundary where a fitter's raw float prediction becomes a Decimal probability
(``Decimal(repr(x))``, the platform's one float->Decimal idiom) before it ever leaves the
package. No LLM creates, alters, smooths or repairs any value here — every probability
wrapped by this module is a direct passthrough of an existing deterministic model or price
computation.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, model_validator

from price_contracts.prices import MarketInfoPrice

_TOLERANCE = Decimal("1e-9")


class MissingProbabilityError(Exception):
    """Raised when an absent probability kind is accessed.

    Carries the runner, the kind, and the explicit reason recorded at construction time —
    never a substituted value from another kind.
    """

    def __init__(self, runner_id: int, kind: str, reason: str) -> None:
        self.runner_id = runner_id
        self.kind = kind
        self.reason = reason
        super().__init__(f"runner {runner_id}: {kind} is absent ({reason!r})")


class ProbabilityRangeError(ValueError):
    """A probability value violates the open-unit-interval requirement."""


class RaceNormalisationError(ValueError):
    """A present probability kind does not sum to 1 across active runners within tolerance."""


class PartialPresenceError(ValueError):
    """A probability kind is present for some race runners and absent for others."""


def _check_unit_interval(value: Decimal, where: str) -> Decimal:
    if not Decimal(0) < value < Decimal(1):
        raise ProbabilityRangeError(f"{where}: probability {value!r} must be in the open interval (0, 1)")
    return value


class FundamentalProbability(BaseModel):
    """p_fundamental — the independent model opinion, no market input (SPEC-036)."""

    model_config = ConfigDict(frozen=True, strict=True)

    probability: Decimal
    model_digest: str

    @model_validator(mode="after")
    def _validate(self) -> "FundamentalProbability":
        _check_unit_interval(self.probability, "p_fundamental")
        if not self.model_digest or not self.model_digest.strip():
            raise ValueError("p_fundamental requires a non-empty generating model_digest")
        return self


class MarketProbability(BaseModel):
    """p_market_info — a frozen versioned information price, wrapped from l5's
    ``MarketInfoPrice`` (SPEC-036). NEVER labelled a model prediction: this type exposes a
    ``price_version`` (the frozen price-definition version, e.g. ``"info-price-v1"``) and has
    no ``model_digest`` field at all.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    probability: Decimal
    price_version: str

    @model_validator(mode="after")
    def _validate(self) -> "MarketProbability":
        _check_unit_interval(self.probability, "p_market_info")
        if not self.price_version or not self.price_version.strip():
            raise ValueError("p_market_info requires a non-empty price_version")
        return self


class CombinedProbability(BaseModel):
    """p_combined — the stage-two market-aware opinion (SPEC-036)."""

    model_config = ConfigDict(frozen=True, strict=True)

    probability: Decimal
    model_digest: str

    @model_validator(mode="after")
    def _validate(self) -> "CombinedProbability":
        _check_unit_interval(self.probability, "p_combined")
        if not self.model_digest or not self.model_digest.strip():
            raise ValueError("p_combined requires a non-empty generating model_digest")
        return self


class RunnerProbabilities(BaseModel):
    """One runner's optional trio of DISTINCT probability kinds (SPEC-036).

    Each kind is present XOR explicitly absent-with-a-reason; missingness never falls back to
    another kind. ``fundamental()``/``market_info()``/``combined()`` are the sanctioned read
    path.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    runner_id: int
    p_fundamental: FundamentalProbability | None = None
    p_fundamental_missing_reason: str | None = None
    p_market_info: MarketProbability | None = None
    p_market_info_missing_reason: str | None = None
    p_combined: CombinedProbability | None = None
    p_combined_missing_reason: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "RunnerProbabilities":
        if self.runner_id <= 0:
            raise ValueError(f"runner_id must be positive, got {self.runner_id}")
        for value, reason, kind in (
            (self.p_fundamental, self.p_fundamental_missing_reason, "p_fundamental"),
            (self.p_market_info, self.p_market_info_missing_reason, "p_market_info"),
            (self.p_combined, self.p_combined_missing_reason, "p_combined"),
        ):
            if value is None and (reason is None or not reason.strip()):
                raise ValueError(f"{kind} is absent but has no explicit non-empty reason")
            if value is not None and reason is not None:
                raise ValueError(f"{kind} is present; a missing_reason must not also be set")
        return self

    def fundamental(self) -> FundamentalProbability:
        if self.p_fundamental is None:
            raise MissingProbabilityError(self.runner_id, "p_fundamental", self.p_fundamental_missing_reason or "")
        return self.p_fundamental

    def market_info(self) -> MarketProbability:
        if self.p_market_info is None:
            raise MissingProbabilityError(self.runner_id, "p_market_info", self.p_market_info_missing_reason or "")
        return self.p_market_info

    def combined(self) -> CombinedProbability:
        if self.p_combined is None:
            raise MissingProbabilityError(self.runner_id, "p_combined", self.p_combined_missing_reason or "")
        return self.p_combined


class RaceProbabilityOutputs(BaseModel):
    """One race's SPEC-036 contract: the race is the unit of analysis, so normalisation is
    checked here, per present kind, across every runner passed to this race."""

    model_config = ConfigDict(frozen=True, strict=True)

    race_id: str
    runners: tuple[RunnerProbabilities, ...]

    @model_validator(mode="after")
    def _validate(self) -> "RaceProbabilityOutputs":
        if not self.race_id or self.race_id != self.race_id.strip():
            raise ValueError("race_id must be non-empty trimmed text")
        if not self.runners:
            raise ValueError(f"race {self.race_id!r}: needs at least one runner")
        runner_ids = [r.runner_id for r in self.runners]
        if len(set(runner_ids)) != len(runner_ids):
            raise ValueError(f"race {self.race_id!r}: duplicate runner ids")

        kinds: tuple[tuple[str, "type"], ...] = (
            ("p_fundamental", FundamentalProbability),
            ("p_market_info", MarketProbability),
            ("p_combined", CombinedProbability),
        )
        for kind_name, _kind_type in kinds:
            present = [getattr(r, kind_name) for r in self.runners if getattr(r, kind_name) is not None]
            n_present = len(present)
            n_total = len(self.runners)
            if 0 < n_present < n_total:
                raise PartialPresenceError(
                    f"race {self.race_id!r}: {kind_name} present for {n_present}/{n_total} runners "
                    "— a kind must be fully present or fully absent race-wide"
                )
            if n_present == n_total and n_present > 0:
                total = sum((p.probability for p in present), Decimal(0))
                if abs(total - Decimal(1)) > _TOLERANCE:
                    raise RaceNormalisationError(
                        f"race {self.race_id!r}: {kind_name} sums to {total!r}, not 1 "
                        f"(tolerance {_TOLERANCE!r})"
                    )
        return self


def build_fundamental_probabilities(
    fundamentals: Mapping[int, float], model_digest: str
) -> dict[int, FundamentalProbability]:
    """Wrap a stage-one/edge-distribution point prediction map as p_fundamental (SPEC-036).

    ``fundamentals`` are raw float outputs of an existing deterministic l4 fitter (ADR 0012
    decision 2: floats stay inside the fitter). This is the one boundary conversion to
    Decimal, via ``Decimal(repr(x))`` — the platform's shortest-repr idiom — before the value
    leaves the package as a typed probability.
    """
    return {
        runner_id: FundamentalProbability(probability=Decimal(repr(value)), model_digest=model_digest)
        for runner_id, value in fundamentals.items()
    }


def build_market_probabilities(
    prices: Mapping[int, MarketInfoPrice], price_version: str
) -> dict[int, MarketProbability]:
    """Wrap l5's ``MarketInfoPrice`` as p_market_info (SPEC-036).

    Never carries a ``model_digest`` — ``price_version`` is the frozen price-definition
    version from ``specs/prices/info-price-v1.yaml`` (or a future successor version), not a
    model lineage identifier.
    """
    return {
        runner_id: MarketProbability(probability=price.implied_probability, price_version=price_version)
        for runner_id, price in prices.items()
    }


def build_combined_probabilities(
    combined: Mapping[int, float], model_digest: str
) -> dict[int, CombinedProbability]:
    """Wrap a stage-two combiner's raw float prediction map as p_combined (SPEC-036)."""
    return {
        runner_id: CombinedProbability(probability=Decimal(repr(value)), model_digest=model_digest)
        for runner_id, value in combined.items()
    }


def assemble_race_probability_outputs(
    race_id: str,
    runner_ids: Sequence[int],
    *,
    fundamental: Mapping[int, FundamentalProbability] | None = None,
    fundamental_missing_reason: str | None = None,
    market_info: Mapping[int, MarketProbability] | None = None,
    market_info_missing_reason: str | None = None,
    combined: Mapping[int, CombinedProbability] | None = None,
    combined_missing_reason: str | None = None,
) -> RaceProbabilityOutputs:
    """Assemble one race's ``RunnerProbabilities`` set from independently-built kind maps.

    Each kind is either a full mapping over ``runner_ids`` (present for every runner) or
    ``None`` with a mandatory non-empty ``*_missing_reason`` — a partial map is refused
    explicitly rather than silently treated as presence with implicit gaps.
    """
    for name, mapping_, reason in (
        ("fundamental", fundamental, fundamental_missing_reason),
        ("market_info", market_info, market_info_missing_reason),
        ("combined", combined, combined_missing_reason),
    ):
        if mapping_ is None and (reason is None or not reason.strip()):
            raise ValueError(f"{name} is absent but no explicit non-empty reason was given")
        if mapping_ is not None:
            if reason is not None:
                raise ValueError(f"{name} is present; a missing_reason must not also be set")
            if set(mapping_) != set(runner_ids):
                raise ValueError(f"{name} map must cover exactly runner_ids, got {sorted(mapping_)}")

    runners = tuple(
        RunnerProbabilities(
            runner_id=rid,
            p_fundamental=fundamental[rid] if fundamental is not None else None,
            p_fundamental_missing_reason=None if fundamental is not None else fundamental_missing_reason,
            p_market_info=market_info[rid] if market_info is not None else None,
            p_market_info_missing_reason=None if market_info is not None else market_info_missing_reason,
            p_combined=combined[rid] if combined is not None else None,
            p_combined_missing_reason=None if combined is not None else combined_missing_reason,
        )
        for rid in runner_ids
    )
    return RaceProbabilityOutputs(race_id=race_id, runners=runners)
