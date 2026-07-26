"""Build the feature matrix once, keyed to the inputs that produced it.

Building features walks the whole Sackmann archive day by day, advancing the rating and
serve state one tournament week at a time, and takes about ten minutes. Every experiment
that wanted the same features paid it again. That is a tax on trying things, and trying
things is the job: four re-runs of a single experiment in one session — a divergence fix, a
control, a venue, a placebo — is what made the tax visible.

**The cache is keyed on what produced it, and a mismatch is a miss rather than a warning.**
A feature cache that silently outlives its inputs is worse than no cache at all: it answers
a question nobody asked, and the answer looks exactly like a real one. Four things identify
a build:

- ``feature_set_version`` — bumped by hand whenever a feature is added, removed or its
  definition changes. This is the one a human has to remember, so it is a module constant
  sitting next to the builder rather than buried in a config file.
- ``corpus_vintage`` — the vintage directory name.
- ``corpus_manifest_digest`` — the vintage's own manifest digest, which catches the
  dangerous case the directory name cannot: same vintage, different contents.
- ``archive_digest`` — over the Sackmann file inventory, which catches a restored or
  extended archive.

A truncated file raises rather than returning short. A run killed mid-write leaves a
plausible-looking cache with fewer rows than it claims, and silently training on a prefix of
the data would be invisible in every downstream number.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from tennis_edge.digests import digest_bytes

__all__ = [
    "FEATURE_SET_VERSION",
    "CacheKey",
    "FeatureRow",
    "archive_digest",
    "load_cache",
    "write_cache",
]

#: Bump on ANY change to what a feature means or which features exist. Nothing else
#: invalidates a cache after a feature edit, because the corpus and archive digests do not
#: change when the code that reads them does.
#: v2 adds the decomposed serve/return layer (serve_detail).
FEATURE_SET_VERSION = "residual-v2"

_KIND = "tennis-edge-feature-cache-v1"


@dataclass(frozen=True)
class CacheKey:
    """Everything that has to match before a cache may be used."""

    feature_set_version: str
    corpus_vintage: str
    corpus_manifest_digest: str
    archive_digest: str


@dataclass(frozen=True)
class FeatureRow:
    """One priced match: its market view, its features, its result and its quotes.

    ``features`` is deliberately sparse. A row without serve coverage has no
    ``point_model_residual`` key at all rather than a zero, because absence is a claim about
    what is known and zero is a claim about the world.
    """

    date: dt.date
    tour: str
    player_a: str
    player_b: str
    market_logit: float
    features: dict[str, float]
    won: int
    odds_a: dict[str, float]
    odds_b: dict[str, float]


def archive_digest(paths: Sequence[Path]) -> str:
    """Digest over the archive inventory: name and byte size of every file, sorted.

    Sizes rather than contents. Hashing a few million rows on every startup would reintroduce
    the cost this module exists to remove, and the archive is append-only in practice — a
    restored, extended or truncated file changes its size.
    """
    inventory = sorted(f"{path.name}:{path.stat().st_size}" for path in paths)
    return digest_bytes("\n".join(inventory).encode("utf-8"))


def write_cache(path: Path | str, rows: Sequence[FeatureRow], *, key: CacheKey) -> None:
    """Write atomically via a temporary file, then rename.

    A cache half-written by an interrupted run is the failure mode :func:`load_cache`
    detects; this is the half that stops it being produced in the first place.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    scratch = target.with_suffix(target.suffix + ".partial")
    with scratch.open("w", encoding="utf-8") as handle:
        header = {"kind": _KIND, "rows": len(rows), **asdict(key)}
        handle.write(json.dumps(header, sort_keys=True) + "\n")
        for row in rows:
            payload = asdict(row)
            payload["date"] = row.date.isoformat()
            handle.write(json.dumps(payload, sort_keys=True,
                                    separators=(",", ":")) + "\n")
    scratch.replace(target)


def load_cache(path: Path | str, *, key: CacheKey) -> list[FeatureRow] | None:
    """Return the cached rows, or ``None`` when there is nothing usable here.

    ``None`` means "build it": either no file, or a file describing different inputs. Both
    are ordinary and neither is an error — a cold cache is what every first run sees.

    A file that *is* this cache but is internally inconsistent raises instead, because that
    is a corrupted artefact rather than an absent one, and rebuilding over it silently would
    hide whatever produced it.
    """
    target = Path(path)
    if not target.exists():
        return None
    lines = target.read_text(encoding="utf-8").splitlines()
    if not lines:
        return None
    header = json.loads(lines[0])
    if header.get("kind") != _KIND:
        raise ValueError(f"not a feature cache: {target}")
    if any(header.get(field) != value for field, value in asdict(key).items()):
        return None
    body = [line for line in lines[1:] if line.strip()]
    if len(body) != header.get("rows"):
        raise ValueError(
            f"truncated feature cache: {target} claims {header.get('rows')} rows, "
            f"holds {len(body)} — delete it and rebuild rather than training on a prefix"
        )
    out: list[FeatureRow] = []
    for line in body:
        raw = json.loads(line)
        raw["date"] = dt.date.fromisoformat(raw["date"])
        out.append(FeatureRow(**raw))
    return out
