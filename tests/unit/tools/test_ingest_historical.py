"""Unit tests for tools/ingest_historical.py (SPEC-023 backfill-provenance ingestion).

Betfair historical files are bz2-compressed, one Exchange-Stream ``mcm`` JSON object per line
(docs/procurement/betfair-pilot-runbook.md §5). These fixtures are entirely SYNTHETIC — built
from that documented shape, never real market data. The tool does not exist yet; every test in
this module is RED (``ModuleNotFoundError``) until ``tools/ingest_historical.py`` and its
``l0_raw.backfill`` sibling land.

SPEC-023: backfilled data does not confer historical validity merely because it was ingested at
some ingestion time; it must declare its true publication time (the ``pt`` field) and must be
marked ``provenance="backfilled"``, never passed off as live-captured.
"""
from __future__ import annotations

import bz2
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from l0_raw.backfill import BackfillMarketRecord
from l0_raw.store import AppendOnlyLog
from tools import ingest_historical as ih

pytestmark = pytest.mark.spec("SPEC-023")


# --------------------------------------------------------------------------------------
# Fixture helpers — build SYNTHETIC Exchange-Stream mcm lines and a real sha256 manifest.
# --------------------------------------------------------------------------------------


def _mcm_line(
    *, pt: int, market_id: str = "1.123456789", extra: dict[str, Any] | None = None
) -> bytes:
    """One synthetic mcm JSON line, encoded exactly as it will be written to a fixture file."""
    obj: dict[str, Any] = {
        "op": "mcm",
        "clk": "AAAAAAAA",
        "pt": pt,
        "mc": [
            {
                "id": market_id,
                "rc": [{"id": 1001, "ltp": 2.5, "tv": 100}],
            }
        ],
    }
    if extra:
        obj.update(extra)
    return json.dumps(obj, separators=(",", ":")).encode("utf-8")


def _write_bz2(path: Path, lines: list[bytes]) -> bytes:
    """Write ``lines`` newline-joined and bz2-compressed; return the compressed bytes."""
    raw = b"\n".join(lines) + b"\n"
    compressed = bz2.compress(raw)
    path.write_bytes(compressed)
    return compressed


def _manifest_from(files: dict[str, bytes]) -> str:
    """Build sha256sum-format manifest text (as ``find | xargs sha256sum`` would produce)."""
    lines = []
    for name, compressed in files.items():
        digest = hashlib.sha256(compressed).hexdigest()
        lines.append(f"{digest}  {name}")
    return "\n".join(lines) + "\n"


def _corpus(tmp_path: Path, files: dict[str, list[bytes]], *, name: str = "raw") -> tuple[Path, Path]:
    """Build a source-dir + manifest for ``{filename: [mcm_line, ...]}``. Returns (source_dir, manifest).

    ``name`` distinguishes independent corpora built under the same ``tmp_path`` (e.g. a
    baseline and a mutated variant in the same test) so their source-dirs never collide.
    """
    source_dir = tmp_path / name
    source_dir.mkdir()
    compressed_by_name: dict[str, bytes] = {}
    for filename, lines in files.items():
        compressed_by_name[filename] = _write_bz2(source_dir / filename, lines)
    manifest = tmp_path / f"{name}-MANIFEST.sha256"
    manifest.write_text(_manifest_from(compressed_by_name), encoding="utf-8")
    return source_dir, manifest


def _read_output_records(output_dir: Path, filename: str) -> list[BackfillMarketRecord]:
    from l0_raw.backfill import decode_backfill

    log = AppendOnlyLog(output_dir / f"{filename}.l0")
    return [decode_backfill(meta, payload) for meta, payload in log.read()]


# --------------------------------------------------------------------------------------
# CLI provenance gate
# --------------------------------------------------------------------------------------


