# Mutation survivor class index

total survivors: 46

- EXACT_ALGEBRAIC_IDENTITY: 23
- POSTPONED_ANNOTATION_RUNTIME_INERT: 22
- IDEMPOTENT_NO_SIDE_EFFECT: 1

## Ten revised micro-gates (A1 §11)

- gate 1 distance_and_strict_boundary: killed 29, survived 0
- gates 2+3 graph_edge_construction_and_components (one code body): killed 22, survived 24 (all classified equivalents: 11 annotation + 12 exact-identity + 1 idempotent)
- gate 4 diameter_and_ambiguity_refusal: killed 13, survived 10 (all exact-identity pair-superset)
- gate 5 canonical_representative: killed 5, survived 0
- gate 6 provenance_preservation (fingerprints, finite validation, frozen contracts): killed 11, survived 0
- gate 7 canonical_ordering: 0 mutation specs — cluster_order_key is a pure tuple constructor with no mutable operators; behaviour pinned by the fingerprint-order-inversion and canonical-order tests
- gate 8 public_status_mapping_and_result_assembly: killed 19, survived 12 (11 annotation + 1 len>0 identity); the solver-side NON_IDENTIFIABLE wiring is pinned by the wiring test + V2 golden (solver.py module-wide mutation deferred, as in Milestones B/C)
- gate 9 serialization_and_digest: killed 14, survived 0 (absolute sha256 pins)
- gate 10 reference_architecture_boundary: AST independence test + the brute-force reference agreement runs INSIDE every mutation job as a second oracle

Hardening rounds used: 1 of 2. Round 1 killed 7 behavioural survivors (exact diameters, partition order, absolute digests, exact-tolerance-diameter chain, order-inversion fixtures).
