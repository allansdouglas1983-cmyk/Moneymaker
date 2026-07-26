"""STAGE3-0006C-D-A3 §13/§14 — independent-reference agreement + architecture boundary.

Compares the production ``compare_registered_variants`` (discretisation-stability comparator)
against the brute-force literal reference (``stability_reference``) over:

- every named contract-fixture shape exercised by ``test_discretisation_stability.py`` (root
  count / status / location-absent / location-ambiguous / boundary / mirror disagreement,
  all-NON_IDENTIFIABLE, all-NO_ROOT, a stable mirror pair, permuted-root variants);
- a deterministic seeded sweep of ~200 generated snapshot trios.

A disagreement between production and the reference is a potential production defect and is
reported, never silently reconciled by editing the reference.

The reference module must import NOTHING outside a stdlib allowlist (AST-enforced here) --
proven independent so the cross-check is a real one.
"""
from __future__ import annotations

import ast
import random
from pathlib import Path

from sport_tennis.coherence.discretisation_stability import (
    VariantSolveSnapshot,
    compare_registered_variants,
)
from sport_tennis.coherence.scan_variants import (
    REGISTERED_VARIANT_ORDER,
    ScanVariant,
    axis_digest,
    variant_axis,
)
from sport_tennis.coherence.solver import Root
from sport_tennis.coherence.solver_contracts import ParameterDomain

from . import stability_reference as ref

_LO, _HI = 0.35, 0.90
_TOL = 1e-3
_DOMAIN = ParameterDomain.from_symmetric(_LO, _HI)
_AXIS_DIGEST = {v: axis_digest(tuple(variant_axis(v, _LO, _HI))) for v in ScanVariant}

# rows = one (status, [(p_a, p_b, on_boundary), ...]) tuple per registered variant, in order.
_Row = tuple[str, list[tuple[float, float, bool]]]


def _prod_snapshot(variant: ScanVariant, row: _Row, a_first: bool) -> VariantSolveSnapshot:
    status, root_specs = row
    roots = tuple(
        Root(p_a=pa, p_b=pb, a_serves_first=a_first, residual=1e-5, jacobian_det=1.0,
             on_boundary=boundary)
        for pa, pb, boundary in root_specs
    )
    return VariantSolveSnapshot(variant=variant, a_serves_first=a_first, status=status,
                                roots=roots, axis_digest=_AXIS_DIGEST[variant])


def _ref_snapshot(row: _Row) -> dict[str, object]:
    status, root_specs = row
    return {
        "status": status,
        "roots": [{"p_a": pa, "p_b": pb, "on_boundary": boundary}
                  for pa, pb, boundary in root_specs],
    }


def _compare(rows: list[_Row], a_first: bool = True) -> tuple[bool, bool]:
    """Returns (production_stable, reference_stable) for the same trio built two ways."""
    assert len(rows) == 3
    prod_snaps = tuple(_prod_snapshot(v, row, a_first)
                        for v, row in zip(REGISTERED_VARIANT_ORDER, rows))
    prod = compare_registered_variants(prod_snaps, domain=_DOMAIN, tolerance=_TOL)
    ref_snaps = [_ref_snapshot(row) for row in rows]
    ref_result = ref.compare_stability(ref_snaps, domain=(_LO, _HI), tolerance=_TOL)
    return prod.stable, ref_result["stable"]


# ---------------------------------------------------------------- named contract-fixture shapes
def test_root_count_disagreement_agrees_unstable() -> None:
    two = [(0.40, 0.40, False), (0.60, 0.60, False)]
    three = [(0.40, 0.40, False), (0.50, 0.50, False), (0.60, 0.60, False)]
    prod, reference = _compare([
        ("MULTIPLE_ROOTS", two), ("MULTIPLE_ROOTS", three), ("MULTIPLE_ROOTS", two)])
    assert prod is False and reference is False


