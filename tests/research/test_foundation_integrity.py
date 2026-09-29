"""Foundation Integrity Test suite validating Gyroscope architectural invariants."""

from pathlib import Path
import pytest

import gyroscope
from gyroscope.config import SystemConfig
from gyroscope.core.exceptions import AuthorityViolationError
from gyroscope.core.types import ReadinessLevel
from gyroscope.observation import Observation
from gyroscope.state import Event, SystemState, deserialize_state, serialize_state


def test_foundation_package_structure():
    """Verify that required package directories and core files exist on disk."""
    root = Path(__file__).parent.parent.parent
    required_paths = [
        root / "gyroscope" / "core",
        root / "gyroscope" / "config",
        root / "gyroscope" / "observation",
        root / "gyroscope" / "state",
        root / "gyroscope" / "provenance",
        root / "gyroscope" / "logging",
        root / "constitution" / "GYROSCOPE_CONSTITUTION_v1.0.md",
        root / "docs" / "GYROSCOPE_BASELINE.md",
        root / "docs" / "FOUNDATION_MANIFEST_v1.0.md",
        root / "docs" / "architecture" / "GYROSCOPE_ARCHITECTURE_v1.0.md",
    ]
    for path in required_paths:
        assert path.exists(), f"Missing required foundation path: {path}"


def test_configuration_determinism_invariant():
    """Verify that configuration hashing is bit-for-bit deterministic."""
    c1 = SystemConfig(symbol="BTC-USD", readiness_level=ReadinessLevel.R3)
    c2 = SystemConfig(symbol="BTC-USD", readiness_level=ReadinessLevel.R3)
    assert c1.compute_config_hash() == c2.compute_config_hash()


def test_research_execution_boundary_invariant():
    """Verify that R0, R1, R2, and R3 readiness levels cannot enter live execution."""
    for rl in [ReadinessLevel.R0, ReadinessLevel.R1, ReadinessLevel.R2, ReadinessLevel.R3]:
        assert not rl.is_production_executable
    assert ReadinessLevel.R4.is_production_executable


def test_state_event_processing_and_hash_stability():
    """Verify state hash evolution and duplicate event suppression."""
    state = SystemState(symbol="ETH-USD")
    initial_hash = state.compute_state_hash()

    evt = Event(event_id="evt_1", event_type="TICK", event_timestamp_ns=1000, payload={"price": 3000.0})
    processed = state.process_event(evt)
    post_hash = state.compute_state_hash()

    assert processed is True
    assert initial_hash != post_hash

    # Duplicate re-processing must be suppressed and produce identical state hash
    duplicate_processed = state.process_event(evt)
    assert duplicate_processed is False
    assert state.compute_state_hash() == post_hash
