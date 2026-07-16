"""Three prices, never conflated (SPEC-051).

``p_market_info`` (model input), ``odds_exec`` (transactable now), and ``p_close`` (diagnostic
only) are **distinct, unrelated types**. They share no base beyond pydantic's ``BaseModel``, so
a function that requires ``OddsExec`` will not type-check when handed a ``MarketInfoPrice`` or a
``ClosePrice`` — the type system prevents the conflation §6.6/§4 warn about. Consumers (e.g. the
EV function, SPEC-050) additionally guard at runtime for dynamically-typed call sites.

Executable/close prices are integer tick indices into the canonical ladder (SPEC-053); no float
represents a price.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from price_contracts.ladder import index_of, is_valid_index, price_of


class OddsExec(BaseModel):
    """Decimal odds actually transactable now — side-specific, size-dependent (SPEC-051).

    v1 is back-only (a hard prohibition), so no side field is carried; a second position and
    lay/hedge are refused elsewhere. The price is an integer tick index (SPEC-053).
    """

    model_config = ConfigDict(frozen=True, strict=True)

    tick_index: int

    @model_validator(mode="after")
    def _valid_tick(self) -> OddsExec:
        if not is_valid_index(self.tick_index):
            raise ValueError(f"tick_index {self.tick_index!r} is not a valid ladder index")
        return self

    @property
    def decimal_odds(self) -> Decimal:
        return price_of(self.tick_index)

    @classmethod
    def from_decimal(cls, price: Decimal) -> OddsExec:
        """Build from an on-ladder decimal price. Raises ``ValueError`` if off-ladder."""
        return cls(tick_index=index_of(price))


class MarketInfoPrice(BaseModel):
    """``p_market_info`` — a market-implied probability used purely as a MODEL INPUT (SPEC-051).

    Never an execution price and never a settlement/close price. Kept as an implied probability
    in the open interval (0, 1).
    """

    model_config = ConfigDict(frozen=True, strict=True)

    implied_probability: Decimal

    @model_validator(mode="after")
    def _in_open_unit_interval(self) -> MarketInfoPrice:
        if not Decimal(0) < self.implied_probability < Decimal(1):
            raise ValueError(
                f"implied_probability {self.implied_probability!r} must be in the open interval (0, 1)"
            )
        return self


class ClosePrice(BaseModel):
    """``p_close`` — a closing price, DIAGNOSTIC ONLY (SPEC-051, SPEC-095).

    Must never be used to price a bet or size a stake; the type keeps it out of those paths.
    An integer tick index into the canonical ladder.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    tick_index: int

    @model_validator(mode="after")
    def _valid_tick(self) -> ClosePrice:
        if not is_valid_index(self.tick_index):
            raise ValueError(f"tick_index {self.tick_index!r} is not a valid ladder index")
        return self

    @property
    def decimal_odds(self) -> Decimal:
        return price_of(self.tick_index)
