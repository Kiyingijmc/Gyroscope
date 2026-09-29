"""Research boundary isolation tests enforcing R0-R2 execution prohibitions."""

import pytest
from gyroscope.core.exceptions import AuthorityViolationError
from gyroscope.core.types import ReadinessLevel


def simulate_production_execution_gate(readiness_level: ReadinessLevel) -> bool:
    """Enforce that R0, R1, and R2 code cannot enter production execution path."""
    if not readiness_level.is_production_executable:
        raise AuthorityViolationError(
            f"Readiness level {readiness_level.value} is forbidden from live production execution."
        )
    return True


def test_r0_r1_r2_execution_blocked():
    for rl in [ReadinessLevel.R0, ReadinessLevel.R1, ReadinessLevel.R2, ReadinessLevel.R3]:
        with pytest.raises(AuthorityViolationError):
            simulate_production_execution_gate(rl)


def test_r4_execution_permitted():
    assert simulate_production_execution_gate(ReadinessLevel.R4) is True