def test_provenance_live_refused(tmp_path: Path) -> None:
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [_mcm_line(pt=1000)]})
    output_dir = tmp_path / "out"
    rc = ih.main(
        [
            "--source-dir",
            str(source_dir),
            "--manifest",
            str(manifest),
            "--output-dir",
            str(output_dir),
            "--provenance",
            "live",
        ]
    )
    assert rc != 0
    assert not output_dir.exists() or not any(output_dir.iterdir())


def test_run_ingest_rejects_provenance_other_than_backfilled(tmp_path: Path) -> None:
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [_mcm_line(pt=1000)]})
    with pytest.raises(ih.InvalidProvenanceError):
        ih.run_ingest(
            source_dir=source_dir,
            manifest=manifest,
            output_dir=tmp_path / "out",
            provenance="live",
        )


# --------------------------------------------------------------------------------------
# Manifest gate: fail closed, refuse-all, no partial output
# --------------------------------------------------------------------------------------


def test_missing_file_in_source_dir_refuses_whole_run(tmp_path: Path) -> None:
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [_mcm_line(pt=1000)]})
    # Delete the file the manifest still references.
    (source_dir / "m1.bz2").unlink()
    output_dir = tmp_path / "out"
    with pytest.raises(ih.ManifestError):
        ih.run_ingest(
            source_dir=source_dir, manifest=manifest, output_dir=output_dir, provenance="backfilled"
        )
    assert not output_dir.exists()


def test_wrong_digest_refuses_whole_run(tmp_path: Path) -> None:
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [_mcm_line(pt=1000)]})
    # Corrupt the file after the manifest was computed from the original bytes.
    (source_dir / "m1.bz2").write_bytes(bz2.compress(b'{"op":"mcm","pt":9999,"mc":[]}\n'))
    output_dir = tmp_path / "out"
    with pytest.raises(ih.ManifestError, match="checksum mismatch"):
        ih.run_ingest(
            source_dir=source_dir, manifest=manifest, output_dir=output_dir, provenance="backfilled"
        )
    assert not output_dir.exists()


def test_extra_unmanifested_file_refuses_whole_run(tmp_path: Path) -> None:
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [_mcm_line(pt=1000)]})
    _write_bz2(source_dir / "m2.bz2", [_mcm_line(pt=2000)])  # not in manifest
    output_dir = tmp_path / "out"
    with pytest.raises(ih.ManifestError, match="m2.bz2"):
        ih.run_ingest(
            source_dir=source_dir, manifest=manifest, output_dir=output_dir, provenance="backfilled"
        )
    assert not output_dir.exists()


def test_manifest_gate_failure_leaves_empty_output_dir_if_preexisting(tmp_path: Path) -> None:
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [_mcm_line(pt=1000)]})
    (source_dir / "m1.bz2").unlink()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    with pytest.raises(ih.ManifestError):
        ih.run_ingest(
            source_dir=source_dir, manifest=manifest, output_dir=output_dir, provenance="backfilled"
        )
    assert list(output_dir.iterdir()) == []


# --------------------------------------------------------------------------------------
# Output-dir append-only gate
# --------------------------------------------------------------------------------------


def test_non_empty_output_dir_refused(tmp_path: Path) -> None:
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [_mcm_line(pt=1000)]})
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "leftover.txt").write_text("stale", encoding="utf-8")
    with pytest.raises(ih.OutputDirNotEmptyError):
        ih.run_ingest(
            source_dir=source_dir, manifest=manifest, output_dir=output_dir, provenance="backfilled"
        )
    # Refusal must not touch pre-existing content.
    assert (output_dir / "leftover.txt").read_text(encoding="utf-8") == "stale"


# --------------------------------------------------------------------------------------
# Content validation: invalid JSON / missing pt -> whole-run refusal naming file + line
# --------------------------------------------------------------------------------------


