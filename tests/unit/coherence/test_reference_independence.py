"""STAGE3-0006 §6 — production/reference independence boundary.

The 1e-9 production-vs-reference agreement is only a real cross-check if the reference shares no
load-bearing logic with production. This test proves, by static import analysis, that
``reference.py`` imports NOTHING from the production logic modules (scoring / match / pmf / solver
/ holdout) and pulls from ``formats`` only the DATA contracts (the enums, FormatSpec and the
format-table accessor) — never the production branching helpers (set_tiebreak_target,
is_match_tiebreak_decider). So a mutation to any production helper cannot change the reference
path, and the agreement remains an independent check.
"""
from __future__ import annotations

import ast
from pathlib import Path

_REFERENCE = Path(__file__).resolve().parents[3] / "sport_tennis" / "coherence" / "reference.py"

# Production LOGIC modules the reference must never import from.
_FORBIDDEN_MODULES = {
    "sport_tennis.coherence.scoring",
    "sport_tennis.coherence.match",
    "sport_tennis.coherence.pmf",
    "sport_tennis.coherence.solver",
    "sport_tennis.coherence.holdout",
}
# From formats, only these DATA symbols are allowed (no production branching helpers).
_ALLOWED_FORMATS_NAMES = {"MatchFormat", "FinalSetRule", "FormatSpec", "format_spec"}
# Production logic symbol names that must not appear anywhere in the reference source.
_FORBIDDEN_SYMBOLS = {
    "tiebreak_server_is_first", "tiebreak_tail_servers", "_deuce_tail_first_win",
    "game_win_prob", "tiebreak_win_prob", "set_distribution", "check_normalized",
    "set_tiebreak_target", "is_match_tiebreak_decider", "set_is_terminal",
    "set_is_tiebreak_state", "set_game_server_is_first", "_expand_set_level",
    "game_is_win", "game_is_loss", "game_is_deuce",
    "tiebreak_is_win", "tiebreak_is_loss", "tiebreak_is_tail",
}


def _tree() -> ast.Module:
    return ast.parse(_REFERENCE.read_text(encoding="utf-8"))


def test_reference_imports_no_production_logic_module() -> None:
    for node in ast.walk(_tree()):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module not in _FORBIDDEN_MODULES, f"reference imports {node.module}"
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in _FORBIDDEN_MODULES, f"reference imports {alias.name}"


def test_reference_imports_only_data_from_formats() -> None:
    for node in ast.walk(_tree()):
        if isinstance(node, ast.ImportFrom) and node.module == "sport_tennis.coherence.formats":
            names = {a.name for a in node.names}
            extra = names - _ALLOWED_FORMATS_NAMES
            assert not extra, f"reference imports non-data symbols from formats: {extra}"


def test_reference_source_references_no_production_logic_symbol() -> None:
    # Belt and suspenders: no production logic symbol name appears anywhere (e.g. via a module
    # attribute) in the reference source.
    names_used = {n.id for n in ast.walk(_tree()) if isinstance(n, ast.Name)}
    attrs_used = {n.attr for n in ast.walk(_tree()) if isinstance(n, ast.Attribute)}
    leaked = (names_used | attrs_used) & _FORBIDDEN_SYMBOLS
    assert not leaked, f"reference references production logic symbols: {leaked}"
