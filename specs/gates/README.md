# specs/gates — Versioned gate definitions

**Spec:** SPECIFICATION.md §10 · **Requirements:** SPEC-093 · **Human-owned** (see `CODEOWNERS`).

`v1.yaml` defines the decision **structure** of the nine promotion gates (§10.2): gate kinds,
checklist items with on-false flavours, the `anytime_valid_bounds_v1` evidence procedure and
its verdict precedence, and the `payback_v1` computed item. It is **frozen** (ADR 0011) and
deliberately contains **no numeric leaves** — a unit test pins this. Gate boundary *numbers*
are deliberate, pre-registered, human-approved decisions — **not** values an agent invents:
they live in each experiment's §9.7 pre-registration record, and volatile economics live in
`docs/facts.yaml`. Any change here is `gates-v2` plus a new pre-registration.
