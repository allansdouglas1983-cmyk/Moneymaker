# .claude/agents — Audit subagents (deterministic tools only)

**Spec:** SPECIFICATION.md §12.5, CLAUDE.md · **Advisory only — never a gate.**

Audit subagents get dedicated deterministic tools (`audit-data`, `audit-leakage`,
`run-evaluation`, `reconcile-session`, `gate evaluate`), **not** general Bash. The
`spec-verifier` subagent is advisory evidence only. Status comes from CI, never from an
agent's prose.

> No agents defined yet.
