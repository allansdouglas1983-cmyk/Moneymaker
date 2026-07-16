"""Re-export shim: the canonical ladder lives in price_contracts.ladder (ADR 0013
addendum — shared neutral contract). Import paths and class identity preserved for
SPEC-053 consumers; new code should import price_contracts directly.
"""
from price_contracts.ladder import (
    LADDER as LADDER,
    MAX_PRICE as MAX_PRICE,
    MIN_PRICE as MIN_PRICE,
    TICK_COUNT as TICK_COUNT,
    index_of as index_of,
    is_on_ladder as is_on_ladder,
    is_valid_index as is_valid_index,
    price_of as price_of,
)
