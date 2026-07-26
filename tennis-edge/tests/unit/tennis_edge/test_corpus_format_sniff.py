"""The workbook reader is chosen by content, not by filename.

tennis-data.co.uk serves every year from a URL ending ``.xlsx``, but the 2002-2012 files
are legacy OLE2 workbooks. The downloader stores them under the name it fetched, so 17 of
the 45 files in a fresh vintage carry a suffix that lies about their format.

A loader that switched on the suffix therefore failed on the oldest third of the corpus. It
failed loudly, which was luck: a format mismatch that half-parsed would have silently
dropped a decade of matches from every fit downstream, and nothing would have said so.

These tests pin the decision to the bytes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tennis_edge.corpus import is_xlsx

#: A ZIP local-file header — the first four bytes of every real .xlsx.
ZIP_MAGIC = b"PK\x03\x04"
#: An OLE2 compound-document header — the first eight bytes of every legacy .xls.
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _write(tmp_path: Path, name: str, head: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(head + b"\x00" * 64)
    return path


class TestFormatIsDecidedByContent:
    def test_a_real_xlsx_is_recognised(self, tmp_path: Path) -> None:
        assert is_xlsx(_write(tmp_path, "atp-2024.xlsx", ZIP_MAGIC))

    def test_a_legacy_xls_is_recognised(self, tmp_path: Path) -> None:
        assert not is_xlsx(_write(tmp_path, "atp-2004.xls", OLE2_MAGIC))

    def test_an_ole2_file_named_xlsx_is_still_ole2(self, tmp_path: Path) -> None:
        """The case that actually occurs: the provider's own naming is wrong."""
        assert not is_xlsx(_write(tmp_path, "atp-2004.xlsx", OLE2_MAGIC))

    def test_a_zip_named_xls_is_still_a_zip(self, tmp_path: Path) -> None:
        """The mirror image, so the check cannot be passing by accident on the suffix."""
        assert is_xlsx(_write(tmp_path, "atp-2024.xls", ZIP_MAGIC))

    def test_neither_format_is_claimed_for_something_else(self, tmp_path: Path) -> None:
        """An HTML error page saved by a failed download must not read as a workbook."""
        assert not is_xlsx(_write(tmp_path, "atp-2024.xlsx", b"<!DO"))

    def test_a_file_shorter_than_the_magic_does_not_raise(self, tmp_path: Path) -> None:
        path = tmp_path / "truncated.xlsx"
        path.write_bytes(b"PK")
        assert not is_xlsx(path)

    def test_an_empty_file_does_not_raise(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.xlsx"
        path.write_bytes(b"")
        assert not is_xlsx(path)

    def test_a_missing_file_raises_rather_than_guessing(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            is_xlsx(tmp_path / "absent.xlsx")
