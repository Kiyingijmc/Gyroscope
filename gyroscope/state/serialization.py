"""State serialization and deserialization routines adhering to STATE_SERIALIZATION_CONTRACT."""

import json
from typing import Any, Dict, Optional

from gyroscope.core.exceptions import StateCorruptedException, VersionMismatchError
from gyroscope.state.base import SystemState


def serialize_state(state: SystemState) -> str:
    """Serialize system state into a canonical versioned JSON string."""
    state_hash = state.compute_state_hash()
    data: Dict[str, Any] = {
        "schema_version": state.schema_version,
        "model_version": state.model_version,
        "feature_version": state.feature_version,
        "symbol": state.symbol,
        "timeframe": state.timeframe,
        "last_event_id": state.last_event_id,
        "last_event_timestamp_ns": state.last_event_timestamp_ns,
        "sequence_number": state.sequence_number,
        "state_hash": state_hash,
        "configuration_hash": state.configuration_hash,
        "state_payload": {
            "custom_state": state.custom_state,
            "processed_event_ids": sorted(list(state._processed_event_ids)),
        },
    }
    return json.dumps(data, sort_keys=True, indent=2)


def deserialize_state(
    json_str: str,
    expected_schema_version: str = "1.0",
    expected_model_version: str = "1.0.0",
    expected_config_hash: Optional[str] = None,
) -> SystemState:
    """Deserialize state JSON string and verify state hash and version invariants."""
    try:
        data = json.loads(json_str)
    except Exception as err:
        raise StateCorruptedException(f"Failed to parse JSON state payload: {err}") from err

    schema_version = data.get("schema_version")
    if schema_version != expected_schema_version:
        raise VersionMismatchError(
            f"Schema version mismatch: payload has '{schema_version}', expected '{expected_schema_version}'"
        )

    model_version = data.get("model_version")
    if model_version != expected_model_version:
        raise VersionMismatchError(
            f"Model version mismatch: payload has '{model_version}', expected '{expected_model_version}'"
        )

    config_hash = data.get("configuration_hash", "")
    if expected_config_hash and config_hash != expected_config_hash:
        raise VersionMismatchError(
            f"Configuration hash mismatch: payload has '{config_hash}', expected '{expected_config_hash}'"
        )

    payload = data.get("state_payload", {})
    custom_state = payload.get("custom_state", {})
    processed_event_ids = payload.get("processed_event_ids", [])

    state = SystemState(
        schema_version=schema_version,
        model_version=model_version,
        feature_version=data.get("feature_version", "1.0.0"),
        symbol=data.get("symbol", "GENERIC"),
        timeframe=data.get("timeframe", "1m"),
        sequence_number=data.get("sequence_number", 0),
        last_event_id=data.get("last_event_id", "INIT"),
        last_event_timestamp_ns=data.get("last_event_timestamp_ns", 0),
        configuration_hash=config_hash,
        custom_state=custom_state,
        _processed_event_ids=set(processed_event_ids),
    )

    computed_hash = state.compute_state_hash()
    header_hash = data.get("state_hash")
    if computed_hash != header_hash:
        raise StateCorruptedException(
            f"State hash integrity failure: header state_hash '{header_hash}' does not match computed state_hash '{computed_hash}'"
        )

    return state
