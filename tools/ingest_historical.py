# Intended repo path: tools/ingest_historical.py
"""Deterministic backfill-provenance ingestion of Betfair historical files (SPEC-023).

Local, offline, founder-run tool (docs/procurement/betfair-pilot-runbook.md §5; ADR 0015
addendum — no network, no cloud, no live account/state). Wraps each line of a purchased
Betfair historical Exchange-Stream file (bz2-compressed, one ``mcm`` JSON object per line) as a
``l0_raw.backfill.BackfillMarketRecord``: the payload bytes stored verbatim (SPEC-001 semantics
extended to the backfill path) and explicitly marked ``provenance="backfilled"`` with its true
publication time (SPEC-023) rather than any live-capture identity.

Design obligations enforced here (see the SPEC-023 test suite for the property-by-property
checks):

* **Manifest gate, fail closed.** Every file in ``--source-dir`` must appear in the sha256
  manifest with a matching digest, and the manifest must not reference a file that is not
  present. Any mismatch/missing/extra file refuses the *entire* run before a single data byte is
  parsed — ingestion never proceeds on an unverified corpus.
* **Content validation, fail closed.** Every line in every file must be valid JSON carrying a
  ``pt`` field. Any violation refuses the entire run, naming every offending file and line
  number found (not just the first).
* **No partial output.** Both gates run to completion — across every file — before
  ``--output-dir`` is touched. A refused run leaves no trace in ``--output-dir``.
* **Append-only output.** ``--output-dir`` must be empty (or absent) when the run starts; this
  tool never overwrites or updates a prior ingestion.
* **Order preservation.** Files are processed in sorted-name order; lines are stored in file
  order. Out-of-order ``pt`` values are preserved exactly as encountered — never sorted
  (SPEC-002 semantics: capture everything unmodified, including out-of-order).
* **Determinism.** Two runs over byte-identical inputs produce byte-identical records except for
  the two ingestion-clock fields (``ingested_at_utc``, ``ingested_at_monotonic_ns``) on
  ``BackfillProvenance``. The report's ``deterministic_content_digest`` is computed over every
  other field plus the payload bytes, so it is stable across repeated runs and changes if and
  only if the ingested content changes. See ``_deterministic_content_digest`` for the exact
  field list.

Manifest-path matching: the runbook's checksum step (§4) runs ``sha256sum`` from the *parent* of
the raw/ directory (``find raw -type f ... | xargs sha256sum``), so manifest entries look like
``raw/file1.bz2`` — one directory level above what ``--source-dir`` (``.../raw``) itself points
at. Matching is therefore done by **basename**, not full relative path: this is the one
deliberately loose part of an otherwise fail-closed gate, needed to make the manifest usable
regardless of which directory it was generated from. A basename collision between two distinct
manifest entries with different digests refuses the run outright (ambiguous, so refused).
"""
from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from l0_raw.backfill import (
    BACKFILL_RECORD_SCHEMA_VERSION,
    BackfillMarketRecord,
    BackfillProvenance,
    backfill_market_to_frame,
)
from l0_raw.records import sha256_hex
from l0_raw.store import AppendOnlyLog

TOOL_VERSION = "ingest-historical-v1"
_SUPPORTED_PROVENANCE = "backfilled"

_MANIFEST_LINE_RE = re.compile(r"^([0-9a-fA-F]{64})[ \t]+\*?(.+)$")


class IngestRefused(Exception):
    """Base class for every whole-run refusal (fail-closed: ingest nothing on any of these)."""


class InvalidProvenanceError(IngestRefused):
    """Raised when ``--provenance`` is anything other than the one v1-supported value."""


class OutputDirNotEmptyError(IngestRefused):
    """Raised when ``--output-dir`` already contains entries (append-only violation)."""


class ManifestError(IngestRefused):
    """Raised for any manifest-gate failure: unparseable manifest, missing file, extra file,
    or a digest mismatch. Carries every problem found, not just the first."""


class ContentValidationError(IngestRefused):
    """Raised when one or more lines fail JSON/``pt`` validation. Carries every offending
    file:line found across the whole corpus, not just the first."""


def _parse_manifest(text: str) -> dict[str, str]:
    """Parse a ``sha256sum``-format manifest into ``{basename: lowercase_hex_digest}``.

    Raises :class:`ManifestError` on any unparseable line, an empty manifest, or a basename
    referenced twice with two different digests (an unresolvable ambiguity).
    """
    entries: dict[str, str] = {}
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        match = _MANIFEST_LINE_RE.match(line)
        if match is None:
            raise ManifestError(
                f"manifest line {line_no} is not a valid sha256sum entry: {raw_line!r}"
            )
        digest = match.group(1).lower()
        path = match.group(2)
        name = PurePosixPath(path).name
        if not name:
            raise ManifestError(f"manifest line {line_no} has an empty file name: {raw_line!r}")
        if name in entries and entries[name] != digest:
            raise ManifestError(
                f"manifest lists conflicting digests for {name!r} (line {line_no}); "
                "basename collision cannot be resolved, refusing the run"
            )
        entries[name] = digest
    if not entries:
        raise ManifestError("manifest contains no entries")
    return entries


