"""Determinism verification tests."""

from gyroscope.state.base import Event, SystemState


def test_identical_event_sequence_yields_identical_state_hash():
    events = [
        Event(event_id=f"evt_{i}", event_type="UPDATE", event_timestamp_ns=1000 + i * 10, payload={"step": i})
        for i in range(10)
    ]

    state_a = SystemState(symbol="BTC-USD")
    for evt in events:
        state_a.process_event(evt)

    state_b = SystemState(symbol="BTC-USD")
    for evt in events:
        state_b.process_event(evt)

    assert state_a.compute_state_hash() == state_b.compute_state_hash()
    assert state_a.sequence_number == 10
    assert state_b.sequence_number == 10


def test_duplicate_event_idempotency():
    state = SystemState()
    evt = Event(event_id="evt_unique_1", event_type="UPDATE", event_timestamp_ns=1000, payload={"val": 100})

    processed_first = state.process_event(evt)
    hash_after_first = state.compute_state_hash()

    processed_second = state.process_event(evt)
    hash_after_second = state.compute_state_hash()

    assert processed_first is True
    assert processed_second is False
    assert state.sequence_number == 1
    assert hash_after_first == hash_after_second
