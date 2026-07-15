"""Shared pytest / Hypothesis configuration.

Hypothesis' default 200ms per-example deadline is a wall-clock timer. It is inappropriate for
the property tests that perform real disk `fsync` (L0 capture and command journal): under load
a single example can exceed it and fail spuriously, reddening CI with no correctness
regression. These property tests assert correctness invariants, not latency, so the deadline
is disabled suite-wide. No assertion is affected.
"""
from __future__ import annotations

from hypothesis import settings

settings.register_profile("moneymaker", deadline=None)
settings.load_profile("moneymaker")