@dataclass(frozen=True)
class IngestReport:
    """The ingestion report: printed to stdout and written to ``report.json``."""

    files: int
    lines: int
    distinct_market_ids: list[str]
    min_pt: int | None
    max_pt: int | None
    per_file_line_counts: dict[str, int]
    deterministic_content_digest: str
    tool_version: str
    manifest_digest: str
    provenance: str

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "files": self.files,
            "lines": self.lines,
            "distinct_market_ids": self.distinct_market_ids,
            "min_pt": self.min_pt,
            "max_pt": self.max_pt,
            "per_file_line_counts": self.per_file_line_counts,
            "deterministic_content_digest": self.deterministic_content_digest,
            "tool_version": self.tool_version,
            "manifest_digest": self.manifest_digest,
            "provenance": self.provenance,
        }


def _deterministic_content_digest(records: Iterable[BackfillMarketRecord]) -> str:
    """SHA-256 over every field of every record EXCEPT the two ingestion-clock fields.

    Included (in this exact order, length-prefixed to avoid ambiguity): ``payload_bytes``,
    ``true_publication_time_ms``, ``checksum``, ``schema_version``, and from ``provenance``:
    ``provenance`` (the literal), ``source_file``, ``source_line``, ``source_file_sha256``,
    ``manifest_digest``, ``ingest_tool_version``.

    Excluded: ``provenance.ingested_at_utc`` and ``provenance.ingested_at_monotonic_ns`` — the
    only two fields that are facts about *when this tool happened to run* rather than facts
    about the ingested content. Two runs over identical inputs differ only in those two fields,
    so this digest is the same across both runs; changing any payload byte, any source line
    number, any source file's bytes, or the manifest changes the digest.
    """
    digest = hashlib.sha256()

    def _put_str(value: str) -> None:
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)

    def _put_int(value: int) -> None:
        digest.update(value.to_bytes(8, "big", signed=True))

    for rec in records:
        digest.update(len(rec.payload_bytes).to_bytes(8, "big"))
        digest.update(rec.payload_bytes)
        _put_int(rec.true_publication_time_ms)
        _put_str(rec.checksum)
        _put_str(rec.schema_version)
        prov = rec.provenance
        _put_str(prov.provenance)
        _put_str(prov.source_file)
        _put_int(prov.source_line)
        _put_str(prov.source_file_sha256)
        _put_str(prov.manifest_digest)
        _put_str(prov.ingest_tool_version)
    return digest.hexdigest()


def _extract_market_ids(message: dict[str, Any]) -> list[str]:
    mc = message.get("mc")
    if not isinstance(mc, list):
        return []
    return [str(entry["id"]) for entry in mc if isinstance(entry, dict) and "id" in entry]


