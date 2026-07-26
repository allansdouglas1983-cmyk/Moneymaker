# Frozen artefacts

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
