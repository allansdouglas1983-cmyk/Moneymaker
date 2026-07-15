# research/scraping — Licensing-restricted, QUARANTINED

**Spec:** SPECIFICATION.md §13.1, §13.2 · **Requirements:** SPEC-100 (active), SPEC-101

Licence-restricted sources live here and **only** here. Racing Post / `rpscrape`-style data
restrict use to private/domestic purposes and prohibit use in connection with a betting
operation — such data **must never enter the deployable feature pipeline**. Until reviewed,
every source is `candidate`, never `permitted` (see the licensed-source registry, §13.2).
Licence taint also propagates through model lineage (§6.12); an import-path ban alone is
insufficient.

> **Status: not yet implemented.** Scaffold marker. Nothing here may be importable from a
> module that can place a bet.
