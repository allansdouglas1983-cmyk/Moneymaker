"""ADR 0017 S5 — probability + model interfaces (Phases 4-5): CONTRACTS ONLY.

Every class in this module is a ``typing.Protocol``. There is no implementation, no
estimate, no numeric default, and no model here — that is the point: Phase 4/5 of ADR
0017 authorise the SHAPE of the seam, never an instance of it. Constructing a concrete
provider or model without an implementation is a typed refusal by omission (there is
nothing to construct), never a silent stub returning a placeholder number.

All protocols are ``@runtime_checkable`` so ``isinstance(obj, SomeProtocol)`` performs a
structural check (method/property presence) against a candidate implementation supplied
by a LATER, separately-governed slice. ``runtime_checkable`` verifies structure only, not
signatures or return-type correctness — the human/CI review of a concrete implementation
against its SPEC-ID remains the substantive gate (CLAUDE.md "Verify before claiming
done"); this module's job stops at the shape of the seam.

Binding invariants, restated on every protocol below because each is independently
reviewable:

* **Deterministic.** Same inputs -> byte-/value-identical outputs. No hidden clock, no
  hidden randomness (an ensemble's random seed, if any, is a versioned, declared input of
  the concrete implementation — never of the contract).
* **No LLM may implement or back any of these.** CLAUDE.md rule 3: an LLM never estimates
  a probability, prices a bet, or sizes a stake. A concrete class satisfying one of these
  protocols is deterministic tested code, or it does not satisfy the protocol.
* **Versioned identity is mandatory.** Every protocol exposes an explicit, non-optional
  identity surface (a provider's ``price_version``/model-style ``model_id`` +
  ``model_version``, or a feature generator's ``generator_id`` + ``generator_version``) so
  every output can be traced to the exact declaration that produced it (SPEC-024,
  SPEC-036, SPEC-037 lineage fields all key off this).
* **Knowledge-time discipline on all inputs.** Every input that could carry information is
  either an existing knowledge-time-guarded type (:class:`~l3_features.feature_set.Feature`
  / ``FeatureSet`` refuse construction without provable pre-off knowability, SPEC-020/022/
  023) or an explicit ``as_of`` decision-time parameter a concrete implementation must
  honour. A protocol method signature does not by itself enforce this at the type level —
  the concrete implementation is reviewed against SPEC-020 the same as any other money/
  evidence module; this module supplies the seam through which that discipline is
  threaded, not the enforcement itself.

Reused platform types only — no new domain vocabulary is invented here:

* :class:`~l4_pricing.races.Race` / ``RunnerRow`` / ``FeatureSchema`` (SPEC-030 choice-set
  input contracts; the audit classifies ``races.py`` naming as racing-flavoured but
  structurally sport-agnostic — reused as-is, renames are ADR 0017 slice S9).
* :class:`~l4_pricing.probability_outputs.FundamentalProbability` / ``MarketProbability``
  / ``CombinedProbability`` / ``RaceProbabilityOutputs`` (SPEC-036 — the audit classifies
  ``RaceProbabilityOutputs`` as a naming-only racing coupling; reused as-is per this
  slice's brief, a rename is a later slice's concern, not this one's).
* :class:`~l3_features.feature_set.FeatureSet` (SPEC-020/023/024 — the knowledge-time- and
  leakage-guarded feature container; ``FeatureGenerator`` returns this type specifically
  because a ``FeatureSet`` cannot be minted without its guards already having run).

Uncertainty-bearing seams (``UncertaintyProvider``, ``BayesianModel``, ``EnsembleModel``)
live in :mod:`l4_pricing.interfaces`, NOT here: they return SPEC-034's
``WinProbabilityDistribution``, whose sole sanctioned exit is the decision-layer typed
lower bound — the type reaches ``l5_decision`` by construction, and ``sport_core`` sits
on the ADR 0013 read-only analytics boundary that must never reach ``l5_decision``.
Seams that return distributions are pricing-layer contracts.

Tennis-flavoured seams (``SurfaceRatingProvider``, ``FitnessSignalProvider``,
``ServeStrengthProvider``, ``ReturnStrengthProvider``) are declared here because ADR 0017
Phase 5 named them alongside the generic seam, but they are SPORT-ADAPTER-LEVEL concerns
(no football, horse-racing or binary-market analogue) exposed through the generic
:class:`FeatureGenerator` seam rather than first-class Core abstractions. Flagged in this
slice's report for the ``sport_tennis`` owner to reconsider relocating them there — no
file in ``sport_tennis/`` is touched by this slice.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Mapping, Protocol, runtime_checkable

from l3_features.feature_set import FeatureSet
from l4_pricing.probability_outputs import (
    CombinedProbability,
    FundamentalProbability,
    MarketProbability,
    RaceProbabilityOutputs,
)
from l4_pricing.races import FeatureSchema, Race

__all__ = [
    "FundamentalProbabilityProvider",
    "MarketProbabilityProvider",
    "CombinedProbabilityProvider",
    "CalibrationProvider",
    "FeatureGenerator",
    "RankingProvider",
    "SurfaceRatingProvider",
    "FitnessSignalProvider",
    "ServeStrengthProvider",
    "ReturnStrengthProvider",
    "SurfaceEloModel",
    "WeightedEloModel",
    "BradleyTerryModel",
    "RegularisedLogisticModel",
    "GradientBoostingModel",
    "MarketCombinationModel",
]


# --------------------------------------------------------------------------------------
# Generic probability-provider seams (ADR 0017 Phase 4). Every one of these must make
# sense unchanged for football Match Odds (N-way, N>=2) and a binary financial prediction
# market (N==2) — the founder's design test — since they take a generic ``Race`` (one
# mutually exclusive choice set) and return generic runner-keyed probability wrappers.
# --------------------------------------------------------------------------------------


@runtime_checkable
class FundamentalProbabilityProvider(Protocol):
    """Produces p_fundamental for every active runner in a race — SPEC-036's independent
    model opinion, with NO market input reachable from this seam.

    Deterministic: the same ``race`` (and, transitively, the same ``as_of`` decision time
    baked into its already knowledge-time-guarded ``RunnerRow`` features) always yields the
    identical probability set. No LLM may implement or back this seam — CLAUDE.md rule 3.
    Versioned identity is mandatory: every output must be traceable to the exact
    ``model_id``/``model_version`` that produced it. Knowledge-time discipline binds every
    input feature already, upstream of this seam, via ``Race``'s ``RunnerRow`` contract.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def predict(self, race: Race, *, as_of: datetime) -> Mapping[int, FundamentalProbability]: ...


