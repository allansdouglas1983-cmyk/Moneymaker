"""Property tests: SPEC-023 determinism of tools/ingest_historical.py over synthetic corpora.

CLAUDE.md rule: "Treat every surprisingly good backtest as a suspected bug" applies just as much
to plumbing determinism claims — the runbook (§5) promises "same input -> byte-identical output
+ ingestion report digest". These properties hold that promise to a generated range of synthetic
Exchange-Stream corpora, not just one hand-built fixture, so a determinism regression cannot hide
behind a lucky example.

All fixtures here are SYNTHETIC, built from the documented bz2/one-JSON-object-per-line mcm
shape (docs/procurement/betfair-pilot-runbook.md §5) — no real Betfair market data exists in
this repository.
"""
from __future__ import annotations

import bz2
import hashlib
import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tools import ingest_historical as ih

pytestmark = pytest.mark.spec("SPEC-023")


def _mcm_bytes(*, pt: int, market_id: str, selection_id: int, ltp: str) -> bytes:
    obj = {
        "op": "mcm",
        "clk": "AAAAAAAA",
        "pt": pt,
        "mc": [{"id": market_id, "rc": [{"id": selection_id, "ltp": ltp, "tv": "10"}]}],
    }
    return json.dumps(obj, separators=(",", ":")).encode("utf-8")


_line_strategy = st.builds(
    _mcm_bytes,
    pt=st.integers(min_value=1_600_000_000_000, max_value=1_800_000_000_000),
    market_id=st.from_regex(r"1\.[0-9]{6,9}", fullmatch=True),
    selection_id=st.integers(min_value=1, max_value=99_999_999),
    ltp=st.from_regex(r"[1-9]\.[0-9]{1,2}", fullmatch=True),
)

_corpus_strategy = st.dictionaries(
    keys=st.from_regex(r"[a-z][a-z0-9]{0,7}\.bz2", fullmatch=True),
    values=st.lists(_line_strategy, min_size=1, max_size=5),
    min_size=1,
    max_size=3,
)


def _build_corpus(root: Path, files: dict[str, list[bytes]]) -> tuple[Path, Path]:
    source_dir = root / "raw"
    source_dir.mkdir()
    compressed: dict[str, bytes] = {}
    for name, lines in files.items():
        raw = b"\n".join(lines) + b"\n"
        blob = bz2.compress(raw)
        (source_dir / name).write_bytes(blob)
        compressed[name] = blob
    manifest_text = "\n".join(
        f"{hashlib.sha256(blob).hexdigest()}  {name}" for name, blob in compressed.items()
    )
    manifest = root / "MANIFEST.sha256"
    manifest.write_text(manifest_text + "\n", encoding="utf-8")
    return source_dir, manifest


@settings(max_examples=40, deadline=None)
@given(files=_corpus_strategy)
def test_determinism_two_runs_same_digest(
    tmp_path_factory: pytest.TempPathFactory, files: dict[str, list[bytes]]
) -> None:
    root = tmp_path_factory.mktemp("ingest-props")
    source_dir, manifest = _build_corpus(root, files)

    report1 = ih.run_ingest(
        source_dir=source_dir, manifest=manifest, output_dir=root / "out1", provenance="backfilled"
    )
    report2 = ih.run_ingest(
        source_dir=source_dir, manifest=manifest, output_dir=root / "out2", provenance="backfilled"
    )

    assert report1.deterministic_content_digest == report2.deterministic_content_digest
    # Only the two ingestion-clock fields on each record may legitimately differ between runs;
    # the report itself carries none of them, so the whole report is reproducible byte-for-byte.
    assert report1.to_json_dict() == report2.to_json_dict()


@settings(max_examples=40, deadline=None)
@given(
    files=_corpus_strategy,
    flip_index=st.integers(min_value=0, max_value=2**16),
)
def test_determinism_digest_changes_on_any_payload_mutation(
    tmp_path_factory: pytest.TempPathFactory,
    files: dict[str, list[bytes]],
    flip_index: int,
) -> None:
    root = tmp_path_factory.mktemp("ingest-props-mut")
    source_dir, manifest = _build_corpus(root, files)
    baseline = ih.run_ingest(
        source_dir=source_dir, manifest=manifest, output_dir=root / "out1", provenance="backfilled"
    )

    # Mutate exactly one payload byte in one file, in a way that keeps every line valid JSON
    # with a numeric "pt" (append a harmless extra key so JSON stays parseable and pt survives).
    first_name = sorted(files)[0]
    mutated_files = dict(files)
    lines = list(mutated_files[first_name])
    idx = flip_index % len(lines)
    obj = json.loads(lines[idx])
    obj["_mutation_marker"] = flip_index
    lines[idx] = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    mutated_files[first_name] = lines

    root2 = tmp_path_factory.mktemp("ingest-props-mut2")
    source_dir2, manifest2 = _build_corpus(root2, mutated_files)
    mutated = ih.run_ingest(
        source_dir=source_dir2,
        manifest=manifest2,
        output_dir=root2 / "out2",
        provenance="backfilled",
    )

    assert baseline.deterministic_content_digest != mutated.deterministic_content_digest
