"""`python -m l8_evidence.gates` — the pinned `gate evaluate` entry point (SPEC-093).

A dedicated __main__ module instead of an `if __name__ == "__main__"` guard in cli.py:
the guard's string comparison is dead code under test and an unkillable-mutant surface.
"""
from l8_evidence.gates.cli import main

raise SystemExit(main())