@runtime_checkable
class MarketProbabilityProvider(Protocol):
    """Produces p_market_info for every active runner — SPEC-036's frozen versioned
    information price, wrapped from the exchange's own live prices. NEVER a model
    prediction: identity is a ``price_version`` (a frozen price-definition version, e.g.
    ``specs/prices/info-price-v1.yaml``), never a ``model_id``/``model_version`` pair —
    the absence of that pair is itself part of the contract (SPEC-036: p_market_info is
    never labelled a model prediction).

    Deterministic: the same executable market state at ``as_of`` always yields the
    identical wrapped price. No LLM may implement or back this seam. Knowledge-time
    discipline: ``as_of`` must be strictly pre-off for any pre-off consumer; this seam
    does not itself enforce that boundary — the concrete implementation is reviewed
    against SPEC-020/022 as any other feature-adjacent code is.
    """

    @property
    def price_version(self) -> str: ...

    def price(self, race: Race, *, as_of: datetime) -> Mapping[int, MarketProbability]: ...


@runtime_checkable
class CombinedProbabilityProvider(Protocol):
    """Produces p_combined for every active runner — SPEC-032/036's stage-two,
    market-aware opinion combining an out-of-fold fundamental with a market-info price.

    Deterministic given its inputs. No LLM may implement or back this seam. Versioned
    identity mandatory via ``model_id``/``model_version``. Knowledge-time discipline: both
    input mappings are themselves knowledge-time-guarded upstream (SPEC-031's strict
    out-of-fold requirement on the fundamental input); this seam consumes, never
    re-derives, that guarantee.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def combine(
        self,
        race: Race,
        fundamental: Mapping[int, FundamentalProbability],
        market: Mapping[int, MarketProbability],
    ) -> Mapping[int, CombinedProbability]: ...


@runtime_checkable
class CalibrationProvider(Protocol):
    """Applies a versioned calibration mapping to an already-assembled race probability
    output — SPEC-097's "any post-hoc calibration MUST renormalise across each race".

    Deterministic: the same ``RaceProbabilityOutputs`` and calibration identity always
    yield the identical calibrated output. No LLM may implement or back this seam.
    Versioned identity mandatory via ``model_id``/``model_version`` (a calibration mapping
    is itself a fitted, versioned artefact). The returned value is a full
    ``RaceProbabilityOutputs`` — its own per-race-sums-to-1 validator is therefore the
    structural proof that renormalisation happened, not a separate claim.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def calibrate(self, race: RaceProbabilityOutputs) -> RaceProbabilityOutputs: ...


