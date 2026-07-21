"""STAGE3-0003 §11/§12 — V0 import quarantine + cross-market audit view (data-only).

The assistant package must not import any execution layer (l5_decision / l5b_risk /
l6_broker / l7_settle) and its probability path must not import research.xmarket. The
cross-market audit view reads the FROZEN artifact as plain data (no research.xmarket import)
and is display-only.
"""
from __future__ import annotations

import ast
from pathlib import Path

from assistant_v0 import xmarket_audit_view as X

_PKG = Path(__file__).resolve().parents[3] / "assistant_v0"
_FORBIDDEN = ("l5_decision", "l5b_risk", "l6_broker", "l7_settle", "research.xmarket",
              "research/xmarket")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_execution_or_xmarket_import_anywhere_in_package() -> None:
    for py in _PKG.glob("*.py"):
        for imp in _imports(py):
            for bad in _FORBIDDEN:
                assert bad not in imp, f"{py.name} imports forbidden {imp!r}"


def test_no_network_or_credential_imports_in_package() -> None:
    # AST-based: the package imports no network/credential libraries. (Docstrings may SAY
    # "no credentials"; we check actual imports, not prose.)
    banned_imports = {"requests", "urllib", "urllib.request", "http", "http.client",
                      "socket", "ftplib", "smtplib", "keyring", "boto3", "paramiko"}
    for py in _PKG.glob("*.py"):
        for imp in _imports(py):
            top = imp.split(".")[0]
            assert imp not in banned_imports and top not in banned_imports, \
                f"{py.name} imports network/credential module {imp!r}"


def test_xmarket_view_absent_artifact_returns_none() -> None:
    assert X.load_xmarket_view("1.does-not-exist", records_path="/nonexistent/path.jsonl") is None


def test_xmarket_view_reads_frozen_artifact_as_data(tmp_path: Path) -> None:
    import json
    from typing import Any
    p = tmp_path / "records.jsonl"
    rec: dict[str, Any] = {"mo_market_id": "1.99", "cohort": "STRICT", "tour": "ATP",
           "total_games": {"exclusion_reason": None, "quote_age_seconds": 12.0,
                           "two_sided_line_count": 5, "min_spread_ticks": 3, "lines_offered": 55},
           "game_handicap": None, "linkage_anomalies": []}
    p.write_text(json.dumps(rec) + "\n")
    view = X.load_xmarket_view("1.99", records_path=str(p))
    assert view is not None
    assert view["total_games"]["present"] is True
    assert view["game_handicap"]["present"] is False
    assert view["cross_market_layer_status"] == "BLOCKED_EXTERNAL_FACTS"
    assert view["settlement_semantics_status"] == "UNRESOLVED"