def test_status_disagreement_agrees_unstable() -> None:
    single = [(0.62, 0.62, False)]
    prod, reference = _compare([
        ("IDENTIFIED", single), ("NO_ROOT", []), ("IDENTIFIED", single)])
    assert prod is False and reference is False


def test_no_root_mixture_agrees_unstable() -> None:
    two = [(0.40, 0.40, False), (0.60, 0.60, False)]
    prod, reference = _compare([
        ("MULTIPLE_ROOTS", two), ("NO_ROOT", []), ("NO_ROOT", [])])
    assert prod is False and reference is False


def test_location_matching_absent_agrees_unstable() -> None:
    base = [(0.40, 0.40, False), (0.60, 0.60, False)]
    moved = [(0.40, 0.40, False), (0.61, 0.61, False)]
    prod, reference = _compare([
        ("MULTIPLE_ROOTS", base), ("MULTIPLE_ROOTS", moved), ("MULTIPLE_ROOTS", base)])
    assert prod is False and reference is False


def test_location_matching_ambiguous_agrees_unstable() -> None:
    left = [(0.5000, 0.5000, False), (0.5005, 0.5005, False)]
    right = [(0.50025, 0.50025, False), (0.50075, 0.50075, False)]
    prod, reference = _compare([
        ("MULTIPLE_ROOTS", left), ("MULTIPLE_ROOTS", right), ("MULTIPLE_ROOTS", left)])
    assert prod is False and reference is False


def test_boundary_flag_disagreement_agrees_unstable() -> None:
    plain = [(0.62, 0.62, False)]
    flagged = [(0.62, 0.62, True)]
    prod, reference = _compare([
        ("IDENTIFIED", plain), ("IDENTIFIED", flagged), ("IDENTIFIED", plain)])
    assert prod is False and reference is False


def test_mirror_relation_disagreement_agrees_unstable() -> None:
    mirror = [(0.40, 0.40, False), (0.60, 0.60, False)]
    drifted = [(0.4008, 0.4008, False), (0.6008, 0.6008, False)]
    prod, reference = _compare([
        ("MULTIPLE_ROOTS", mirror), ("MULTIPLE_ROOTS", drifted), ("MULTIPLE_ROOTS", mirror)])
    assert prod is False and reference is False


def test_all_non_identifiable_agrees_stable() -> None:
    prod, reference = _compare([
        ("NON_IDENTIFIABLE", [(0.78, 0.50, False)]),
        ("NON_IDENTIFIABLE", []),
        ("NON_IDENTIFIABLE", [(0.7805, 0.5002, False)])])
    assert prod is True and reference is True


def test_all_no_root_agrees_stable() -> None:
    prod, reference = _compare([("NO_ROOT", []), ("NO_ROOT", []), ("NO_ROOT", [])])
    assert prod is True and reference is True


def test_stable_mirror_pair_agrees_stable() -> None:
    prod, reference = _compare([
        ("MULTIPLE_ROOTS", [(0.40, 0.40, False), (0.60, 0.60, False)]),
        ("MULTIPLE_ROOTS", [(0.3999, 0.3999, False), (0.5999, 0.5999, False)]),
        ("MULTIPLE_ROOTS", [(0.4001, 0.4001, False), (0.6001, 0.6001, False)])])
    assert prod is True and reference is True


def test_permuted_root_variants_agree_and_are_order_invariant() -> None:
    rows: list[_Row] = [
        ("MULTIPLE_ROOTS", [(0.40, 0.40, False), (0.60, 0.60, False)]),
        ("MULTIPLE_ROOTS", [(0.3999, 0.3999, False), (0.5999, 0.5999, False)]),
        ("MULTIPLE_ROOTS", [(0.4001, 0.4001, False), (0.6001, 0.6001, False)])]
    prod, reference = _compare(rows)
    assert prod is True and reference is True
    reversed_rows: list[_Row] = [(status, list(reversed(specs))) for status, specs in rows]
    prod_rev, reference_rev = _compare(reversed_rows)
    assert (prod_rev, reference_rev) == (prod, reference)

    unstable_rows: list[_Row] = [
        ("MULTIPLE_ROOTS", [(0.40, 0.40, False), (0.60, 0.60, False)]),
        ("MULTIPLE_ROOTS", [(0.40, 0.40, False), (0.61, 0.61, False)]),
        ("MULTIPLE_ROOTS", [(0.40, 0.40, False), (0.60, 0.60, False)])]
    prod_u, reference_u = _compare(unstable_rows)
    assert prod_u is False and reference_u is False
    reversed_unstable: list[_Row] = [(status, list(reversed(specs)))
                                     for status, specs in unstable_rows]
    prod_u_rev, reference_u_rev = _compare(reversed_unstable)
    assert (prod_u_rev, reference_u_rev) == (prod_u, reference_u)