def test_invalid_json_line_refuses_whole_run_naming_file_and_line(tmp_path: Path) -> None:
    lines = [_mcm_line(pt=1000), b"{not valid json", _mcm_line(pt=1002)]
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": lines})
    output_dir = tmp_path / "out"
    with pytest.raises(ih.ContentValidationError, match=r"m1\.bz2:2") as exc_info:
        ih.run_ingest(
            source_dir=source_dir, manifest=manifest, output_dir=output_dir, provenance="backfilled"
        )
    assert not output_dir.exists()
    assert "m1.bz2:2" in str(exc_info.value)


def test_missing_pt_field_refuses_whole_run(tmp_path: Path) -> None:
    bad_line = json.dumps({"op": "mcm", "mc": []}, separators=(",", ":")).encode("utf-8")
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [_mcm_line(pt=1000), bad_line]})
    output_dir = tmp_path / "out"
    with pytest.raises(ih.ContentValidationError, match=r"m1\.bz2:2"):
        ih.run_ingest(
            source_dir=source_dir, manifest=manifest, output_dir=output_dir, provenance="backfilled"
        )
    assert not output_dir.exists()


def test_multiple_errors_across_files_all_reported(tmp_path: Path) -> None:
    source_dir, manifest = _corpus(
        tmp_path,
        {
            "m1.bz2": [_mcm_line(pt=1000), b"not json at all"],
            "m2.bz2": [b"{}"],
        },
    )
    with pytest.raises(ih.ContentValidationError) as exc_info:
        ih.run_ingest(
            source_dir=source_dir,
            manifest=manifest,
            output_dir=tmp_path / "out",
            provenance="backfilled",
        )
    message = str(exc_info.value)
    assert "m1.bz2:2" in message
    assert "m2.bz2:1" in message


# --------------------------------------------------------------------------------------
# Byte-exact payload preservation
# --------------------------------------------------------------------------------------


def test_payload_bytes_survive_exactly_weird_key_order_unicode_duplicate_keys(tmp_path: Path) -> None:
    # Hand-built line (NOT produced via _mcm_line/json.dumps) so we control the exact bytes:
    # unusual key order, a non-ASCII value, and a duplicate "pt" key.
    weird_line = (
        b'{"mc":[{"id":"1.999","rc":[]}],"note":"caf\xc3\xa9 \xe2\x98\x95",'
        b'"pt":555,"pt":555,"op":"mcm"}'
    )
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [weird_line]})
    output_dir = tmp_path / "out"
    ih.run_ingest(
        source_dir=source_dir, manifest=manifest, output_dir=output_dir, provenance="backfilled"
    )
    records = _read_output_records(output_dir, "m1.bz2")
    assert len(records) == 1
    assert records[0].payload_bytes == weird_line
    assert records[0].checksum == hashlib.sha256(weird_line).hexdigest()


# --------------------------------------------------------------------------------------
# Order preservation: out-of-order pt values, never sorted
# --------------------------------------------------------------------------------------


def test_out_of_order_pt_preserved_never_sorted(tmp_path: Path) -> None:
    lines = [_mcm_line(pt=5000), _mcm_line(pt=1000), _mcm_line(pt=3000)]
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": lines})
    output_dir = tmp_path / "out"
    report = ih.run_ingest(
        source_dir=source_dir, manifest=manifest, output_dir=output_dir, provenance="backfilled"
    )
    records = _read_output_records(output_dir, "m1.bz2")
    assert [r.true_publication_time_ms for r in records] == [5000, 1000, 3000]
    assert report.min_pt == 1000
    assert report.max_pt == 5000


# --------------------------------------------------------------------------------------
# Provenance fields present with backfilled marker
# --------------------------------------------------------------------------------------


