"""Unit tests for SystemState, Event handling, state hashing, and serialization."""

import pytest
from gyroscope.core.exceptions import (
    DeterminismViolationError,
    StateCorruptedException,
    VersionMismatchError,
)
from gyroscope.state.base import Event, SystemState
from gyroscope.state.serialization import deserialize_state, serialize_state


def test_system_state_hash_determinism():
    state1 = SystemState(symbol="ETH-USD", sequence_number=5, custom_state={"alpha": 0.5, "beta": 1.2})
    state2 = SystemState(symbol="ETH-USD", sequence_number=5, custom_state={"beta": 1.2, "alpha": 0.5})

    # Hashes must be identical regardless of dictionary key insertion order
    assert state1.compute_state_hash() == state2.compute_state_hash()


def test_state_serialization_and_deserialization_roundtrip():
    state = SystemState(
        symbol="BTC-USD",
        sequence_number=10,
        last_event_id="evt_001",
        last_event_timestamp_ns=5000,
        custom_state={"counter": 42},
    )

    serialized = serialize_state(state)
    restored = deserialize_state(serialized)

    assert restored.symbol == state.symbol
    assert restored.sequence_number == state.sequence_number
    assert restored.last_event_id == state.last_event_id
    assert restored.custom_state == state.custom_state
    assert restored.compute_state_hash() == state.compute_state_hash()


def test_corrupted_state_hash_rejection():
    state = SystemState(symbol="BTC-USD", sequence_number=1)
    serialized = serialize_state(state)

    # Tamper with custom_state in the JSON payload without updating header state_hash
    tampered = serialized.replace('"custom_state": {}', '"custom_state": {"hacked": true}')

    with pytest.raises(StateCorruptedException, match="Snapshot envelope integrity failure"):
        deserialize_state(tampered)


def test_version_mismatch_rejection():
    state = SystemState(symbol="BTC-USD", schema_version="1.0", model_version="1.0.0")
    serialized = serialize_state(state)

    with pytest.raises(VersionMismatchError, match="Schema version mismatch"):
        deserialize_state(serialized, expected_schema_version="2.0")

    with pytest.raises(VersionMismatchError, match="Model version mismatch"):
        deserialize_state(serialized, expected_model_version="2.0.0")


def test_out_of_order_event_raises_determinism_error():
    state = SystemState(last_event_timestamp_ns=2000)
    out_of_order_event = Event(
        event_id="evt_old",
        event_type="TICK",
        event_timestamp_ns=1500,  # Earlier than last_event_timestamp_ns
    )

    with pytest.raises(DeterminismViolationError, match="Out-of-order event timestamp"):
        state.process_event(out_of_order_event)