@runtime_checkable
class FeatureGenerator(Protocol):
    """Generates a knowledge-time-guarded ``FeatureSet`` for a race as of a decision time —
    the generic seam through which every sport-adapter-level signal (tennis serve
    strength, a football team's rolling form, a market's own microstructure features)
    must pass; the Core never depends on a sport-specific feature type directly.

    Deterministic: the same ``race``/``as_of`` pair always yields byte-identical features
    (SPEC-024's ``feature_set_hash`` reproducibility). No LLM may implement or back this
    seam — CLAUDE.md rule 3 and SPEC-039 both forbid an LLM inventing or repairing a
    feature value. Versioned identity mandatory via ``generator_id``/``generator_version``.
    Knowledge-time discipline is structural here, not merely documented: the returned
    ``FeatureSet`` is composed of ``Feature`` instances, and ``Feature`` cannot be
    constructed without a ``FeatureBuildContext`` proving pre-off knowability
    (SPEC-020/022/023) — a non-conforming generator cannot silently skip the guard because
    the return type itself refuses to exist unguarded.
    """

    @property
    def generator_id(self) -> str: ...

    @property
    def generator_version(self) -> str: ...

    def generate(self, race: Race, *, as_of: datetime) -> FeatureSet: ...


@runtime_checkable
class RankingProvider(Protocol):
    """Produces a race-normalised ranking score per active runner — the SPEC-035 seam a
    boosting/ranking model must pass through. A raw LambdaRank-style score is explicitly
    NOT a probability (SPEC-035): this seam's contract is the score itself; turning scores
    into probabilities is the grouped softmax/Plackett-Luce responsibility of a
    ``FundamentalProbabilityProvider`` or ``CombinedProbabilityProvider`` built on top of
    it, never an implicit softmax buried inside this seam.

    Deterministic given the declared model artefact. No LLM may implement or back this
    seam. Versioned identity mandatory via ``model_id``/``model_version``. Knowledge-time
    discipline inherited from ``race``'s already-guarded features.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def rank_scores(self, race: Race, *, as_of: datetime) -> Mapping[int, Decimal]: ...


# --------------------------------------------------------------------------------------
# Tennis-flavoured providers — declared per ADR 0017 Phase 5's brief, but these are
# adapter-level: a football Match Odds market or a binary financial market has no serve,
# no surface, no player fitness. They exist as instances of the generic FeatureGenerator
# seam above, never as a Core abstraction a sport-agnostic caller depends on directly.
# Report flag: the sport_tennis owner may prefer these declared in sport_tennis/ instead
# of sport_core/ for exactly that reason — left here only because this slice's brief
# places them in this file, not because sport_core should depend on tennis vocabulary.
# --------------------------------------------------------------------------------------


@runtime_checkable
class SurfaceRatingProvider(Protocol):
    """Sport-adapter-level: a player's surface-conditioned rating as of a decision time.

    Not a generic Core seam — no football or binary-market analogue exists; concrete
    implementations are exposed to the Core only through ``FeatureGenerator``. Deterministic
    given the declared rating artefact. No LLM may implement or back this seam. Versioned
    identity mandatory via ``model_id``/``model_version``. Knowledge-time discipline via the
    mandatory ``as_of`` parameter — a concrete implementation must not read information
    published after it.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def rating(self, player_id: int, surface: str, *, as_of: datetime) -> Decimal: ...


@runtime_checkable
class FitnessSignalProvider(Protocol):
    """Sport-adapter-level: a player's fitness/fatigue/injury signal as of a decision time.

    Not a generic Core seam. Deterministic given the declared signal artefact. No LLM may
    implement or back this seam. Versioned identity mandatory via ``model_id``/
    ``model_version``. Knowledge-time discipline via the mandatory ``as_of`` parameter.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def signal(self, player_id: int, *, as_of: datetime) -> Decimal: ...


@runtime_checkable
class ServeStrengthProvider(Protocol):
    """Sport-adapter-level: a player's surface-conditioned serve-strength signal.

    Not a generic Core seam — flagged for possible relocation to ``sport_tennis``.
    Deterministic given the declared signal artefact. No LLM may implement or back this
    seam. Versioned identity mandatory via ``model_id``/``model_version``. Knowledge-time
    discipline via the mandatory ``as_of`` parameter.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def serve_strength(self, player_id: int, surface: str, *, as_of: datetime) -> Decimal: ...


