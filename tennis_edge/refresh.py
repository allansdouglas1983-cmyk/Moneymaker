"""Tennis-Data acquisition with immutable vintages.

The corpus is the foundation every measurement in this package rests on, so it is versioned
rather than overwritten. A run that finds changed provider bytes mints a **new** vintage
directory and copies unchanged files into it, leaving every earlier vintage exactly as it
was. That is what makes an old result re-runnable: a number computed on
``vintage-2026-07-18`` can still be reproduced after the provider revises a file.

Each stored file records its source URL, retrieval time, the provider's ``Last-Modified`` and
``ETag``, and a SHA-256. Conditional requests use the previous vintage's validators, so a
weekly run normally transfers almost nothing.

Only the current and previous year are re-fetched by default. Earlier years are settled
history that the provider does not revise, and pulling 47 files weekly to discover that would
be rude to a free service.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from tennis_edge.corpus import default_vintage_root
from tennis_edge.digests import digest_bytes

__all__ = [
    "BASE_URL",
    "TOUR_FIRST_YEAR",
    "MUTABLE_YEAR_LOOKBACK",
    "FetchResponse",
    "Fetcher",
    "FileProvenance",
    "Vintage",
    "RefreshResult",
    "http_fetcher",
    "list_vintages",
    "latest_vintage",
    "refresh",
]

BASE_URL = "http://www.tennis-data.co.uk"
TOUR_FIRST_YEAR: Mapping[str, int] = {"ATP": 2000, "WTA": 2007}

#: Years within this many of the current one are re-checked every run; older ones only when
#: the local vintage is missing the file entirely.
MUTABLE_YEAR_LOOKBACK = 1

_TOUR_PATH = {"ATP": "{year}", "WTA": "{year}w"}
_FORMATS = ("{year}.xlsx", "{year}.xls")

#: WTA directories before 2007 exist on the site but serve unrelated or ATP content — the
#: 2001w file contains 2010s rows, 2006w serves the ATP file. Fetching them would silently
#: corrupt the corpus, so the first-year floor above is enforced, not advisory.
_WTA_FLOOR_NOTE = "WTA directories before 2007 serve mislabelled content and are never fetched"


@dataclass(frozen=True)
class FetchResponse:
    """One HTTP result. ``body`` is None for 304 Not Modified or any non-200."""

    status: int
    body: bytes | None
    last_modified: str | None = None
    etag: str | None = None


#: (url, conditional headers) -> response. Injected so tests never touch the network.
Fetcher = Callable[[str, Mapping[str, str]], FetchResponse]


@dataclass(frozen=True)
class FileProvenance:
    """Everything recorded about one stored provider file."""

    tour: str
    year: int
    source_url: str
    stored_as: str
    sha256: str
    size_bytes: int
    retrieved_utc: str
    last_modified: str | None
    etag: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "tour": self.tour, "year": self.year, "source_url": self.source_url,
            "stored_as": self.stored_as, "sha256": self.sha256,
            "size_bytes": self.size_bytes, "retrieved_utc": self.retrieved_utc,
            "last_modified": self.last_modified, "etag": self.etag,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "FileProvenance":
        return cls(
            tour=str(raw["tour"]), year=int(str(raw["year"])),
            source_url=str(raw["source_url"]), stored_as=str(raw["stored_as"]),
            sha256=str(raw["sha256"]), size_bytes=int(str(raw["size_bytes"])),
            retrieved_utc=str(raw["retrieved_utc"]),
            last_modified=None if raw.get("last_modified") is None
            else str(raw["last_modified"]),
            etag=None if raw.get("etag") is None else str(raw["etag"]),
        )


@dataclass(frozen=True)
class Vintage:
    """An immutable directory of provider bytes plus its provenance."""

    vintage_id: str
    root: Path
    provenance: tuple[FileProvenance, ...]
    #: False when the provenance was reconstructed by hashing files on disk rather than
    #: recorded at download time — an externally supplied corpus. The bytes are still
    #: digested and reproducible, but there is no retrieval time or provider validator, so
    #: any claim about *when* the data was obtained is unavailable rather than assumed.
    provenance_complete: bool = True

    def by_key(self) -> dict[tuple[str, int], FileProvenance]:
        return {(p.tour, p.year): p for p in self.provenance}

    def path_of(self, prov: FileProvenance) -> Path:
        return self.root / prov.stored_as

    @property
    def manifest_digest(self) -> str:
        manifest = "\n".join(sorted(f"{p.sha256}  {p.stored_as}" for p in self.provenance))
        return digest_bytes((manifest + "\n").encode("utf-8"))


@dataclass(frozen=True)
class RefreshResult:
    """Outcome of one refresh run."""

    changed: bool
    vintage: Vintage
    previous_vintage_id: str | None
    checked: int
    unchanged: int
    updated: tuple[str, ...]
    added: tuple[str, ...]
    failures: tuple[str, ...]

    def report(self) -> str:
        head = "new vintage" if self.changed else "no change"
        return (
            f"{head}: {self.vintage.vintage_id} ({len(self.vintage.provenance)} files, "
            f"manifest {self.vintage.manifest_digest[:19]}...)\n"
            f"  checked {self.checked}, unchanged {self.unchanged}, "
            f"updated {len(self.updated)}, added {len(self.added)}, "
            f"failures {len(self.failures)}"
        )


def http_fetcher(url: str, headers: Mapping[str, str]) -> FetchResponse:
    """One polite conditional GET against the permitted source."""
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            return FetchResponse(
                status=int(response.status), body=response.read(),
                last_modified=response.headers.get("Last-Modified"),
                etag=response.headers.get("ETag"),
            )
    except urllib.error.HTTPError as exc:
        return FetchResponse(
            status=int(exc.code), body=None,
            last_modified=exc.headers.get("Last-Modified") if exc.headers else None,
            etag=exc.headers.get("ETag") if exc.headers else None,
        )
    except urllib.error.URLError as exc:
        return FetchResponse(status=0, body=None) if exc else FetchResponse(0, None)


def list_vintages(root: Path | str) -> list[Vintage]:
    """Every vintage under ``root/tennis_data``, oldest first."""
    base = Path(root) / "tennis_data"
    if not base.exists():
        return []
    out: list[Vintage] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir() or not child.name.startswith("vintage-"):
            continue
        provenance_path = child / "PROVENANCE.json"
        if provenance_path.exists():
            rows = json.loads(provenance_path.read_text())
            out.append(
                Vintage(
                    vintage_id=child.name, root=child,
                    provenance=tuple(FileProvenance.from_dict(r) for r in rows),
                )
            )
            continue
        reconstructed = _reconstruct_provenance(child)
        if reconstructed:
            out.append(
                Vintage(
                    vintage_id=child.name, root=child, provenance=reconstructed,
                    provenance_complete=False,
                )
            )
    return out


def _reconstruct_provenance(directory: Path) -> tuple[FileProvenance, ...]:
    """Derive provenance for a corpus placed on disk without a download record.

    Used for an externally supplied vintage. Everything derivable from the bytes is
    derived; everything about the retrieval is left explicitly unknown rather than invented.
    """
    rows: list[FileProvenance] = []
    for path in sorted(directory.iterdir()):
        if path.suffix not in (".xls", ".xlsx") or not path.is_file():
            continue
        stem = path.stem
        tour = "ATP" if stem.lower().startswith("atp") else "WTA"
        digits = "".join(ch for ch in stem if ch.isdigit())
        if len(digits) < 4:
            continue
        payload = path.read_bytes()
        rows.append(
            FileProvenance(
                tour=tour, year=int(digits[:4]), source_url="", stored_as=path.name,
                sha256=digest_bytes(payload), size_bytes=len(payload),
                retrieved_utc="unknown", last_modified=None, etag=None,
            )
        )
    return tuple(sorted(rows, key=lambda p: (p.tour, p.year)))


def latest_vintage(root: Path | str) -> Vintage | None:
    vintages = list_vintages(root)
    return vintages[-1] if vintages else None


def _targets(
    previous: Vintage | None, *, today: dt.date, years: Sequence[int] | None
) -> list[tuple[str, int]]:
    have = previous.by_key() if previous is not None else {}
    targets: list[tuple[str, int]] = []
    for tour, first in sorted(TOUR_FIRST_YEAR.items()):
        span = years if years is not None else range(first, today.year + 1)
        for year in span:
            if year < first or year > today.year:
                continue  # the WTA floor is load-bearing: see _WTA_FLOOR_NOTE
            if years is not None or (tour, year) not in have:
                targets.append((tour, year))
            elif year >= today.year - MUTABLE_YEAR_LOOKBACK:
                targets.append((tour, year))
    return targets


def _next_vintage_dir(base: Path, today: dt.date) -> tuple[str, Path]:
    stem = f"vintage-{today.isoformat()}"
    candidate = base / stem
    suffix = 1
    while candidate.exists():
        candidate = base / f"{stem}-{suffix:02d}"
        suffix += 1
    return candidate.name, candidate


def refresh(
    root: Path | str | None = None,
    *,
    now_utc: dt.datetime,
    fetcher: Fetcher = http_fetcher,
    years: Sequence[int] | None = None,
) -> RefreshResult:
    """Check the source, download what changed, mint a new vintage only if content moved."""
    base = (Path(root) if root is not None else default_vintage_root()) / "tennis_data"
    base.mkdir(parents=True, exist_ok=True)
    today = now_utc.date()
    retrieved = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    previous = latest_vintage(base.parent)
    have = previous.by_key() if previous is not None else {}

    fetched: dict[tuple[str, int], tuple[bytes, str | None, str | None, str]] = {}
    failures: list[str] = []
    updated: list[str] = []
    added: list[str] = []
    unchanged = 0

    targets = _targets(previous, today=today, years=years)
    for tour, year in targets:
        prior = have.get((tour, year))
        headers: dict[str, str] = {}
        if prior is not None:
            if prior.etag:
                headers["If-None-Match"] = prior.etag
            if prior.last_modified:
                headers["If-Modified-Since"] = prior.last_modified
        got = False
        for template in _FORMATS:
            name = template.format(year=year)
            url = f"{BASE_URL}/{_TOUR_PATH[tour].format(year=year)}/{name}"
            response = fetcher(url, headers)
            if response.status == 304:
                unchanged += 1
                got = True
                break
            if response.status != 200 or response.body is None:
                continue
            digest = digest_bytes(response.body)
            if prior is not None and digest == prior.sha256:
                unchanged += 1
            elif prior is None:
                added.append(f"{tour}-{year}")
            else:
                updated.append(f"{tour}-{year}")
            fetched[(tour, year)] = (
                response.body, response.last_modified, response.etag, url
            )
            got = True
            break
        if not got:
            failures.append(f"{tour}-{year}")

    if not (updated or added):
        if previous is None:
            raise RuntimeError("no local vintage exists and nothing could be retrieved")
        return RefreshResult(
            changed=False, vintage=previous, previous_vintage_id=previous.vintage_id,
            checked=len(targets), unchanged=unchanged, updated=(), added=(),
            failures=tuple(failures),
        )

    vintage_id, vintage_dir = _next_vintage_dir(base, today)
    vintage_dir.mkdir(parents=True)
    provenance: list[FileProvenance] = []
    carried = dict(have)
    for key, (body, last_modified, etag, url) in sorted(fetched.items()):
        tour, year = key
        stored_as = f"{tour.lower()}-{year}{Path(url).suffix}"
        (vintage_dir / stored_as).write_bytes(body)
        provenance.append(
            FileProvenance(
                tour=tour, year=year, source_url=url, stored_as=stored_as,
                sha256=digest_bytes(body), size_bytes=len(body), retrieved_utc=retrieved,
                last_modified=last_modified, etag=etag,
            )
        )
        carried.pop(key, None)
    if previous is not None:
        for key, prior in sorted(carried.items()):
            source = previous.path_of(prior)
            if source.exists():
                shutil.copyfile(source, vintage_dir / prior.stored_as)
                provenance.append(prior)
    provenance.sort(key=lambda p: (p.tour, p.year))

    (vintage_dir / "PROVENANCE.json").write_text(
        json.dumps([p.to_dict() for p in provenance], indent=1, sort_keys=True) + "\n"
    )
    vintage = Vintage(vintage_id=vintage_id, root=vintage_dir, provenance=tuple(provenance))
    (vintage_dir / "MANIFEST.sha256").write_text(
        "\n".join(sorted(f"{p.sha256}  {p.stored_as}" for p in provenance)) + "\n"
    )
    return RefreshResult(
        changed=True, vintage=vintage,
        previous_vintage_id=None if previous is None else previous.vintage_id,
        checked=len(targets), unchanged=unchanged,
        updated=tuple(sorted(updated)), added=tuple(sorted(added)),
        failures=tuple(failures),
    )
