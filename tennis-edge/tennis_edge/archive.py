"""Restoring Jeff Sackmann's match archive from Software Heritage.

``JeffSackmann/tennis_atp`` and ``tennis_wta`` are **deleted from GitHub**. Software
Heritage crawled both before they went, so its archive is now the only route to the corpus
— and that makes this module load-bearing rather than convenient. Without it a fresh
container has no serve statistics, and :mod:`tennis_edge.weekly` refuses to run at all.

Everything is **pinned**, not resolved live. Each entry in :data:`PINNED` names the exact
snapshot, revision and directory of the last successful crawl, plus a digest over the git
blob hashes of every match file it should contain. A restore that does not reproduce that
digest is refused. Two consequences worth stating:

* the corpus is reproducible — the same pin always yields the same bytes, which is what a
  frozen policy needs underneath it;
* the coverage asymmetry is permanent. ATP was last archived 2026-05-08 and WTA
  2025-01-03, so ATP runs to May 2026 and WTA only to the end of the 2024 season. That is
  a real property of the data and any split has to respect it.

The vault route costs about five requests per repository rather than one per file, which
matters: Software Heritage rate-limits anonymous API use to 120 requests an hour, and the
two repositories hold 280 match files between them. Compressed they are roughly 88 MB and
download in under twenty seconds.

**Licence.** CC BY-NC-SA 4.0 — attribution to Jeff Sackmann / Tennis Abstract,
non-commercial use only. The files are written outside the repository and are never
committed or redistributed.

Run with ``python -m tennis_edge.archive`` (``--verify`` to check without fetching).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

from tennis_edge.sackmann import default_root

__all__ = [
    "PINNED",
    "PinnedArchive",
    "RestoreError",
    "RestoreResult",
    "git_blob_sha1",
    "manifest_digest",
    "manifest_of",
    "restore",
    "verify",
    "main",
]

_API = "https://archive.softwareheritage.org/api/1"

#: Files the corpus consumes. ``sackmann.available_files`` sorts these into families and
#: skips doubles and amateur outright, so those are not installed either — 22 of the ATP
#: repository's 166 match files are singles-irrelevant and nothing would ever read them.
#: The repository README and the point-by-point data are likewise not fetched.
#: ``test_the_installed_set_is_exactly_what_the_loader_consumes`` holds the two in step.
_MATCH_FILE = re.compile(r"^(atp|wta)_matches_[a-z0-9_]*\.csv$")
_NOT_SINGLES = ("doubles", "amateur")


def _is_consumed(name: str) -> bool:
    """Whether ``sackmann.available_files`` would ever hand this file to a loader."""
    return bool(_MATCH_FILE.match(name)) and not any(t in name for t in _NOT_SINGLES)

#: A cooked tarball is trusted for its bytes, never for its member names.
_MAX_MEMBER_BYTES = 256 * 1024 * 1024


class RestoreError(RuntimeError):
    """The archive could not be restored to the pinned content."""


@dataclass(frozen=True)
class PinnedArchive:
    """One deleted repository, pinned to a specific Software Heritage crawl."""

    repo: str
    tour: str
    #: Date of the last successful crawl — the true end of this tour's coverage.
    visit_date: str
    snapshot: str
    revision: str
    directory: str
    file_count: int
    manifest_digest: str

    @property
    def swhid(self) -> str:
        return f"swh:1:dir:{self.directory}"

    @property
    def vault_url(self) -> str:
        return f"{_API}/vault/flat/{self.swhid}/"

    @property
    def raw_url(self) -> str:
        return f"{self.vault_url}raw/"

    def target(self, root: Path) -> Path:
        return root / self.repo


#: The last successful crawl of each repository before it was deleted. Resolved and
#: verified against the corpus in use on 2026-07-25: every consumed file reproduced byte
#: for byte.
PINNED: tuple[PinnedArchive, ...] = (
    PinnedArchive(
        repo="tennis_atp", tour="atp", visit_date="2026-05-08",
        snapshot="eb00298fdee7dfd337518efa20717c5dd7b5bcfa",
        revision="2c40e40c0f3ac51cc11eabe6c7c25932234e83e0",
        directory="5f25f9c216cf8621c36e81d86f6b9ccaba0911d4",
        file_count=144,
        manifest_digest=(
            "sha256:3d89797776540e9f8870e58bee5b9466db953cce0d303684d5fae70ba275bc75"
        ),
    ),
    PinnedArchive(
        repo="tennis_wta", tour="wta", visit_date="2025-01-03",
        snapshot="a7180315f0ad8304c821a58be9685f128631f9f3",
        revision="225f6afd12d906cbe9bfab507551cdc5f346a540",
        directory="4806024f4da7f98c24adc77fd5e30507a869209e",
        file_count=114,
        manifest_digest=(
            "sha256:1acb161438d850e7afb469d07f6ad7b585b33a280db64b0ae6102a8908a99771"
        ),
    ),
)


@dataclass
class RestoreResult:
    """What one restore did."""

    restored: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    root: Path = Path(".")

    def report(self) -> str:
        parts = []
        if self.restored:
            parts.append("restored " + ", ".join(self.restored))
        if self.skipped:
            parts.append("already complete: " + ", ".join(self.skipped))
        return f"{'; '.join(parts) or 'nothing to do'} (under {self.root})"


Fetcher = Callable[..., bytes]


def git_blob_sha1(data: bytes) -> str:
    """The hash git gives this content, which is what Software Heritage publishes."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def manifest_digest(manifest: Mapping[str, str]) -> str:
    """A single digest over ``{filename: git blob hash}``, independent of ordering."""
    payload = json.dumps(dict(sorted(manifest.items())), separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def manifest_of(directory: Path | str) -> dict[str, str]:
    """Hash every match file in a directory. Missing directory reads as empty."""
    path = Path(directory)
    if not path.is_dir():
        return {}
    return {
        child.name: git_blob_sha1(child.read_bytes())
        for child in sorted(path.iterdir())
        if child.is_file() and _is_consumed(child.name)
    }


def verify(archive: PinnedArchive, root: Path | str) -> str | None:
    """``None`` if the corpus on disk is exactly what was pinned, else why it is not."""
    manifest = manifest_of(archive.target(Path(root)))
    if not manifest:
        return f"{archive.repo}: no match files present"
    if len(manifest) != archive.file_count:
        return (f"{archive.repo}: {len(manifest)} match files present, "
                f"{archive.file_count} pinned")
    found = manifest_digest(manifest)
    if found != archive.manifest_digest:
        return (f"{archive.repo}: content does not match the pinned digest "
                f"(found {found}, pinned {archive.manifest_digest})")
    return None


def _http(url: str, method: str = "GET") -> bytes:
    request = urllib.request.Request(url, method=method)
    request.add_header("Accept", "*/*")
    with urllib.request.urlopen(request, timeout=600) as response:  # noqa: S310 - https
        payload: bytes = response.read()
    return payload


def _safe_members(tar: tarfile.TarFile, archive: PinnedArchive) -> dict[str, bytes]:
    """Read the match files out of a cooked tarball, rejecting anything else.

    An archive fetched over the network is never handed to ``extractall``: a member is
    free to name ``../`` or an absolute path and write wherever the process can reach.
    Members are read by hand, and any name that is not a plain match-file basename inside
    the expected SWHID directory is a hard failure rather than a skip — a tarball shaped
    differently than expected is not one we should be quietly taking two files from.
    """
    contents: dict[str, bytes] = {}
    for member in tar.getmembers():
        name = member.name
        if name.startswith("/") or ".." in Path(name).parts:
            raise RestoreError(f"{archive.repo}: unsafe member in cooked archive: {name!r}")
        if not member.isfile():
            continue
        base = name.rsplit("/", 1)[-1]
        if not _is_consumed(base):
            continue
        if member.size > _MAX_MEMBER_BYTES:
            raise RestoreError(f"{archive.repo}: implausibly large member {base!r}")
        handle = tar.extractfile(member)
        if handle is None:  # pragma: no cover - isfile() already established this
            raise RestoreError(f"{archive.repo}: unreadable member {base!r}")
        contents[base] = handle.read()
    return contents


def _restore_one(archive: PinnedArchive, root: Path, fetch: Fetcher) -> None:
    fetch(archive.vault_url, "POST")          # cook; already-cooked returns done
    payload = fetch(archive.raw_url, "GET")

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tar:
        contents = _safe_members(tar, archive)

    manifest = {name: git_blob_sha1(data) for name, data in contents.items()}
    if len(manifest) != archive.file_count:
        raise RestoreError(
            f"{archive.repo}: cooked archive holds {len(manifest)} match files, "
            f"{archive.file_count} pinned — refusing to install a partial corpus"
        )
    found = manifest_digest(manifest)
    if found != archive.manifest_digest:
        raise RestoreError(
            f"{archive.repo}: content does not match the pinned digest "
            f"(found {found}, pinned {archive.manifest_digest})"
        )

    target = archive.target(root)
    target.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(contents.items()):
        (target / name).write_bytes(data)


def restore(
    root: Path | str | None = None,
    *,
    archives: tuple[PinnedArchive, ...] = PINNED,
    fetch: Fetcher = _http,
    force: bool = False,
) -> RestoreResult:
    """Restore any archive that is missing or does not verify.

    Verification decides, not the presence of files: a truncated or corrupted corpus is
    refetched. A corpus that already verifies costs zero requests, so a warm container
    re-running the weekly job does not re-download anything.
    """
    base = Path(root) if root is not None else default_root()
    result = RestoreResult(root=base)
    for archive in archives:
        if not force and verify(archive, base) is None:
            result.skipped.append(archive.repo)
            continue
        _restore_one(archive, base, fetch)
        problem = verify(archive, base)
        if problem is not None:  # pragma: no cover - _restore_one already verified
            raise RestoreError(problem)
        result.restored.append(archive.repo)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Restore the Sackmann match archive from Software Heritage. The "
                    "upstream GitHub repositories are deleted; this is the only route. "
                    "Data is CC BY-NC-SA 4.0 and is written outside the repository."
    )
    parser.add_argument("--root", default=None, help="where the corpus lives")
    parser.add_argument("--verify", action="store_true",
                        help="check the local corpus without fetching anything")
    parser.add_argument("--force", action="store_true",
                        help="refetch even if the local corpus already verifies")
    args = parser.parse_args(argv)
    base = Path(args.root) if args.root else default_root()

    if args.verify:
        problems = [p for p in (verify(a, base) for a in PINNED) if p is not None]
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            return 1
        print(f"all {len(PINNED)} archives verify against their pinned digests "
              f"({sum(a.file_count for a in PINNED):,} match files under {base})")
        return 0

    try:
        result = restore(base, force=args.force)
    except RestoreError as error:
        print(f"restore failed: {error}", file=sys.stderr)
        return 1
    print(result.report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