@runtime_checkable
class ReturnStrengthProvider(Protocol):
    """Sport-adapter-level: a player's surface-conditioned return-strength signal.

    Not a generic Core seam — flagged for possible relocation to ``sport_tennis``.
    Deterministic given the declared signal artefact. No LLM may implement or back this
    seam. Versioned identity mandatory via ``model_id``/``model_version``. Knowledge-time
    discipline via the mandatory ``as_of`` parameter.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def return_strength(self, player_id: int, surface: str, *, as_of: datetime) -> Decimal: ...


# --------------------------------------------------------------------------------------
# Named MODEL CONTRACTS (ADR 0017 Phase 5). Each names a future model family the founder's
# program specifically called out; no model exists yet anywhere in the platform. Every
# one requires a versioned model_id + model_version — the model-identity requirement the
# platform's lineage fields (SPEC-024, SPEC-036, SPEC-037) key off.
# --------------------------------------------------------------------------------------


@runtime_checkable
class SurfaceEloModel(Protocol):
    """A future surface-conditioned Elo rating system. Deterministic given its declared
    update rule and rating history. No LLM may implement or back this model. Versioned
    identity mandatory via ``model_id``/``model_version``. Knowledge-time discipline via
    the mandatory ``as_of`` parameter on every rating query.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def rating(self, player_id: int, surface: str, *, as_of: datetime) -> Decimal: ...


@runtime_checkable
class WeightedEloModel(Protocol):
    """A future Elo variant with declared, versioned per-match/recency weighting.
    Deterministic given its declared weighting scheme and rating history. No LLM may
    implement or back this model. Versioned identity mandatory via ``model_id``/
    ``model_version``. Knowledge-time discipline via the mandatory ``as_of`` parameter.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def rating(self, player_id: int, *, as_of: datetime) -> Decimal: ...


@runtime_checkable
class BradleyTerryModel(Protocol):
    """A future Bradley-Terry choice model over a race's active runners (the pairwise
    special case for N==2, natively general for N>2 per the audit's conditional-logit
    note). Deterministic given its declared fitted parameters. No LLM may implement or
    back this model. Versioned identity mandatory via ``model_id``/``model_version``.
    Knowledge-time discipline inherited from ``race``'s already-guarded features.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def win_probability(self, race: Race, *, as_of: datetime) -> Mapping[int, FundamentalProbability]: ...


@runtime_checkable
class RegularisedLogisticModel(Protocol):
    """A future regularised logistic-regression choice model, fitted against a canonical,
    versioned ``FeatureSchema`` (SPEC-030). Deterministic given its declared coefficients
    and schema. No LLM may implement or back this model. Versioned identity mandatory via
    ``model_id``/``model_version``. Knowledge-time discipline inherited from ``race``'s
    already-guarded features; ``feature_schema`` fixes exactly which named, ordered
    features the model consumes.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    @property
    def feature_schema(self) -> FeatureSchema: ...

    def win_probability(self, race: Race, *, as_of: datetime) -> Mapping[int, FundamentalProbability]: ...


@runtime_checkable
class GradientBoostingModel(Protocol):
    """Future marker: a gradient-boosting choice model. SPEC-035 binds any concrete
    implementation: ranking scores must not be softmaxed and called probabilities — a
    conforming implementation trains a grouped softmax/cross-entropy objective or
    Plackett-Luce, validated on race-level proper scores, not a bare LambdaRank objective.
    Deterministic given its declared trees/objective. No LLM may implement or back this
    model. Versioned identity mandatory via ``model_id``/``model_version``. Knowledge-time
    discipline inherited from ``race``'s already-guarded features. Design of the concrete
    objective is explicitly future work — this marker fixes only the seam.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def win_probability(self, race: Race, *, as_of: datetime) -> Mapping[int, FundamentalProbability]: ...


@runtime_checkable
class MarketCombinationModel(Protocol):
    """Future marker naming SPEC-032's stage-two market-combination family as a versioned
    model contract in its own right (distinct from the generic
    ``CombinedProbabilityProvider`` seam, which any concrete stage-two implementation,
    including this one, must also satisfy). Deterministic given its declared combination
    parameters (e.g. SPEC-032's alpha/beta). No LLM may implement or back this model.
    Versioned identity mandatory via ``model_id``/``model_version``. Knowledge-time
    discipline inherited from both input mappings' own upstream guarantees.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def combine(
        self,
        race: Race,
        fundamental: Mapping[int, FundamentalProbability],
        market: Mapping[int, MarketProbability],
    ) -> Mapping[int, CombinedProbability]: ...
