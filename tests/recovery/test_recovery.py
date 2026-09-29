"""Recovery and restoration tests."""

import pytest
from gyroscope.core.exceptions import StateCorruptedException
from gyroscope.state.base import SystemState
from gyroscope.state.serialization import deserialize_state, serialize_state


def test_crash_recovery_from_valid_snapshot():
    state = SystemState(symbol="BTC-USD", sequence_number=100, last_event_id="evt_100", last_event_timestamp_ns=9999)
    snapshot = serialize_state(state)

    recovered_state = deserialize_state(snapshot)
    assert recovered_state.sequence_number == 100
    assert recovered_state.last_event_id == "evt_100"


def test_crash_recovery_from_corrupt_file_fails_safely():
    corrupt_snapshot = "{" + '"schema_version": "1.0", "corrupt": true'

    with pytest.raises(StateCorruptedException):
        deserialize_state(corrupt_snapshot)
