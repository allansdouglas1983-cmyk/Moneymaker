"""Derive the (tour, city) -> surface table that board.ts serves.

The Odds API names tournaments geographically (`tennis_atp_washington_open`) while the
corpus names them by sponsor (`Citi Open`), so the two cannot be joined by name. They CAN
be joined by city: the corpus carries `location` alongside `surface` for every match.

Emitted from data, never from recall — the Stuttgart split (ATP grass, WTA clay, same city
same month) is the case that makes recall unsafe. A city whose surface is not overwhelmingly
consistent is OMITTED rather than guessed: London hosts Queen's on grass and the Finals on
indoor hard, Paris hosts Roland Garros on clay and the Masters on hard.

Run from tennis-edge/: python tools/derive_surface_map.py
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.corpus import default_vintage_root, load_corpus  # noqa: E402
from tennis_edge.refresh import latest_vintage  # noqa: E402

#: Editions before this are excluded: a venue that resurfaced should be represented by
#: what it is now, not by an average over its history.
SINCE = "2019-01-01"
#: A city must be this consistent to be asserted at all.
MIN_PURITY = 0.98
#: And carry this many matches, so one small edition cannot mint a mapping.
MIN_MATCHES = 20


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


def main() -> None:
    vintage = latest_vintage(default_vintage_root())
    assert vintage is not None
    matches, _stats = load_corpus(vintage.root)
    recent = [m for m in matches if str(m.match_date) >= SINCE]

    counts: dict[tuple[str, str], collections.Counter] = collections.defaultdict(
        collections.Counter)
    for m in recent:
        counts[(m.tour, slug(m.location))][m.surface] += 1

    kept, omitted = [], []
    for (tour, city), surfaces in sorted(counts.items()):
        surface, top = surfaces.most_common(1)[0]
        total = sum(surfaces.values())
        purity = top / total
        if not city or surface not in ("Hard", "Clay", "Grass"):
            omitted.append((tour, city, dict(surfaces), "unusable"))
        elif purity < MIN_PURITY or total < MIN_MATCHES:
            omitted.append((tour, city, dict(surfaces), f"purity={purity:.2f} n={total}"))
        else:
            kept.append((tour, city, surface, total))

    print(f"// Derived by tools/derive_surface_map.py from {vintage.root.name}:")
    print(f"// {len(recent):,} matches since {SINCE}, {len(kept)} cities asserted, "
          f"{len(omitted)} omitted as ambiguous.")
    print("const CITY_SURFACE: Record<string, string> = {")
    for tour, city, surface, total in kept:
        print(f'  "{tour}|{city}": "{surface}",  // {total} matches')
    print("};")
    print()
    print("// Omitted — genuinely ambiguous, so served as the Hard default and flagged:")
    for tour, city, surfaces, why in omitted:
        print(f"//   {tour} {city}: {surfaces} ({why})")


if __name__ == "__main__":
    main()