def run_ingest(
    *, source_dir: Path, manifest: Path, output_dir: Path, provenance: str
) -> IngestReport:
    """Validate, then ingest, a Betfair historical corpus. Raises :class:`IngestRefused` on any
    fail-closed condition; on any refusal, ``output_dir`` is left exactly as it was found."""
    if provenance != _SUPPORTED_PROVENANCE:
        raise InvalidProvenanceError(
            f"unsupported --provenance {provenance!r}: v1 accepts only "
            f"{_SUPPORTED_PROVENANCE!r} (SPEC-023 forbids backfilled data from being marked, "
            "or mistaken for, a live capture)"
        )
    if not source_dir.is_dir():
        raise ManifestError(f"--source-dir does not exist or is not a directory: {source_dir}")
    if not manifest.is_file():
        raise ManifestError(f"--manifest does not exist or is not a file: {manifest}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise OutputDirNotEmptyError(
            "--output-dir is not empty; this tool is append-only and refuses to ingest into "
            f"pre-existing output: {output_dir}"
        )

    # --- 1. Manifest gate: verify every file BEFORE reading any content. ---
    manifest_bytes = manifest.read_bytes()
    manifest_digest = sha256_hex(manifest_bytes)
    manifest_entries = _parse_manifest(manifest_bytes.decode("utf-8"))

    source_files = sorted(
        (p for p in source_dir.iterdir() if p.is_file()), key=lambda p: p.name
    )
    source_names = {p.name for p in source_files}
    manifest_names = set(manifest_entries)

    problems: list[str] = []
    missing = sorted(manifest_names - source_names)
    if missing:
        problems.append(
            "file(s) listed in the manifest but absent from --source-dir: " + ", ".join(missing)
        )
    extra = sorted(source_names - manifest_names)
    if extra:
        problems.append(
            "file(s) present in --source-dir but absent from the manifest: " + ", ".join(extra)
        )

    file_hashes: dict[str, str] = {}
    for path in source_files:
        expected = manifest_entries.get(path.name)
        if expected is None:
            continue  # already reported as "extra" above
        actual = sha256_hex(path.read_bytes())
        file_hashes[path.name] = actual
        if actual != expected:
            problems.append(f"checksum mismatch for {path.name}: manifest={expected} actual={actual}")

    if problems:
        raise ManifestError(
            "manifest verification failed, refusing the entire run (nothing ingested): "
            + "; ".join(problems)
        )

    # --- 2. Content validation: every line in every file, before any output is written. ---
    ParsedLine = tuple[int, bytes, int, list[str]]  # (line_no, raw_bytes, pt_ms, market_ids)
    parsed: dict[str, list[ParsedLine]] = {}
    content_errors: list[str] = []

    for path in source_files:
        try:
            raw = bz2.decompress(path.read_bytes())
        except OSError as exc:
            content_errors.append(f"{path.name}: not a valid bz2 file: {exc}")
            continue
        lines = raw.split(b"\n")
        if lines and lines[-1] == b"":
            lines = lines[:-1]
        file_lines: list[ParsedLine] = []
        for line_no, line in enumerate(lines, start=1):
            try:
                message = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                content_errors.append(f"{path.name}:{line_no}: invalid JSON: {exc}")
                continue
            if not isinstance(message, dict) or "pt" not in message:
                content_errors.append(f"{path.name}:{line_no}: missing required 'pt' field")
                continue
            pt = message["pt"]
            if isinstance(pt, bool) or not isinstance(pt, (int, float)):
                content_errors.append(f"{path.name}:{line_no}: 'pt' is not numeric: {pt!r}")
                continue
            file_lines.append((line_no, line, int(pt), _extract_market_ids(message)))
        parsed[path.name] = file_lines

    if content_errors:
        raise ContentValidationError(
            "content validation failed, refusing the entire run (nothing ingested): "
            + "; ".join(content_errors)
        )

    # --- 3. Write output. Both gates passed for the whole corpus, so this is the only point
    #        at which --output-dir is touched. ---
    ingested_at_utc = datetime.now(timezone.utc)
    ingested_at_monotonic_ns = time.monotonic_ns()
    output_dir.mkdir(parents=True, exist_ok=True)

    total_lines = 0
    market_id_set: set[str] = set()
    min_pt: int | None = None
    max_pt: int | None = None
    per_file_counts: dict[str, int] = {}
    all_records: list[BackfillMarketRecord] = []

    for path in source_files:
        file_lines = parsed[path.name]
        log = AppendOnlyLog(output_dir / f"{path.name}.l0")
        count = 0
        for line_no, line, pt_ms, market_ids in file_lines:
            record = BackfillMarketRecord(
                payload_bytes=line,
                true_publication_time_ms=pt_ms,
                checksum=sha256_hex(line),
                schema_version=BACKFILL_RECORD_SCHEMA_VERSION,
                provenance=BackfillProvenance(
                    provenance="backfilled",
                    source_file=path.name,
                    source_line=line_no,
                    source_file_sha256=file_hashes[path.name],
                    manifest_digest=manifest_digest,
                    ingest_tool_version=TOOL_VERSION,
                    ingested_at_utc=ingested_at_utc,
                    ingested_at_monotonic_ns=ingested_at_monotonic_ns,
                ),
            )
            meta, frame_payload = backfill_market_to_frame(record)
            log.append(meta, frame_payload)
            all_records.append(record)
            count += 1
            total_lines += 1
            market_id_set.update(market_ids)
            min_pt = pt_ms if min_pt is None else min(min_pt, pt_ms)
            max_pt = pt_ms if max_pt is None else max(max_pt, pt_ms)
        per_file_counts[path.name] = count

    report = IngestReport(
        files=len(source_files),
        lines=total_lines,
        distinct_market_ids=sorted(market_id_set),
        min_pt=min_pt,
        max_pt=max_pt,
        per_file_line_counts=dict(sorted(per_file_counts.items())),
        deterministic_content_digest=_deterministic_content_digest(all_records),
        tool_version=TOOL_VERSION,
        manifest_digest=manifest_digest,
        provenance=_SUPPORTED_PROVENANCE,
    )
    (output_dir / "report.json").write_text(
        json.dumps(report.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="SPEC-023 backfill-provenance ingestion of Betfair historical files."
    )
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--provenance", required=True, type=str)
    args = parser.parse_args(argv)
    try:
        report = run_ingest(
            source_dir=args.source_dir,
            manifest=args.manifest,
            output_dir=args.output_dir,
            provenance=args.provenance,
        )
    except IngestRefused as exc:
        print(f"[ingest-historical] FAIL: {type(exc).__name__}: {exc}")
        return 1
    except OSError as exc:
        print(f"[ingest-historical] FAIL: OSError: {exc}")
        return 1
    print(json.dumps(report.to_json_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
