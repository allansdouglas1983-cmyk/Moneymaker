# Research routing protocol (Cost-Aware Deep Research Routing Amendment, 2026-07-16)

The project owner executes broad external investigations through ChatGPT Deep Research
(existing Pro membership). Claude Code does NOT run its own large-agent research
workflow by default.

**Claude Code directly:** repository-local facts; code/schema inspection; narrow
official-document lookups; small questions resolvable from one or two authoritative
sources; questions needed to formulate a research request accurately.

**Handed off to ChatGPT Deep Research:** broad multi-source investigations; current
pricing/provider comparisons; data licensing and commercial-use research; academic
literature reviews; market-microstructure reviews; regulatory/legal synthesis;
competitor/product research; anything where Claude Code's research cost would be
disproportionate. Claude Code may run its own large-agent workflow only with explicit
owner authorisation, or when the question depends on private repository context that
cannot be represented in a handoff.

**Layout:**
- `requests/DR-XXXX-short-title.md` — the structured request: BLOCKING|ADVISORY,
  related SPEC-IDs/gates/ADRs/files/budget decisions, and a complete copy-paste prompt
  (exact questions, current-as-of date, jurisdiction, permitted source hierarchy,
  deliverables, acceptance criteria, unresolved-decision consequence, work that may
  continue, work that must pause).
- `findings/DR-XXXX-....md` — the returned report, saved verbatim with a dated header,
  then assessed: facts / source claims / inferences / recommendations / unresolved
  questions separated, plus an impact assessment. Changes route through the ADR /
  specification-correction process.
- `ledger.yaml` — one entry per DR id: status (REQUESTED | RETURNED | ASSESSED |
  SUPERSEDED), dates, blocking scope.

**Research never authorises:** purchases, paid subscriptions, live access, real-money
activity, model promotion, gate passage, or automatic specification changes
(Amendment A §4: research informs decisions; it never proves a gate).
