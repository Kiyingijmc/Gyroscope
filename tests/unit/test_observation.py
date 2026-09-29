"""Unit tests for Observation causal timestamps and invariants."""

import pytest
from gyroscope.core.exceptions import CausalViolationError
from gyroscope.observation.models import Observation


def test_valid_observation_creation():
    obs = Observation.create(
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=1050,
        processing_timestamp_ns=1100,
        price=50000.0,
        bid=49999.0,
        ask=50001.0,
        volume=1.5,
    )
    assert obs.symbol == "BTC-USD"
    assert obs.spread == 2.0
    assert obs.event_timestamp_ns == 1000
    assert obs.arrival_timestamp_ns == 1050
    assert obs.processing_timestamp_ns == 1100


def test_arrival_time_preceding_event_time_raises_error():
    with pytest.raises(CausalViolationError, match="Arrival time .* cannot precede event time"):
        Observation.create(
            symbol="BTC-USD",
            timeframe="1m",
            event_timestamp_ns=2000,
            arrival_timestamp_ns=1900,  # Invalid: arrival < event
            processing_timestamp_ns=2100,
            price=50000.0,
        )


def test_processing_time_preceding_event_time_raises_error():
    with pytest.raises(CausalViolationError, match="Processing time .* cannot precede event time"):
        Observation.create(
            symbol="BTC-USD",
            timeframe="1m",
            event_timestamp_ns=2000,
            arrival_timestamp_ns=2050,
            processing_timestamp_ns=1950,  # Invalid: proc < event
            price=50000.0,
        )


def test_decision_time_preceding_processing_time_raises_error():
    with pytest.raises(CausalViolationError, match="Decision time .* cannot precede processing time"):
        Observation(
            observation_id="obs_1",
            symbol="BTC-USD",
            timeframe="1m",
            event_timestamp_ns=1000,
            arrival_timestamp_ns=1050,
            processing_timestamp_ns=1100,
            decision_timestamp_ns=1090,  # Invalid: dec < proc
        )
