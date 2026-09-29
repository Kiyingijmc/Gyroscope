"""Replay contract verification tests."""

from gyroscope.state.base import Event, SystemState
from gyroscope.state.serialization import deserialize_state, serialize_state


def test_replay_snapshot_resume_identity():
    """Live state processing continuous events must match snapshotting mid-stream and resuming."""
    events = [
        Event(event_id=f"evt_{i}", event_type="UPDATE", event_timestamp_ns=1000 + i * 10, payload={"count": i})
        for i in range(20)
    ]

    # Continuous live processing
    live_state = SystemState(symbol="BTC-USD")
    for evt in events:
        live_state.process_event(evt)

    # Replay with snapshot at event 10
    replay_state = SystemState(symbol="BTC-USD")
    for evt in events[:10]:
        replay_state.process_event(evt)

    # Snapshot state
    snapshot_json = serialize_state(replay_state)

    # Resume state from snapshot (automatically restores processed event IDs for idempotency)
    restored_state = deserialize_state(snapshot_json)

    for evt in events[10:]:
        restored_state.process_event(evt)

    assert restored_state.compute_state_hash() == live_state.compute_state_hash()
    assert restored_state.sequence_number == live_state.sequence_number
