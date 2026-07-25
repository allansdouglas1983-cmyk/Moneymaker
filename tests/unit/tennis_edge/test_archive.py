"""Restoring the Sackmann archive from Software Heritage.

The upstream repositories are deleted, so this restore path is the only way the corpus
exists at all. It therefore has to be verifiable rather than merely convenient: the tests
below pin the integrity check, the extraction safety rules, and the refusal to accept a
corpus that does not hash to what was pinned.
"""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from tennis_edge.archive import (
    PINNED,
    PinnedArchive,
    RestoreError,
    git_blob_sha1,
    manifest_digest,
    manifest_of,
    restore,
    verify,
)


def _tarball(entries: dict[str, bytes], *, prefix: str) -> bytes:
    """A Software-Heritage-shaped flat tarball: every member under one SWHID directory."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, payload in entries.items():
            info = tarfile.TarInfo(f"{prefix}/{name}")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


_FILES = {
    "atp_matches_2003.csv": b"a,b\n1,2\n",
    "atp_matches_qual_chall_2003.csv": b"a,b\n3,4\n",
    "README.md": b"not a match file\n",
    "atp_matches_doubles_2003.csv": b"a,b\n5,6\n",
}
_WANTED = {"atp_matches_2003.csv", "atp_matches_qual_chall_2003.csv"}


def _pinned(entries: dict[str, bytes] | None = None) -> PinnedArchive:
    kept = {k: v for k, v in (entries or _FILES).items() if k in _WANTED}
    return PinnedArchive(
        repo="tennis_atp", tour="atp", visit_date="2026-05-08",
        snapshot="0" * 40, revision="1" * 40, directory="2" * 40,
        file_count=len(kept),
        manifest_digest=manifest_digest({k: git_blob_sha1(v) for k, v in kept.items()}),
    )


def _fetcher(payload: bytes, *, calls: list[str] | None = None):
    def fetch(url: str, method: str = "GET") -> bytes:
        if calls is not None:
            calls.append(f"{method} {url}")
        if method == "POST":
            return b'{"status":"done"}'
        return payload
    return fetch


# ------------------------------------------------------------------- hashing


def test_git_blob_hashing_matches_git() -> None:
    """The archive is verified against the hashes Software Heritage publishes, which are
    git blob hashes — so this must agree with git itself, not merely with itself."""
    assert git_blob_sha1(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    assert git_blob_sha1(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_the_manifest_digest_ignores_insertion_order() -> None:
    assert manifest_digest({"a": "1", "b": "2"}) == manifest_digest({"b": "2", "a": "1"})


def test_the_manifest_digest_changes_when_a_file_changes() -> None:
    assert manifest_digest({"a": "1"}) != manifest_digest({"a": "2"})


# ------------------------------------------------------------------- pinning


def test_both_deleted_repositories_are_pinned() -> None:
    """Pinned, not resolved live: the repos are gone, so there is no newer good visit to
    find, and pinning is what keeps the corpus reproducible under a frozen policy."""
    assert {a.repo for a in PINNED} == {"tennis_atp", "tennis_wta"}
    for archive in PINNED:
        assert len(archive.directory) == 40 and len(archive.snapshot) == 40
        assert archive.manifest_digest.startswith("sha256:")
        assert archive.file_count > 0
        assert archive.swhid == f"swh:1:dir:{archive.directory}"


def test_the_pinned_coverage_asymmetry_is_recorded() -> None:
    """ATP runs to May 2026 and WTA only to January 2025 because that is when each repo
    was last archived. The asymmetry is real and any split has to respect it."""
    by_repo = {a.repo: a for a in PINNED}
    assert by_repo["tennis_atp"].visit_date == "2026-05-08"
    assert by_repo["tennis_wta"].visit_date == "2025-01-03"


# ------------------------------------------------------------------- restore


def test_restore_writes_only_match_files(tmp_path: Path) -> None:
    archive = _pinned()
    restore(tmp_path, archives=(archive,), fetch=_fetcher(_tarball(_FILES, prefix=archive.swhid)))
    written = {p.name for p in (tmp_path / "tennis_atp").iterdir()}
    assert written == _WANTED, "README and doubles are not part of the consumed corpus"


def test_restore_verifies_what_it_wrote(tmp_path: Path) -> None:
    archive = _pinned()
    result = restore(tmp_path, archives=(archive,),
                     fetch=_fetcher(_tarball(_FILES, prefix=archive.swhid)))
    assert result.restored == [archive.repo] and result.skipped == []
    assert verify(archive, tmp_path) is None


def test_a_tampered_archive_is_refused(tmp_path: Path) -> None:
    """The whole point of pinning a digest: content that is not what was pinned must not
    become the corpus, however plausible it looks."""
    archive = _pinned()
    tampered = dict(_FILES)
    tampered["atp_matches_2003.csv"] = b"a,b\n9,9\n"
    with pytest.raises(RestoreError, match="does not match the pinned digest"):
        restore(tmp_path, archives=(archive,),
                fetch=_fetcher(_tarball(tampered, prefix=archive.swhid)))


def test_a_short_archive_is_refused(tmp_path: Path) -> None:
    archive = _pinned()
    short = {k: v for k, v in _FILES.items() if k != "atp_matches_2003.csv"}
    with pytest.raises(RestoreError):
        restore(tmp_path, archives=(archive,),
                fetch=_fetcher(_tarball(short, prefix=archive.swhid)))


def test_a_member_escaping_the_directory_is_refused(tmp_path: Path) -> None:
    """Never extractall() an archive fetched over the network."""
    archive = _pinned()
    evil = _tarball({"../../escaped.csv": b"x"}, prefix=archive.swhid)
    with pytest.raises(RestoreError, match="unsafe member"):
        restore(tmp_path, archives=(archive,), fetch=_fetcher(evil))
    assert not (tmp_path.parent / "escaped.csv").exists()


def test_an_absolute_member_is_refused(tmp_path: Path) -> None:
    archive = _pinned()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        info = tarfile.TarInfo("/etc/passwd")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(RestoreError, match="unsafe member"):
        restore(tmp_path, archives=(archive,), fetch=_fetcher(buffer.getvalue()))


# ------------------------------------------------------------------- idempotency


def test_an_already_complete_corpus_is_not_refetched(tmp_path: Path) -> None:
    """A weekly job on a warm container must not re-download 88 MB to learn nothing."""
    archive = _pinned()
    payload = _tarball(_FILES, prefix=archive.swhid)
    restore(tmp_path, archives=(archive,), fetch=_fetcher(payload))

    calls: list[str] = []
    result = restore(tmp_path, archives=(archive,), fetch=_fetcher(payload, calls=calls))
    assert calls == [], "a verified corpus must cost zero requests"
    assert result.skipped == [archive.repo] and result.restored == []


def test_force_refetches_a_complete_corpus(tmp_path: Path) -> None:
    archive = _pinned()
    payload = _tarball(_FILES, prefix=archive.swhid)
    restore(tmp_path, archives=(archive,), fetch=_fetcher(payload))

    calls: list[str] = []
    result = restore(tmp_path, archives=(archive,), force=True,
                     fetch=_fetcher(payload, calls=calls))
    assert calls and result.restored == [archive.repo]


def test_a_corrupted_local_file_triggers_a_refetch(tmp_path: Path) -> None:
    """Verification is what decides, not the mere presence of files."""
    archive = _pinned()
    payload = _tarball(_FILES, prefix=archive.swhid)
    restore(tmp_path, archives=(archive,), fetch=_fetcher(payload))
    (tmp_path / "tennis_atp" / "atp_matches_2003.csv").write_bytes(b"corrupted\n")
    assert verify(archive, tmp_path) is not None

    result = restore(tmp_path, archives=(archive,), fetch=_fetcher(payload))
    assert result.restored == [archive.repo]
    assert verify(archive, tmp_path) is None


def test_manifest_of_a_missing_directory_is_empty(tmp_path: Path) -> None:
    assert manifest_of(tmp_path / "nope") == {}