def test_provenance_fields_present_and_marked_backfilled(tmp_path: Path) -> None:
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [_mcm_line(pt=1000)]})
    output_dir = tmp_path / "out"
    ih.run_ingest(
        source_dir=source_dir, manifest=manifest, output_dir=output_dir, provenance="backfilled"
    )
    (record,) = _read_output_records(output_dir, "m1.bz2")
    prov = record.provenance
    assert prov.provenance == "backfilled"
    assert prov.source_file == "m1.bz2"
    assert prov.source_line == 1
    assert prov.source_file_sha256 == hashlib.sha256((source_dir / "m1.bz2").read_bytes()).hexdigest()
    assert prov.manifest_digest == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert prov.ingest_tool_version == "ingest-historical-v1"
    assert record.true_publication_time_ms == 1000
    # Ingestion clocks are ingestion-time facts, distinct from the true publication time.
    assert prov.ingested_at_utc is not None
    assert isinstance(prov.ingested_at_monotonic_ns, int)


# --------------------------------------------------------------------------------------
# Report counts correct on a hand-built fixture
# --------------------------------------------------------------------------------------


def test_report_counts_correct(tmp_path: Path) -> None:
    source_dir, manifest = _corpus(
        tmp_path,
        {
            "a.bz2": [_mcm_line(pt=100, market_id="1.111"), _mcm_line(pt=200, market_id="1.111")],
            "b.bz2": [_mcm_line(pt=50, market_id="1.222")],
        },
    )
    output_dir = tmp_path / "out"
    report = ih.run_ingest(
        source_dir=source_dir, manifest=manifest, output_dir=output_dir, provenance="backfilled"
    )
    assert report.files == 2
    assert report.lines == 3
    assert report.distinct_market_ids == ["1.111", "1.222"]
    assert report.min_pt == 50
    assert report.max_pt == 200
    assert report.per_file_line_counts == {"a.bz2": 2, "b.bz2": 1}
    assert report.tool_version == "ingest-historical-v1"
    assert report.provenance == "backfilled"
    # report.json on disk matches the returned report.
    on_disk = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert on_disk == report.to_json_dict()


def test_main_prints_report_json_to_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [_mcm_line(pt=1000)]})
    output_dir = tmp_path / "out"
    rc = ih.main(
        [
            "--source-dir",
            str(source_dir),
            "--manifest",
            str(manifest),
            "--output-dir",
            str(output_dir),
            "--provenance",
            "backfilled",
        ]
    )
    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["lines"] == 1
    assert printed["provenance"] == "backfilled"


# --------------------------------------------------------------------------------------
# Determinism: same inputs -> identical deterministic-content digest across two runs
# --------------------------------------------------------------------------------------


def test_determinism_same_inputs_same_digest_across_two_runs(tmp_path: Path) -> None:
    lines = [_mcm_line(pt=1000), _mcm_line(pt=999), _mcm_line(pt=1005)]
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": lines})

    report1 = ih.run_ingest(
        source_dir=source_dir, manifest=manifest, output_dir=tmp_path / "out1", provenance="backfilled"
    )
    report2 = ih.run_ingest(
        source_dir=source_dir, manifest=manifest, output_dir=tmp_path / "out2", provenance="backfilled"
    )
    assert report1.deterministic_content_digest == report2.deterministic_content_digest
    # The whole report is otherwise free of ingestion-clock fields, so it is fully identical.
    assert report1.to_json_dict() == report2.to_json_dict()


def test_determinism_digest_changes_if_payload_byte_changes(tmp_path: Path) -> None:
    source_dir, manifest = _corpus(tmp_path, {"m1.bz2": [_mcm_line(pt=1000)]})
    report1 = ih.run_ingest(
        source_dir=source_dir, manifest=manifest, output_dir=tmp_path / "out1", provenance="backfilled"
    )

    source_dir2, manifest2 = _corpus(
        tmp_path, {"m1.bz2": [_mcm_line(pt=1000, market_id="1.999999")]}, name="raw2"
    )
    report2 = ih.run_ingest(
        source_dir=source_dir2,
        manifest=manifest2,
        output_dir=tmp_path / "out2",
        provenance="backfilled",
    )
    assert report1.deterministic_content_digest != report2.deterministic_content_digest
