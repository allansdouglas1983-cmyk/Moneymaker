"""L4 pricing — two-stage race pricing (SPEC-030…SPEC-035, SPECIFICATION.md §6.4).

Stage one: conditional logit on the race as one mutually exclusive choice set. Stage two:
combine out-of-fold fundamentals with the market's implied probability. Outputs reach the
decision layer only as a distribution's conservative lower bound, never a point estimate.
Design: docs/decisions/0012-l4-pricing.md.
"""
