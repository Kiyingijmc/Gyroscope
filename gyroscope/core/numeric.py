"""Numeric determinism boundary for Gyroscope research and execution kernel.

Defines the boundary between:
1. Authoritative financial and risk quantities (exact Decimal representation).
2. Analytical model quantities (floating-point representation where mathematically appropriate).
"""

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any, Union

# Default authoritative precision: 8 decimal places (sats/pip precision)
AUTHORITATIVE_PRECISION = Decimal("0.00000001")


def to_authoritative_decimal(
    val: Union[int, float, str, Decimal],
    precision: Decimal = AUTHORITATIVE_PRECISION,
) -> Decimal:
    """Convert a value to an authoritative Decimal, quantized deterministically."""
    if isinstance(val, Decimal):
        d = val
    elif isinstance(val, float):
        d = Decimal(str(val))
    else:
        d = Decimal(val)

    return d.quantize(precision, rounding=ROUND_HALF_EVEN)


def assert_exact_financial_quantity(val: Any) -> Decimal:
    """Assert that a value is an exact Decimal and not a binary float."""
    if not isinstance(val, Decimal):
        raise TypeError(
            f"Authoritative financial/risk quantity must be exact Decimal, got {type(val).__name__} ({val!r})"
        )
    return val
