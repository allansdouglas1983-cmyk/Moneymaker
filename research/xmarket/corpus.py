"""Cross-market feasibility audit — corpus reader (STAGE3-0002 §3; audit code version
xmarket-audit-v1).

Thin, deterministic reader over the bz2 ADVANCED corpus: market_id from the filename, the
first ``marketDefinition`` as a :class:`~research.xmarket.linkage.MarketRef`, and the
ordered stream messages for reconstruction. No price/outcome interpretation here.

Audit-only: reads market DEFINITION identity fields and (downstream) prices; NEVER
outcomes/settlement. Import-quarantined from l5_decision / l5b_risk / l6_broker. No
latent-model equation. The raw corpus is read-only — this module never writes to it.
"""
from __future__ import annotations

import bz2
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from research.xmarket.linkage import MarketRef

AUDIT_CODE_VERSION = "xmarket-audit-v1"


class CorpusReadError(Exception):
    """A corpus file cannot be read deterministically (e.g. no marketDefinition)."""


def market_id_from_path(path: Path | str) -> str:
    """The Betfair market id is the filename without the .bz2 suffix (e.g. 1.258775580)."""
    name = Path(path).name
    if name.endswith(".bz2"):
        name = name[: -len(".bz2")]
    return name


def _market_time_ms(value: object) -> int | None:
    """Parse a Betfair ISO marketTime (e.g. 2026-06-03T12:00:00.000Z) to epoch ms, or an
    already-numeric epoch ms straight through. Unparseable / absent => None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value:
        iso = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    return None


def iter_messages(path: Path | str) -> Iterator[dict[str, Any]]:
    """Yield the stream messages of a market file in file (publish) order."""
    with bz2.open(path, "rt") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def read_first_definition(path: Path | str) -> MarketRef:
    """Read the first ``marketDefinition`` in a market file into a MarketRef. Refuses a file
    that never carries a marketDefinition."""
    mid = market_id_from_path(path)
    for msg in iter_messages(path):
        for mc in msg.get("mc") or []:
            md = mc.get("marketDefinition")
            if md is not None:
                return MarketRef(
                    market_id=mc.get("id", mid),
                    event_id=md.get("eventId"),
                    market_type=md.get("marketType"),
                    market_time_ms=_market_time_ms(md.get("marketTime")),
                    event_name=md.get("eventName"),
                )
    raise CorpusReadError(f"{path} has no marketDefinition")


def iter_market_files(root: Path | str) -> Iterator[tuple[str, Path]]:
    """Yield (market_id, path) for every .bz2 file under root, in sorted path order."""
    for p in sorted(Path(root).rglob("*.bz2")):
        yield market_id_from_path(p), p


def build_corpus_catalogue(root: Path | str) -> dict[str, MarketRef]:
    """Read every market's first definition into a deterministic market_id -> MarketRef
    catalogue. A file without a definition is skipped-with-refusal upstream; here we raise
    so the caller records it in the funnel rather than silently dropping it."""
    cat: dict[str, MarketRef] = {}
    for _mid, path in iter_market_files(root):
        ref = read_first_definition(path)
        cat[ref.market_id] = ref
    return cat
