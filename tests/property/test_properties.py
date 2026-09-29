"""Property-based invariant tests verifying system properties."""

import random
from gyroscope.state.base import Event, SystemState
from gyroscope.state.serialization import deserialize_state, serialize_state


def test_property_state_serialization_roundtrip_invariant():
    """P2: For any valid state, deserialize(serialize(state)) == state."""
    for i in range(50):
        seq = random.randint(1, 1000)
        ts = random.randint(1000, 1000000)
        symbol = random.choice(["BTC-USD", "ETH-USD", "SOL-USD"])
        custom_val = random.random()

        state = SystemState(
            symbol=symbol,
            sequence_number=seq,
            last_event_id=f"evt_{i}",
            last_event_timestamp_ns=ts,
            custom_state={"val": custom_val, "idx": i},
        )

        serialized = serialize_state(state)
        restored = deserialize_state(serialized)

        assert restored.compute_state_hash() == state.compute_state_hash()
        assert restored.custom_state == state.custom_state


def test_property_event_idempotency_invariant():
    """P3: Processing any event N times (N >= 1) results in identical state as processing 1 time."""
    state = SystemState()
    evt = Event(event_id="evt_prop_1", event_type="UPDATE", event_timestamp_ns=5000, payload={"x": 42})

    state.process_event(evt)
    initial_hash = state.compute_state_hash()

    for _ in range(10):
        state.process_event(evt)

    assert state.compute_state_hash() == initial_hash
    assert state.sequence_number == 1
