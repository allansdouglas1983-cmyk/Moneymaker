"""Shared neutral price contracts (SPEC-051/053; relocated per founder direction,
ADR 0013 addendum): the canonical tick ladder and the three distinct price types.
Lower-layer home so both the decision layer and pricing/analytics consumers depend
DOWNWARD on the same contract. ⚠️ MONEY-CRITICAL — same rules as l5_decision.
"""
