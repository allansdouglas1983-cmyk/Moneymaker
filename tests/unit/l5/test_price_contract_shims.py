"""ADR 0013 addendum: price_contracts/ is the SOLE authoritative implementation of the
three price types and the canonical ladder. The l5_decision shims are pure re-exports —
this test refuses any shim that acquires independent logic (a function, class, constant
or expression of its own), and proves class identity is preserved across both paths.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

pytestmark = pytest.mark.spec("SPEC-051")

_SHIMS = ("l5_decision/prices.py", "l5_decision/ladder.py")
_REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("shim", _SHIMS)
def test_shim_contains_only_reexports(shim: str) -> None:
    tree = ast.parse((_REPO / shim).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # module docstring
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
            "price_contracts"
        ):
            continue
        pytest.fail(
            f"{shim} must contain only a docstring and price_contracts re-exports; "
            f"found {ast.dump(node)[:80]}"
        )


def test_shim_classes_are_identical_objects() -> None:
    import l5_decision.ladder as shim_ladder
    import l5_decision.prices as shim_prices
    import price_contracts.ladder as real_ladder
    import price_contracts.prices as real_prices

    assert shim_prices.OddsExec is real_prices.OddsExec
    assert shim_prices.MarketInfoPrice is real_prices.MarketInfoPrice
    assert shim_prices.ClosePrice is real_prices.ClosePrice
    assert shim_ladder.LADDER is real_ladder.LADDER
    assert shim_ladder.index_of is real_ladder.index_of


def test_authoritative_types_are_defined_in_price_contracts() -> None:
    from l5_decision.prices import MarketInfoPrice

    assert inspect.getmodule(MarketInfoPrice).__name__ == "price_contracts.prices"  # type: ignore[union-attr]
