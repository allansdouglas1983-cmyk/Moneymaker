# Frozen artefacts

**The SERVED model is `residual-model-v3.json`** (22 features; its digest is what the
site's `/health` reports and what every prediction and forecast row cites). The plain
`residual-model.json` beside it is the earlier 10-feature v1 — it stays because the frozen
`weekly.py` policy v2 names it, and a frozen policy keeps its inputs — but nothing served
reads it. The first refresh run's grading step loaded it by mistake and the feature-set
guard refused loudly (2026-07-29); tools that grade or emit vectors must point at v3.

`residual-model.json` is the fitted residual model — coefficients, training window,
feature-set version and a digest.

**Why it is committed.** A prediction recorded today is only evidence if the coefficients
that produced it can be named months later. A model refitted on every run cannot be held to
anything it said, because there is no longer a "it" that said it. The digest is what a
ledger row cites, and `load_model` refuses a file whose contents no longer match the digest
it carries.

**Re-fitting is a new artefact, not an edit.** `python -m tennis_edge.cli fit` overwrites
this file and produces a different digest, which is the correct behaviour: any prediction
already recorded still names the model that made it, and the new one has to earn its own
record. It is never updated from live outcomes.

**It authorises nothing.** The CLI that consumes it pins `recommendation` to
`NOT_EVALUATED`, and TE-0007 measured this model's exchange performance as undecided at the
power available. See `docs/research/findings/TE-0007-the-model-that-beats-the-price.md`.
