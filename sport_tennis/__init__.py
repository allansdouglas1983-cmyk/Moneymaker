"""Tennis sport module (ADR 0017 S4): immutable domain CONTRACTS only.

No algorithms, no data, no probability estimation, no invented schemas beyond the
named contracts in ``docs/architecture/sport-agnostic-audit.md`` slice S4 and
``docs/decisions/0017-sport-agnostic-transition.md`` Phase 3. See ``domain.py`` for
the contracts and ``adapter.py`` for the tennis :class:`sport_core.adapter.SportAdapter`
declaration.
"""
from __future__ import annotations
