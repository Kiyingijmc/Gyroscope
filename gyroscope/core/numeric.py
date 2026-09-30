"""Numeric determinism boundary for Gyroscope research and execution kernel.

Defines the boundary between:
1. Authoritative financial and risk quantities (exact Decimal representation).
2. Analytical model quantities (floating-point representation where mathematically appropriate).
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import math
from typing import Any, Union

# Default authoritative precision: 8 decimal places (sats/pip precision)
AUTHORITATIVE_PRECISION = Decimal("0.00000001")


def to_authoritative_decimal(
    val: Union[int, float, str, Decimal],
    precision: Decimal = AUTHORITATIVE_PRECISION,
) -> Decimal:
    """Convert a value to an authoritative Decimal, quantized deterministically and rejecting NaN/Infinity."""
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"Authoritative Decimal cannot accept NaN or Infinity float value: {val}")
        d = Decimal(str(val))
    elif isinstance(val, Decimal):
        if val.is_nan() or val.is_infinite():
            raise ValueError(f"Authoritative Decimal cannot accept NaN or Infinity Decimal value: {val}")
        d = val
    elif isinstance(val, str):
        try:
            d = Decimal(val)
        except InvalidOperation as err:
            raise ValueError(f"Invalid string for authoritative Decimal conversion: '{val}'") from err
        if d.is_nan() or d.is_infinite():
            raise ValueError(f"Authoritative Decimal cannot accept NaN or Infinity string value: '{val}'")
    else:
        d = Decimal(val)

    return d.quantize(precision, rounding=ROUND_HALF_EVEN)


def assert_exact_financial_quantity(val: Any) -> Decimal:
    """Assert that a value is an exact Decimal and not a binary float, NaN, or Infinity."""
    if not isinstance(val, Decimal):
        raise TypeError(
            f"Authoritative financial/risk quantity must be exact Decimal, got {type(val).__name__} ({val!r})"
        )
    if val.is_nan() or val.is_infinite():
        raise ValueError(f"Authoritative financial quantity cannot be NaN or Infinity: {val}")
    return val
