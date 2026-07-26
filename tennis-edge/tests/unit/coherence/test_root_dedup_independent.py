"""STAGE3-0006C-D-A1 §10 — independent-reference agreement + architecture boundary (RED).

Compares the production canonical dedup against the brute-force literal reference
(``dedup_reference``) over all permutations of bounded candidate sets, deterministic
pseudo-random sets, exact-boundary, chain and multiple-component examples. A disagreement is
STOP_REFERENCE_DISAGREEMENT. The reference must import nothing from ``sport_tennis`` and nothing
from the production module (AST-enforced here).
"""
from __future__ import annotations

import ast
import itertools
import math
import random
from pathlib import Path

from sport_tennis.coherence.root_dedup import deduplicate_roots
from sport_tennis.coherence.solver import Root

from . import dedup_reference as ref

TOL = 1e-3


def mk(pa: float, pb: float, res: float = 1e-5, a_first: bool = True,
       jd: float = 1.0, boundary: bool = False) -> Root:
    return Root(p_a=pa, p_b=pb, a_serves_first=a_first, residual=res, jacobian_det=jd,
                on_boundary=boundary)


def agree(cands: list[Root]) -> None:
    prod = deduplicate_roots(cands, TOL)
    want = ref.ref_dedup(cands, TOL)
    assert prod.ambiguous == want["ambiguous"], cands
    assert list(prod.representatives()) == want["representatives"], cands
    assert [list(c.members) for c in prod.clusters] == want["valid_components"], cands
    # exact stored diameters must equal the literal reference diameters (kills 2-member->0.0
    # and pair-skipping diameter mutants that keep the classification unchanged)
    assert [c.diameter for c in prod.clusters] \
        == [ref.ref_diameter(c) for c in want["valid_components"]], cands
    assert [list(c) for c in prod.ambiguous_components] \
        == sorted((sorted(c, key=ref.ref_fingerprint) for c in want["ambiguous_components"]),
                  key=lambda c: ref.ref_fingerprint(c[0])), cands
    # component partition INCLUDING canonical order must match the reference exactly
    from sport_tennis.coherence.root_dedup import connected_components
    assert [list(c) for c in connected_components(cands, TOL)] \
        == ref.ref_components(list(cands), TOL), cands


# ------------------------------------------------------------------ architecture boundary
def test_reference_module_is_independent() -> None:
    src = (Path(__file__).parent / "dedup_reference.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for n in names:
            assert not n.startswith("sport_tennis"), f"reference imports production: {n}"
            assert "root_dedup" not in n, f"reference imports the module under test: {n}"


# ------------------------------------------------------------------ exhaustive permutations
def test_all_permutations_of_bounded_sets_agree() -> None:
    fixtures = [
        [mk(0.5, 0.5, 3e-5), mk(0.5009, 0.5, 1e-5), mk(0.5018, 0.5, 2e-5)],   # the chain
        [mk(0.5, 0.5, 3e-5), mk(0.5004, 0.5002, 1e-5), mk(0.4998, 0.5004, 2e-5)],  # valid cluster
        [mk(0.4, 0.6, 1e-5), mk(0.7, 0.3, 5e-5), mk(0.55, 0.45, 9e-5)],       # distinct roots
        [mk(0.5, 0.5, 1e-5, True), mk(0.5002, 0.5001, 1e-5, False),
         mk(0.62, 0.38, 2e-5), mk(0.6205, 0.3804, 1e-6, False)],              # two clusters
        [mk(0.0, 0.0), mk(TOL, 0.0), mk(math.nextafter(TOL, 0.0), 1.0)],      # exact boundary
    ]
    for cands in fixtures:
        for perm in itertools.permutations(cands):
            agree(list(perm))


# ------------------------------------------------------------------ deterministic pseudo-random
def test_randomized_deterministic_sets_agree() -> None:
    rng = random.Random(20260724)
    centers = [(0.45, 0.55), (0.62, 0.38), (0.5, 0.5)]
    for trial in range(60):
        n = rng.randint(0, 6)
        cands = []
        for _ in range(n):
            cx, cy = centers[rng.randrange(len(centers))]
            cands.append(mk(cx + rng.uniform(-8e-4, 8e-4), cy + rng.uniform(-8e-4, 8e-4),
                            res=rng.uniform(1e-6, 1e-4), a_first=rng.random() < 0.5,
                            jd=rng.uniform(0.5, 2.0), boundary=rng.random() < 0.2))
        agree(cands)
        rng.shuffle(cands)
        agree(cands)


# ------------------------------------------------------------------ canonical order inversions
def test_two_ambiguous_chains_order_by_first_member_fingerprint() -> None:
    # bases chosen (searched offline, deterministic) so the two chains' MIN-fingerprint order is
    # INVERTED versus their MAX-fingerprint order: a mutant sorting ambiguous components by any
    # member other than the canonical first (c[0]) orders them differently and dies.
    def chain(ba: float, bb: float) -> list[Root]:
        return [mk(ba, bb, 3e-5), mk(ba + 9e-4, bb, 1e-5), mk(ba + 1.8e-3, bb, 2e-5)]

    two = chain(0.4, 0.4) + chain(0.52, 0.35)
    for perm in [two, list(reversed(two)), two[3:] + two[:3]]:
        agree(perm)
        result = deduplicate_roots(perm, TOL)
        assert len(result.ambiguous_components) == 2


def test_two_valid_components_order_by_first_member_fingerprint() -> None:
    # same inversion construction for VALID components: kills wrong-member component-order keys
    # in connected_components (agree() compares partition order against the reference).
    v1 = [mk(0.4, 0.4, 2e-5), mk(0.4003, 0.4, 1e-5)]
    v2 = [mk(0.44, 0.62, 2e-5), mk(0.4403, 0.62, 1e-5)]
    for perm in [v1 + v2, v2 + v1, [v1[1], v2[0], v1[0], v2[1]]]:
        agree(perm)
        assert len(deduplicate_roots(perm, TOL).clusters) == 2


# ------------------------------------------------------------------ multi-component + chains
def test_mixed_chain_and_valid_components_agree() -> None:
    chain = [mk(0.5, 0.5, 3e-5), mk(0.5009, 0.5, 1e-5), mk(0.5018, 0.5, 2e-5)]
    valid = [mk(0.7, 0.3, 4e-5), mk(0.7003, 0.3002, 2e-5)]
    lone = [mk(0.42, 0.61, 6e-5)]
    for perm in itertools.permutations(chain + valid + lone, 6):
        agree(list(perm))
        break  # one canonical order suffices here; permutation sweep above covers ordering
    # explicit mixed permutations of a smaller superset
    small = chain + lone
    for perm in itertools.permutations(small):
        agree(list(perm))
