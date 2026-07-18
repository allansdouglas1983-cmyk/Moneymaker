"""Governed competitor-identity bridge (founder directive 2026-07-18 §5).

Tennis-Data record → provider-specific source identity → internal namespaced
:class:`~sport_core.competitors.CompetitorId` → Betfair runner alias.

Structure and guarantees:

* **Namespaces stay distinct** — ATP → ``td-atp``, WTA → ``td-wta``; the same
  surname+initial in both tours is two identities, and a Betfair name matching both
  refuses as cross-namespace ambiguous rather than guessing a tour.
* **Display names are never canonical identity** — identity is the namespaced
  ``CompetitorId``; Betfair names ride as :class:`~sport_core.competitors.
  CompetitorDisplay` aliases (F-07 discipline: nothing joins on names downstream of
  this module; this module is the ONE governed place name-joining happens).
* **Deterministic, versioned normalization** — ``NORMALIZATION_VERSION = td-norm-v1``:
  NFKD diacritic stripping, casefold, whitespace collapse. Changing the rule is a
  version bump, never an in-place edit.
* **Ambiguity refuses** — a Tennis-Data identity matching multiple Betfair names, a
  Betfair name matching multiple source identities, or a cross-namespace tie lands in
  the UNRESOLVED ledger with a typed reason; nothing is dropped and nothing is guessed.
* **Corrections are append-only** — :func:`apply_corrections` returns a NEW result
  carrying the correction records (who, why, what); originals are never mutated. There
  are deliberately no hand-coded aliases in this module: every mapping derives from the
  inputs, and every exception goes through a recorded correction.
* **No sporting result is used** — inputs are names only; June results are sealed and
  irrelevant here by construction.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum, unique

from sport_core.competitors import CompetitorDisplay, CompetitorId

__all__ = [
    "NORMALIZATION_VERSION",
    "PROVIDER",
    "SourceIdentity",
    "BridgeProvenance",
    "BridgeMapping",
    "UnresolvedReason",
    "UnresolvedIdentity",
    "BridgeResult",
    "IdentityCorrection",
    "normalize_name",
    "build_bridge",
    "apply_corrections",
    "load_correction_ledger",
]

NORMALIZATION_VERSION = "td-norm-v1"
PROVIDER = "tennis-data.co.uk"
_TOUR_NAMESPACE = {"ATP": "td-atp", "WTA": "td-wta"}


def normalize_name(raw: str) -> str:
    """Deterministic ``td-norm-v1``: NFKD-strip diacritics, casefold, collapse spaces."""
    decomposed = unicodedata.normalize("NFKD", raw)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(ascii_only.casefold().split())


def _td_key(normalized: str) -> tuple[str, str] | None:
    """(surname, initials) from a Tennis-Data name like 'de minaur a.' / 'del potro j.m.'.

    The trailing dotted token(s) are initials; everything before is the surname."""
    tokens = normalized.split(" ")
    initial_tokens: list[str] = []
    while tokens and tokens[-1].replace(".", "").isalpha() and "." in tokens[-1]:
        initial_tokens.insert(0, tokens.pop())
    if not tokens or not initial_tokens:
        return None
    initials = "".join(t.replace(".", "") for t in initial_tokens)
    return (" ".join(tokens), initials)


def _betfair_keys(normalized: str) -> list[tuple[str, str]]:
    """Candidate (surname, initials) keys for a Betfair full name, one per split point:
    'juan martin del potro' → ('martin del potro','j'), ('del potro','jm'), ('potro','jmd')."""
    tokens = normalized.split(" ")
    if len(tokens) < 2:
        return []
    keys = []
    for k in range(1, len(tokens)):
        surname = " ".join(tokens[k:])
        initials = "".join(t[0] for t in tokens[:k] if t)
        keys.append((surname, initials))
    return keys


@dataclass(frozen=True)
class SourceIdentity:
    """Provider-specific identity: the provider, tour namespace, and the RAW name."""

    provider: str
    tour: str
    raw_name: str
    normalized_name: str


@dataclass(frozen=True)
class BridgeProvenance:
    provider: str
    source_vintage: str
    normalization_version: str


@dataclass(frozen=True)
class BridgeMapping:
    competitor_id: CompetitorId
    source: SourceIdentity
    betfair_alias: CompetitorDisplay
    provenance: BridgeProvenance


@unique
class UnresolvedReason(Enum):
    NO_SOURCE_MATCH = "NO_SOURCE_MATCH"                    # Betfair name matches no source identity
    HOMONYM_MULTIPLE_BETFAIR = "HOMONYM_MULTIPLE_BETFAIR"  # one source identity, >1 Betfair name
    HOMONYM_MULTIPLE_SOURCE = "HOMONYM_MULTIPLE_SOURCE"    # one Betfair name, >1 source identity, same namespace
    CROSS_NAMESPACE_AMBIGUOUS = "CROSS_NAMESPACE_AMBIGUOUS"  # matches in both td-atp and td-wta
    MALFORMED_SOURCE_NAME = "MALFORMED_SOURCE_NAME"        # Tennis-Data name without surname+initial shape


@dataclass(frozen=True)
class UnresolvedIdentity:
    name: str
    reason: UnresolvedReason
    detail: str


@dataclass(frozen=True)
class IdentityCorrection:
    """Append-only, provenanced human correction (merge/alias/detach). Never silent."""

    subject: CompetitorId
    action: str            # e.g. ADD_ALIAS | MERGE_INTO | DETACH_ALIAS
    detail: str
    authorised_by: str
    rationale: str

    def __post_init__(self) -> None:
        for field_name in ("action", "detail", "authorised_by", "rationale"):
            if not getattr(self, field_name):
                raise ValueError(f"IdentityCorrection.{field_name} must be non-empty")


@dataclass(frozen=True)
class BridgeResult:
    mappings: tuple[BridgeMapping, ...]
    unresolved: tuple[UnresolvedIdentity, ...]
    corrections: tuple[IdentityCorrection, ...] = ()


def build_bridge(
    *,
    td_names_by_tour: Mapping[str, Iterable[str]],
    betfair_full_names: Iterable[str],
    source_vintage: str,
) -> BridgeResult:
    """Pure, deterministic, order-independent bridge construction. Names in, mappings +
    unresolved ledger out; every ambiguity refuses with a typed reason."""
    provenance_by_tour: dict[str, BridgeProvenance] = {}
    # source identities keyed (namespace, surname, initials); whitespace/diacritic
    # variants of the same raw name collapse to ONE source identity per tour.
    sources: dict[tuple[str, str, str], SourceIdentity] = {}
    unresolved: list[UnresolvedIdentity] = []
    for tour in sorted(td_names_by_tour):
        namespace = _TOUR_NAMESPACE.get(tour.upper())
        if namespace is None:
            raise ValueError(f"unknown tour {tour!r}: namespaces are ATP/WTA only")
        provenance_by_tour[namespace] = BridgeProvenance(
            provider=PROVIDER, source_vintage=source_vintage, normalization_version=NORMALIZATION_VERSION
        )
        for raw in sorted(set(td_names_by_tour[tour])):
            norm = normalize_name(raw)
            key = _td_key(norm)
            if key is None:
                unresolved.append(
                    UnresolvedIdentity(name=raw, reason=UnresolvedReason.MALFORMED_SOURCE_NAME, detail=tour)
                )
                continue
            sources.setdefault((namespace, key[0], key[1]), SourceIdentity(
                provider=PROVIDER, tour=tour.upper(), raw_name=raw, normalized_name=norm
            ))

    # Betfair name -> candidate source identities (exact surname + initials-prefix rule:
    # source initials must be a prefix of the Betfair-derived initials or vice versa).
    matches_by_source: dict[tuple[str, str, str], list[str]] = {}
    candidates_by_betfair: dict[str, list[tuple[str, str, str]]] = {}
    for bf in sorted(set(betfair_full_names)):
        bnorm = normalize_name(bf)
        cands: list[tuple[str, str, str]] = []
        for surname, initials in _betfair_keys(bnorm):
            for (namespace, s_sur, s_ini), _src in sources.items():
                if s_sur == surname and (s_ini.startswith(initials) or initials.startswith(s_ini)):
                    cands.append((namespace, s_sur, s_ini))
        cands = sorted(set(cands))
        candidates_by_betfair[bf] = cands
        for c in cands:
            matches_by_source.setdefault(c, []).append(bf)

    mappings: list[BridgeMapping] = []
    for bf in sorted(candidates_by_betfair):
        cands = candidates_by_betfair[bf]
        if not cands:
            unresolved.append(UnresolvedIdentity(name=bf, reason=UnresolvedReason.NO_SOURCE_MATCH, detail=""))
            continue
        namespaces = {c[0] for c in cands}
        if len(namespaces) > 1:
            unresolved.append(
                UnresolvedIdentity(
                    name=bf, reason=UnresolvedReason.CROSS_NAMESPACE_AMBIGUOUS, detail=str(sorted(namespaces))
                )
            )
            continue
        if len(cands) > 1:
            unresolved.append(
                UnresolvedIdentity(
                    name=bf,
                    reason=UnresolvedReason.HOMONYM_MULTIPLE_SOURCE,
                    detail=str([f"{c[1]}|{c[2]}" for c in cands]),
                )
            )
            continue
        c = cands[0]
        if len(matches_by_source[c]) > 1:
            unresolved.append(
                UnresolvedIdentity(
                    name=bf,
                    reason=UnresolvedReason.HOMONYM_MULTIPLE_BETFAIR,
                    detail=str(sorted(matches_by_source[c])),
                )
            )
            continue
        namespace, surname, initials = c
        cid = CompetitorId(f"{namespace}:{surname}|{initials}")
        mappings.append(
            BridgeMapping(
                competitor_id=cid,
                source=sources[c],
                betfair_alias=CompetitorDisplay(
                    competitor_id=cid, display_name=bf, aliases=frozenset({bf})
                ),
                provenance=provenance_by_tour[namespace],
            )
        )
    return BridgeResult(mappings=tuple(mappings), unresolved=tuple(sorted(unresolved, key=lambda u: (u.reason.value, u.name))))


def load_correction_ledger(path: str) -> tuple[IdentityCorrection, ...]:
    """Load the append-only governed identity-correction ledger
    (specs/evidence/identity-correction-ledger-v1.yaml). Returns the applied corrections
    in file order (an empty tuple when none have been human-entered yet). An agent never
    writes this file — corrections are per-case, evidence-backed, human-reviewed entries.
    """
    import yaml

    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    out: list[IdentityCorrection] = []
    for row in doc.get("corrections") or []:
        out.append(
            IdentityCorrection(
                subject=CompetitorId(row["subject"]),
                action=row["action"],
                detail=row["detail"],
                authorised_by=row["reviewer"],
                rationale=row["rationale"],
            )
        )
    return tuple(out)


def apply_corrections(result: BridgeResult, corrections: Sequence[IdentityCorrection]) -> BridgeResult:
    """Append-only: returns a NEW result with corrections applied and recorded; the input
    result is never mutated. A correction referencing an unknown identity refuses."""
    known = {m.competitor_id for m in result.mappings}
    new_mappings = list(result.mappings)
    for c in corrections:
        if c.subject not in known:
            raise ValueError(f"correction refers to unknown identity {c.subject.value!r}")
        if c.action == "ADD_ALIAS":
            for i, m in enumerate(new_mappings):
                if m.competitor_id == c.subject:
                    new_alias = replace(
                        m.betfair_alias, aliases=m.betfair_alias.aliases | {c.detail}
                    )
                    new_mappings[i] = replace(m, betfair_alias=new_alias)
        # other actions (MERGE_INTO, DETACH_ALIAS) are recorded append-only and applied
        # by future governed logic; recording without silent application is the
        # conservative default for actions this version does not yet interpret.
    return BridgeResult(
        mappings=tuple(new_mappings),
        unresolved=result.unresolved,
        corrections=result.corrections + tuple(corrections),
    )
