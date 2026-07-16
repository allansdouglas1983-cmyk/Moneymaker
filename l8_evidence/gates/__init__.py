"""Deterministic gate evaluator (SPEC-093, money-critical).

`gate evaluate` returns one of the four §10.1 outcomes from a versioned gate spec bound
to data and model hashes. An LLM never decides a gate. See docs/decisions/0011.
"""