# ---------------------------------------------------------------- deterministic seeded sweep
_LATTICE = [round(_LO + i * 0.0004, 4) for i in range(int(round((_HI - _LO) / 0.0004)) + 1)]


def _clamp(x: float) -> float:
    return min(max(x, _LO), _HI)


def _lattice_point(rng: random.Random) -> float:
    return rng.choice(_LATTICE)


def _status_for_count(n: int) -> str:
    if n == 0:
        return "NO_ROOT"
    if n == 1:
        return "IDENTIFIED"
    return "MULTIPLE_ROOTS"


def _generate_trio(rng: random.Random) -> list[_Row]:
    if rng.random() < 0.12:
        rows: list[_Row] = []
        shared_count = rng.randint(0, 4)
        for _ in range(3):
            count = shared_count if rng.random() < 0.7 else rng.randint(0, 4)
            roots = [(_lattice_point(rng), _lattice_point(rng), rng.random() < 0.2)
                     for _ in range(count)]
            rows.append(("NON_IDENTIFIABLE", roots))
        return rows

    base_count = rng.randint(0, 4)
    base_roots = [(_lattice_point(rng), _lattice_point(rng)) for _ in range(base_count)]
    mixed_rows: list[_Row] = []
    for _ in range(3):
        count = base_count if rng.random() < 0.75 else rng.randint(0, 4)
        variant_roots: list[tuple[float, float, bool]] = []
        for i in range(count):
            if i < len(base_roots) and rng.random() < 0.8:
                pa0, pb0 = base_roots[i]
                steps_a = rng.choice([-3, -2, -1, 0, 0, 0, 1, 2, 3])
                steps_b = rng.choice([-3, -2, -1, 0, 0, 0, 1, 2, 3])
                pa = _clamp(pa0 + steps_a * 0.0004)
                pb = _clamp(pb0 + steps_b * 0.0004)
            else:
                pa, pb = _lattice_point(rng), _lattice_point(rng)
            variant_roots.append((pa, pb, rng.random() < 0.2))
        mixed_rows.append((_status_for_count(len(variant_roots)), variant_roots))
    return mixed_rows


def test_deterministic_seeded_sweep_agrees_with_reference() -> None:
    rng = random.Random(20260724)
    mismatches: list[tuple[list[_Row], bool, bool]] = []
    for _ in range(200):
        rows = _generate_trio(rng)
        prod, reference = _compare(rows)
        if prod != reference:
            mismatches.append((rows, prod, reference))
    assert not mismatches, (
        "production/reference disagreement on generated trio(s) -- see STAGE3-0006C-D-A3 §13/"
        f"§14 counterexample report: {mismatches!r}")


# ---------------------------------------------------------------- architecture boundary
_ALLOWED_STDLIB_IMPORTS = {"itertools", "math", "typing", "__future__"}


def test_reference_module_imports_only_stdlib_allowlist() -> None:
    src = (Path(__file__).parent / "stability_reference.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for n in names:
            top_level = n.split(".")[0]
            assert top_level in _ALLOWED_STDLIB_IMPORTS, (
                f"reference imports outside the stdlib allowlist: {n}")
            assert not n.startswith("sport_tennis"), f"reference imports production: {n}"
